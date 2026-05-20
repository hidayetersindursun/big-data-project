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

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX       = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_REAL      = f"{_S3_PREFIX}://s3-bbuckett/bronze/market"
BRONZE_SYNTHETIC = f"{_S3_PREFIX}://s3-bbuckett/bronze/market_synthetic"
SILVER_PATH      = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"

# NOT: year/month burada YOK — transform withColumn("year"/"month") ile Bronze
# partition kolonlarını date'ten yeniden türetir (aynı isimle override eder).
# DROP_COLS'a year/month konulursa türetilen kolonlar da düşer, FINAL_COLS patlar.
DROP_COLS = {
    "imageUrl", "indexTime", "percentage", "categories", "id",
    "promotionText", "discountRatio", "refinedQuantityUnit",
    "_scraped_at", "_base_date", "day",
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


def _ym(date_str: str) -> int:
    """'2025-05-20' → 202505 (year*100+month, partition pruning için)."""
    parts = date_str.split("-")
    return int(parts[0]) * 100 + int(parts[1])


def read_synthetic(spark):
    """
    bronze/market_synthetic karma partition derinliği:
      geçmiş aylar  → year=YYYY/month=MM/part-*.parquet      (2 seviye)
      cari ay       → year=YYYY/month=MM/day=DD/part-*.parquet (3 seviye)
    Tek read ile okunursa Spark "Conflicting partition column names" hatası verir.
    İki derinlik ayrı okunup birleştirilir; day kolonu atılır (year/month yeterli).
    """
    base = BRONZE_SYNTHETIC
    df_ym = (
        spark.read.option("basePath", base)
        .parquet(f"{base}/year=*/month=*/part-*.parquet")
    )
    try:
        df_ymd = (
            spark.read.option("basePath", base)
            .parquet(f"{base}/year=*/month=*/day=*/part-*.parquet")
        )
        if "day" in df_ymd.columns:
            df_ymd = df_ymd.drop("day")
        return df_ym.unionByName(df_ymd, allowMissingColumns=True)
    except Exception as e:
        print(f"  (3-seviye partition okunamadı, sadece 2-seviye: {e})")
        return df_ym


def filter_by_date(df, start_date, end_date):
    """Bronze partition kolonları year/month üzerinden tarih aralığı filtrele."""
    ym = F.col("year") * 100 + F.col("month")
    if start_date:
        df = df.filter(ym >= _ym(start_date))
    if end_date:
        df = df.filter(ym <= _ym(end_date))
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None,
                        help="YYYY-MM-DD; partition pruning (year/month). Default: tüm Bronze")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--mode", choices=("overwrite", "append"), default="overwrite")
    args = parser.parse_args()

    spark = get_spark_session("market_silver")

    # market_synthetic büyük (5.5 GB) — shuffle partition sayısını artır
    spark.conf.set("spark.sql.shuffle.partitions", "200")

    if args.start_date or args.end_date:
        print(f"Tarih filtresi: {args.start_date or '...'} → {args.end_date or '...'}")

    print("=== bronze/market (gerçek) ===")
    df_real = filter_by_date(spark.read.parquet(BRONZE_REAL), args.start_date, args.end_date)
    df_real_s = transform_real(df_real)
    print(f"  Bronze : {df_real.count():,} satır")
    print(f"  Silver : {df_real_s.count():,} satır")

    print("\n=== bronze/market_synthetic ===")
    df_synth = filter_by_date(read_synthetic(spark), args.start_date, args.end_date)
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
        .mode(args.mode)
        .partitionBy("year", "month")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
