"""
Gold: price_inequality

İki ayrı çıktı:
  gold/price_inequality_market/    → market_prices üzerinden 81 şehir (per-kg)
  gold/price_inequality_hal/       → hal_prices üzerinden 81 şehir

Her ikisinde de per (date, product_canonical):
  - avg_price, median_price, min_price, max_price
  - cv (coefficient of variation = stddev/mean)
  - spread_pct = (max - min) / avg * 100
  - min_city, max_city
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

from pyspark.sql import functions as F
from pyspark.sql import Window
from utils.spark_session import get_spark_session
from silver.utils.cities import normalize_city_expr  # noqa: E402

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_MARKET = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"
SILVER_HAL = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_MARKET = f"{_S3_PREFIX}://s3-bbuckett/gold/price_inequality_market"
GOLD_HAL = f"{_S3_PREFIX}://s3-bbuckett/gold/price_inequality_hal"


def compute_inequality(df, price_col, product_col, source_label):
    """Per (date, product) için şehirler arası eşitsizlik metrikleri."""
    # Önce şehir bazında günlük ortalama
    city_avg = (
        df
        .groupBy("date", product_col, "city")
        .agg(F.avg(price_col).alias("city_price"))
    )

    # Sonra ürün bazında şehirler arası agg
    agg = (
        city_avg
        .groupBy("date", product_col)
        .agg(
            F.avg("city_price").alias("avg_price"),
            F.expr("percentile_approx(city_price, 0.5)").alias("median_price"),
            F.min("city_price").alias("min_price"),
            F.max("city_price").alias("max_price"),
            F.stddev("city_price").alias("std_price"),
            F.count("*").alias("n_cities"),
        )
        .filter(F.col("avg_price") > 0)
        .withColumn("cv", F.col("std_price") / F.col("avg_price"))
        .withColumn("spread_pct", (F.col("max_price") - F.col("min_price")) / F.col("avg_price") * 100)
    )

    # min_city, max_city
    w_min = Window.partitionBy("date", product_col).orderBy(F.col("city_price").asc())
    w_max = Window.partitionBy("date", product_col).orderBy(F.col("city_price").desc())
    min_max = (
        city_avg
        .withColumn("rn_min", F.row_number().over(w_min))
        .withColumn("rn_max", F.row_number().over(w_max))
    )
    mins = (min_max.filter(F.col("rn_min") == 1)
            .select("date", product_col, F.col("city").alias("min_city")))
    maxs = (min_max.filter(F.col("rn_max") == 1)
            .select("date", product_col, F.col("city").alias("max_city")))

    out = (
        agg
        .join(mins, ["date", product_col], "left")
        .join(maxs, ["date", product_col], "left")
        .withColumn("year", F.year("date"))
        .withColumn("month", F.month("date"))
        .withColumn("source_label", F.lit(source_label))
    )
    return out.withColumnRenamed(product_col, "product")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    args = parser.parse_args()

    spark = get_spark_session("gold_price_inequality")
    spark.conf.set("spark.sql.shuffle.partitions", "200")

    # ---- Hal tarafı (81 şehir, hal_prices) ----
    hal = spark.read.parquet(SILVER_HAL)
    if args.start_date:
        hal = hal.filter(F.col("date") >= args.start_date)
    if args.end_date:
        hal = hal.filter(F.col("date") <= args.end_date)
    hal = hal.withColumn("city", normalize_city_expr(F.col("city")))

    hal_out = compute_inequality(hal, "price_avg", "product_name", "hal")
    hal_out.printSchema()
    print(f"Hal inequality satır: {hal_out.count():,}")
    (hal_out.write.mode("overwrite").partitionBy("year", "month").parquet(GOLD_HAL))
    print(f"Yazıldı → {GOLD_HAL}")

    # ---- Market tarafı (joined kullan: product_canonical zaten var) ----
    joined = spark.read.parquet(SILVER_JOINED).filter(F.col("market_price_per_kg").isNotNull())
    if args.start_date:
        joined = joined.filter(F.col("date") >= args.start_date)
    if args.end_date:
        joined = joined.filter(F.col("date") <= args.end_date)

    mkt_out = compute_inequality(joined, "market_price_per_kg", "product_canonical", "market")
    print(f"Market inequality satır: {mkt_out.count():,}")
    (mkt_out.write.mode("overwrite").partitionBy("year", "month").parquet(GOLD_MARKET))
    print(f"Yazıldı → {GOLD_MARKET}")

    spark.stop()


if __name__ == "__main__":
    main()
