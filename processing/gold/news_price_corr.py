"""
Gold: news_price_corr

GDELT günlük food/Turkey-food haber sayısı + ortalama tone × günlük fiyat değişimi
arasındaki cross-correlation (lag 0..14 gün).

Per (product_canonical, lag_days):
  correlation = corr(daily_price_change, gdelt_metric_lagged)
  p_value     = scipy.stats.pearsonr p-value

GDELT backfill gap'leri olduğu için sadece tam-coverage yıllara filtre uygula
(default: 2017, 2018, 2022, 2023, 2024).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql import Window
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_GDELT = f"{_S3_PREFIX}://s3-bbuckett/silver/gdelt_daily"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/news_price_corr"

DEFAULT_FULL_YEARS = [2017, 2018, 2022, 2023, 2024]
MAX_LAG = 14
TOP_PRODUCTS = 20


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=str, default=",".join(str(y) for y in DEFAULT_FULL_YEARS),
                        help="Comma-separated years (default: tam coverage yıllar)")
    parser.add_argument("--top-products", type=int, default=TOP_PRODUCTS)
    args = parser.parse_args()

    target_years = [int(y) for y in args.years.split(",")]

    spark = get_spark_session("gold_news_price_corr")

    gdelt = spark.read.parquet(SILVER_GDELT).filter(F.col("year").isin(*target_years))
    joined = (
        spark.read.parquet(SILVER_JOINED)
        .filter(F.col("year").isin(*target_years))
        .filter(F.col("market_price_per_kg").isNotNull())
    )

    # Top N ürün
    top = (
        joined
        .groupBy("product_canonical")
        .agg(F.count("*").alias("n"))
        .orderBy(F.col("n").desc())
        .limit(args.top_products)
        .collect()
    )
    top_products = [r["product_canonical"] for r in top]
    print(f"Top {args.top_products} ürün: {top_products}")

    joined = joined.filter(F.col("product_canonical").isin(*top_products))

    # Per (date, product) günlük ortalama market_price
    daily_price = (
        joined
        .groupBy("date", "product_canonical")
        .agg(F.avg("market_price_per_kg").alias("price"))
    )

    # Önceki günle fark
    w = Window.partitionBy("product_canonical").orderBy("date")
    daily_change = (
        daily_price
        .withColumn("price_prev", F.lag("price").over(w))
        .withColumn("d_price", F.col("price") - F.col("price_prev"))
        .withColumn("d_price_pct",
                    F.when(F.col("price_prev") > 0,
                           (F.col("price") - F.col("price_prev")) / F.col("price_prev")))
        .select("date", "product_canonical", "d_price_pct")
    )

    # Pandas'a indir
    price_pdf = daily_change.dropna().toPandas()
    gdelt_pdf = (
        gdelt
        .select("date", "n_food", "avg_tone_food", "n_turkey_food", "avg_tone_turkey_food")
        .toPandas()
    )
    price_pdf["date"] = pd.to_datetime(price_pdf["date"])
    gdelt_pdf["date"] = pd.to_datetime(gdelt_pdf["date"])

    from scipy.stats import pearsonr

    results = []
    for prod in top_products:
        ts = price_pdf[price_pdf["product_canonical"] == prod].set_index("date")["d_price_pct"]
        if len(ts) < 30:
            continue
        for metric in ["n_food", "avg_tone_food", "n_turkey_food", "avg_tone_turkey_food"]:
            news = gdelt_pdf.set_index("date")[metric]
            for lag in range(MAX_LAG + 1):
                # News'i lag gün sonraki fiyatla bağla
                news_lagged = news.shift(lag)
                merged = pd.concat([ts, news_lagged.rename("news")], axis=1, join="inner").dropna()
                if len(merged) < 30:
                    continue
                try:
                    r, p = pearsonr(merged["d_price_pct"], merged["news"])
                except Exception:
                    continue
                results.append({
                    "product_canonical": prod,
                    "gdelt_metric": metric,
                    "lag_days": lag,
                    "correlation": float(r),
                    "p_value": float(p),
                    "n_obs": int(len(merged)),
                })

    if not results:
        print("UYARI: Hiçbir korelasyon hesaplanamadı.")
        spark.stop()
        return

    pdf_out = pd.DataFrame(results)
    out_df = spark.createDataFrame(pdf_out)
    out_df.printSchema()
    out_df.orderBy(F.col("p_value").asc()).show(30, truncate=False)

    (
        out_df
        .write
        .mode("overwrite")
        .partitionBy("gdelt_metric")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
