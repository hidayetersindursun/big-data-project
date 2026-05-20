"""
Bronze akaryakit → Silver akaryakit

Dönüşümler:
  - Tarih (DD.MM.YYYY string) → date (DATE)
  - İl → city (Title Case)
  - Marka → brand
  - Yakıt Tipi → fuel_type
  - Fiyat → price_tl
  - source etiketi eklendi
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_PATH = f"{_S3_PREFIX}://s3-bbuckett/bronze/akaryakit"
SILVER_PATH = f"{_S3_PREFIX}://s3-bbuckett/silver/akaryakit"


def transform(df):
    return (
        df
        # Tarih: DD.MM.YYYY → DATE
        .withColumn("date", F.to_date(F.col("Tarih"), "dd.MM.yyyy"))

        # Şehir: ALL CAPS → Title Case
        .withColumn("city", F.initcap(F.lower(F.col("İl"))))

        # Sütun yeniden adlandırma
        .withColumnRenamed("Marka", "brand")
        .withColumnRenamed("Yakıt Tipi", "fuel_type")
        .withColumnRenamed("Fiyat", "price_tl")

        # Kaynak etiketi
        .withColumn("source", F.lit("akaryakit"))

        # Ham sütunları kaldır
        .drop("Tarih", "İl")

        # Null tarih veya fiyat satırlarını at
        .filter(F.col("date").isNotNull() & F.col("price_tl").isNotNull())

        .select("date", "city", "brand", "fuel_type", "price_tl", "source")
    )


def main():
    spark = get_spark_session("akaryakit_silver")

    df_bronze = spark.read.parquet(BRONZE_PATH)
    df_silver = transform(df_bronze)

    print(f"Bronze satır sayısı : {df_bronze.count():,}")
    print(f"Silver satır sayısı : {df_silver.count():,}")
    df_silver.printSchema()
    df_silver.show(10, truncate=False)

    print("\n=== Yakıt tipi dağılımı ===")
    df_silver.groupBy("fuel_type").count().orderBy("count", ascending=False).show(20, truncate=False)

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
