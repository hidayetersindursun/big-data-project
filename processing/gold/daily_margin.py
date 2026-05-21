"""
Gold: daily_margin

Girdi : silver/market_hal_joined
Çıktı : gold/daily_margin/year=YYYY/month=MM/...

Per (date, city, product_canonical, market_name):
  - market_avg, hal_avg (silver_joined zaten günlük aggregate)
  - margin_pct
  - margin_7d: 7-gün rolling ortalama (Window)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

from pyspark.sql import functions as F
from pyspark.sql import Window
from utils.spark_session import get_spark_session
from utils.partitions import filter_by_date_partitioned  # noqa: E402

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/daily_margin"


def transform(df):
    # Sadece margin'i hesaplanabilen (hem hal hem market dolu) satırlar
    base = df.filter(
        F.col("hal_price_per_kg").isNotNull()
        & F.col("market_price_per_kg").isNotNull()
        & (F.col("hal_price_per_kg") > 0)
    )

    w = (
        Window
        .partitionBy("city", "product_canonical", "market_name")
        .orderBy("date")
        .rowsBetween(-6, 0)
    )

    return (
        base
        .withColumn("margin_7d", F.avg("margin_pct").over(w))
        .withColumn("hal_price_7d", F.avg("hal_price_per_kg").over(w))
        .withColumn("market_price_7d", F.avg("market_price_per_kg").over(w))
        .select(
            "date", "year", "month", "city", "product_canonical", "market_name",
            "hal_price_per_kg", "market_price_per_kg",
            "margin_abs", "margin_pct", "margin_7d",
            "hal_price_7d", "market_price_7d",
            "hal_source_type", "market_source_type",
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    args = parser.parse_args()

    spark = get_spark_session("gold_daily_margin")
    spark.conf.set("spark.sql.shuffle.partitions", "200")

    # silver_joined year/month partition'lı → year/month pruning ile S3 okumasını daralt.
    df = filter_by_date_partitioned(
        spark.read.parquet(SILVER_JOINED), args.start_date, args.end_date
    )

    out = transform(df)
    out.printSchema()
    n = out.count()
    print(f"\nGold daily_margin satır: {n:,}")

    # repartition(year, month) → her ay partition'ı ~1 dosya (küçük-dosya patlamasını önler).
    (
        out
        .repartition("year", "month")
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
