"""
Bronze commodities → Silver commodities

Dönüşümler:
  - date (string YYYY-MM-DD) → date (DATE)
  - commodity_name alt çizgi temizlendi (Brent_Oil → Brent Oil)
  - _ingested_at kaldırıldı (ingestion metadata)
  - source etiketi eklendi
  - Partition: commodity_name (10 emtia, küçük veri)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_PATH = f"{_S3_PREFIX}://s3-bbuckett/bronze/commodities"
SILVER_PATH = f"{_S3_PREFIX}://s3-bbuckett/silver/commodities"


def transform(df):
    return (
        df
        # date: string → DATE
        .withColumn("date", F.to_date(F.col("date"), "yyyy-MM-dd"))

        # commodity_name: alt çizgi → boşluk
        .withColumn("commodity_name", F.regexp_replace(F.col("commodity_name"), "_", " "))

        # ingestion metadata kaldır
        .drop("_ingested_at")

        # kaynak etiketi
        .withColumn("source", F.lit("commodities"))

        # null tarih veya fiyat satırlarını at
        .filter(F.col("date").isNotNull() & F.col("close").isNotNull())

        .select("date", "ticker", "commodity_name", "open", "high", "low", "close", "volume", "source")
    )


def main():
    spark = get_spark_session("commodities_silver")

    df_bronze = spark.read.parquet(BRONZE_PATH)
    df_silver = transform(df_bronze)

    print(f"Bronze satır sayısı : {df_bronze.count():,}")
    print(f"Silver satır sayısı : {df_silver.count():,}")
    df_silver.printSchema()
    df_silver.show(10, truncate=False)

    print("\n=== Emtia dağılımı ===")
    from pyspark.sql import functions as F
    df_silver.groupBy("commodity_name", "ticker").agg(
        F.min("date").alias("ilk_tarih"),
        F.max("date").alias("son_tarih"),
        F.count("*").alias("satir")
    ).orderBy("commodity_name").show(20, truncate=False)

    (
        df_silver
        .write
        .mode("append")
        .partitionBy("commodity_name")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
