"""
Bronze hal_all → Silver hal_prices

Dönüşümler:
  - tarih (string) → date (DATE)
  - en_dusuk / en_yuksek (string) → price_min / price_max (DOUBLE)
  - price_avg hesaplama
  - urun → product_name (Title Case standardizasyonu)
  - kategori → category (Title Case, null → "Bilinmiyor")
  - sehir → city (mevcut haliyle korunur, zaten standart)
  - veri_turu → source_type (gerçek/sentetik ayrımı Gold'da kullanılır)
  - Partition sütunları (year, month) kaldırılır, date'den türetilir
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_PATH = f"{_S3_PREFIX}://s3-bbuckett/bronze/hal_all"
SILVER_PATH = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"


def transform(df):
    return (
        df
        # Tarih: string → DATE
        .withColumn("date", F.to_date(F.col("tarih"), "yyyy-MM-dd"))

        # Fiyat: string → DOUBLE
        .withColumn("price_min", F.col("en_dusuk").cast("double"))
        .withColumn("price_max", F.col("en_yuksek").cast("double"))
        .withColumn("price_avg", F.round((F.col("price_min") + F.col("price_max")) / 2, 2))

        # Ürün adı: Title Case standardizasyonu
        .withColumn("product_name", F.initcap(F.lower(F.trim(F.col("urun")))))

        # Kategori: Title Case + null doldurma
        .withColumn(
            "category",
            F.initcap(F.lower(F.coalesce(F.trim(F.col("kategori")), F.lit("Bilinmiyor"))))
        )

        # Şehir: mevcut haliyle koru, sütun adını standartlaştır
        .withColumnRenamed("sehir", "city")

        # Kaynak tipi
        .withColumnRenamed("veri_turu", "source_type")

        # Sabit kaynak etiketi
        .withColumn("source", F.lit("hal"))

        # Gereksiz / türetilmiş sütunları kaldır
        .drop("tarih", "en_dusuk", "en_yuksek", "urun", "kategori", "year", "month")

        # Null fiyat satırlarını at
        .filter(F.col("price_min").isNotNull() & F.col("price_max").isNotNull())

        # Sütun sırası
        .select(
            "date", "city", "product_name", "category",
            "price_min", "price_max", "price_avg",
            "source_type", "source"
        )
    )


def main():
    spark = get_spark_session("hal_silver")

    df_bronze = spark.read.parquet(BRONZE_PATH)
    df_silver = transform(df_bronze)

    print(f"Bronze satır sayısı : {df_bronze.count():,}")
    print(f"Silver satır sayısı : {df_silver.count():,}")
    df_silver.printSchema()
    df_silver.show(10, truncate=False)

    (
        df_silver
        .write
        .mode("append")
        .partitionBy("date")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
