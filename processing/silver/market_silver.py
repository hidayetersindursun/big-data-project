"""
Bronze market + Bronze market_synthetic → Silver market_prices

İki kaynak ayrı okunur, sütunlar hizalanır, union edilir:
  bronze/market           → gerçek scrape (2026+, year/month/day partition)
  bronze/market_synthetic → sentetik geçmiş (2019-2025, year/month partition)

Dönüşümler:
  - _scraped_at (ISO-8601 string) → date (DATE)
  - _city / _district → city / district
  - marketAdi → market_name
  - title → product_name
  - main_category → category
  - unitPriceValue → unit_price_value (TL, mevcut birim başına)
  - unitPrice → unit_price_str (birim bilgisi için korundu — "270,00 ₺/Kg" vb.)
  - refinedVolumeOrWeight → volume_weight
  - _synthetic (bool) + _base_date (str) → source_type ("real" / "synthetic")
  - market kaynağında olmayan _synthetic / _base_date kolonları None ile doldurulur

Atılan kolonlar:
  - imageUrl, indexTime, percentage, categories, id
  - promotionText, discountRatio, refinedQuantityUnit (büyük çoğunluk null)
  - _scraped_at (date'e dönüştürüldükten sonra)
  - _base_date (source_type'a dönüştürüldükten sonra)
  - year, month, day (bronze partition; silver'da year/month yeniden oluşturulur)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX       = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_REAL      = f"{_S3_PREFIX}://s3-bbuckett/bronze/market"
BRONZE_SYNTHETIC = f"{_S3_PREFIX}://s3-bbuckett/bronze/market_synthetic"
SILVER_PATH      = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"

DROP_COLS = {
    "imageUrl", "indexTime", "percentage", "categories", "id",
    "promotionText", "discountRatio", "refinedQuantityUnit",
    "_scraped_at", "_base_date", "year", "month", "day",
    "_synthetic",
}


def transform_real(df):
    return (
        df
        .withColumn("date",        F.to_date(F.col("_scraped_at")))
        .withColumn("city",        F.col("_city"))
        .withColumn("district",    F.col("_district"))
        .withColumn("product_name",F.col("title"))
        .withColumn("category",    F.col("main_category"))
        .withColumn("market_name", F.col("marketAdi"))
        .withColumn("unit_price_value", F.col("unitPriceValue"))
        .withColumn("unit_price_str",   F.col("unitPrice"))
        .withColumn("volume_weight",    F.col("refinedVolumeOrWeight"))
        .withColumn("source_type", F.lit("real"))
        .withColumn("source",      F.lit("market"))
        .withColumn("year",        F.year(F.col("date")))
        .withColumn("month",       F.month(F.col("date")))
        .drop(*[c for c in DROP_COLS if c in df.columns])
        .drop("_city", "_district", "title", "main_category",
              "marketAdi", "unitPriceValue", "unitPrice", "refinedVolumeOrWeight",
              "menu_category")
        .filter(F.col("date").isNotNull() & F.col("unit_price_value").isNotNull())
    )


def transform_synthetic(df):
    return (
        df
        .withColumn("date",        F.to_date(F.col("_scraped_at")))
        .withColumn("city",        F.col("_city"))
        .withColumn("district",    F.col("_district"))
        .withColumn("product_name",F.col("title"))
        .withColumn("category",    F.col("main_category"))
        .withColumn("market_name", F.col("marketAdi"))
        .withColumn("unit_price_value", F.col("unitPriceValue"))
        .withColumn("unit_price_str",   F.col("unitPrice"))
        .withColumn("volume_weight",    F.col("refinedVolumeOrWeight"))
        .withColumn("source_type", F.lit("synthetic"))
        .withColumn("source",      F.lit("market"))
        .withColumn("year",        F.year(F.col("date")))
        .withColumn("month",       F.month(F.col("date")))
        .drop(*[c for c in DROP_COLS if c in df.columns])
        .drop("_city", "_district", "title", "main_category",
              "marketAdi", "unitPriceValue", "unitPrice", "refinedVolumeOrWeight",
              "menu_category")
        .filter(F.col("date").isNotNull() & F.col("unit_price_value").isNotNull())
    )


FINAL_COLS = [
    "date", "year", "month",
    "city", "district",
    "product_name", "brand", "category",
    "market_name", "depotId", "depotName",
    "price", "unit_price_value", "unit_price_str", "volume_weight",
    "discount", "latitude", "longitude",
    "source_type", "source",
]


def main():
    spark = get_spark_session("market_silver")

    # market_synthetic büyük (5.5 GB) — shuffle partition sayısını artır
    spark.conf.set("spark.sql.shuffle.partitions", "200")

    print("=== bronze/market (gerçek) ===")
    df_real = spark.read.parquet(BRONZE_REAL)
    df_real_s = transform_real(df_real)
    print(f"  Bronze : {df_real.count():,} satır")
    print(f"  Silver : {df_real_s.count():,} satır")

    print("\n=== bronze/market_synthetic ===")
    df_synth = spark.read.parquet(BRONZE_SYNTHETIC)
    df_synth_s = transform_synthetic(df_synth)
    print(f"  Bronze : {df_synth.count():,} satır")
    print(f"  Silver : {df_synth_s.count():,} satır")

    df_silver = df_real_s.select(FINAL_COLS).unionByName(df_synth_s.select(FINAL_COLS))

    print(f"\n=== Birleşik silver/market_prices ===")
    print(f"  Toplam : {df_silver.count():,} satır")
    df_silver.printSchema()
    df_silver.show(5, truncate=False)

    print("\n=== Kaynak dağılımı ===")
    df_silver.groupBy("source_type").count().show()

    print("\n=== Yıl dağılımı ===")
    df_silver.groupBy("year").count().orderBy("year").show()

    (
        df_silver
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
