"""
Bronze epias → Silver epias

26 dataset, her biri farklı şemada. Her dataset kendi Silver alt klasörüne yazılır:
  s3a://s3-bbuckett/silver/epias/{dataset_adı}/

Tüm datasetlerde ortak dönüşümler:
  - timestamp (ISO-8601 string +03:00) → TIMESTAMP
  - _dataset, _source, _ingested_at meta kolonları kaldırılır
  - source = "epias" sabit etiketi eklenir
  - year / month partition korunur
  - Null timestamp satırları atılır

5 datasette schema evolution sorunu (bronzda aynı kolon farklı dönemlerde
int↔double olarak yazılmış):
  mcp_smp_imbalance, zero_balance_adjustment, kgup,
  renewable_realtime_generation, unplanned_outages
  → mergeSchema=true + enableVectorizedReader=false ile çözülür
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_BASE = f"{_S3_PREFIX}://s3-bbuckett/bronze/epias"
SILVER_BASE = f"{_S3_PREFIX}://s3-bbuckett/silver/epias"

ALL_DATASETS = [
    "price_and_cost",
    "mcp_smp_imbalance",
    "zero_balance_adjustment",
    "real_time_generation",
    "realtime_consumption",
    "kgup",
    "consumption",
    "injection_quantity",
    "renewable_realtime_generation",
    "renewable_injection_quantity",
    "wind_forecast",
    "renewable_unit_cost",
    "renewable_total_cost",
    "dam_volume",
    "intraday_market",
    "primary_frequency_capacity",
    "secondary_frequency_capacity",
    "transmission_loss_factor",
    "dam_daily_level",
    "dam_active_fullness",
    "dam_active_volume",
    "natural_gas_spot",
    "natural_gas_balancing",
    "natural_gas_daily_transmission",
    "planned_outages",
    "unplanned_outages",
]

# Bronzda aynı kolon farklı dönemlerde farklı numerik tiplerle yazılmış
SCHEMA_EVOLUTION_DATASETS = {
    "mcp_smp_imbalance",        # positiveImbalance: int↔double
    "zero_balance_adjustment",  # renewableImbalance: double↔int64
    "kgup",                     # tasKomur: bigint↔double
    "renewable_realtime_generation",  # gunes: bigint↔double
    "unplanned_outages",        # hourlyLoadAvg: bigint↔double
}

META_COLS = {"_dataset", "_source", "_ingested_at"}


def read_bronze(spark, dataset):
    path = f"{BRONZE_BASE}/{dataset}"
    if dataset in SCHEMA_EVOLUTION_DATASETS:
        spark.conf.set("spark.sql.parquet.enableVectorizedReader", "false")
        df = spark.read.option("mergeSchema", "true").parquet(path)
        spark.conf.set("spark.sql.parquet.enableVectorizedReader", "true")
    else:
        df = spark.read.parquet(path)
    return df


def transform(df):
    to_drop = [c for c in META_COLS if c in df.columns]
    if to_drop:
        df = df.drop(*to_drop)

    df = (
        df
        .withColumn("timestamp", F.col("timestamp").cast("timestamp"))
        .withColumn("source", F.lit("epias"))
        .filter(F.col("timestamp").isNotNull())
    )
    return df


def process(spark, dataset):
    print(f"\n{'='*50}")
    print(f"Dataset: {dataset}")

    df_bronze = read_bronze(spark, dataset)
    df_silver = transform(df_bronze)

    bronze_count = df_bronze.count()
    silver_count = df_silver.count()
    print(f"  Bronze : {bronze_count:,} satır")
    print(f"  Silver : {silver_count:,} satır  (düşen: {bronze_count - silver_count:,})")
    df_silver.printSchema()

    silver_path = f"{SILVER_BASE}/{dataset}"
    (
        df_silver
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(silver_path)
    )
    print(f"  Yazıldı → {silver_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=ALL_DATASETS,
        help="Tek bir dataset işle (varsayılan: tümü)",
    )
    args = parser.parse_args()

    spark = get_spark_session("epias_silver")

    targets = [args.dataset] if args.dataset else ALL_DATASETS
    failed = []

    for dataset in targets:
        try:
            process(spark, dataset)
        except Exception as e:
            print(f"  HATA [{dataset}]: {e}")
            failed.append(dataset)

    print(f"\n{'='*50}")
    print(f"Tamamlanan : {len(targets) - len(failed)}/{len(targets)}")
    if failed:
        print(f"Başarısız  : {failed}")

    spark.stop()


if __name__ == "__main__":
    main()
