"""
Silver join: market_prices + hal_prices → market_hal_joined

Bu Silver'ın "trunk" tablosudur — bütün Gold tabloları bunun üstünde duruyor.

Akış:
  1. silver/market_prices oku.
       Filtre: unit_price_str '/Kg' ile bitiyor (per-kg ürünler).
       Filtre: discount = false (indirimli ürünler marjı bozar).
  2. silver/hal_prices oku.
  3. lookups/hal_market_mapping.csv'yi broadcast et.
  4. Her iki tarafı normalize_city ile şehir adı uniformize.
  5. Market ⋈ mapping ON market.product_name = mapping.market_product
       → product_canonical, unit_conversion_factor uygula.
  6. Hal ⋈ mapping_distinct(hal_product, product_canonical)
       ON hal.product_name = mapping.hal_product
  7. (date, city, product_canonical) anahtarında FULL OUTER JOIN.
  8. margin_abs, margin_pct, year, month türet.
  9. partitionBy(year, month) ile yaz.

CLI:
  python processing/silver/silver_joined.py
  python processing/silver/silver_joined.py --start-date 2025-05-20 --end-date 2026-05-20
  python processing/silver/silver_joined.py --debug-day 2026-05-13
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session
from utils.cities import normalize_city_expr  # noqa: E402

_ON_EMR = os.environ.get("ON_EMR", "false").lower() == "true"
_S3_PREFIX = "s3" if _ON_EMR else "s3a"
SILVER_MARKET = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"
SILVER_HAL = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"
SILVER_OUT = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"

LOOKUP_DIR = Path(__file__).resolve().parent / "lookups"
MAPPING_CSV = LOOKUP_DIR / "hal_market_mapping.csv"
# EMR cluster mode'da script S3'ten tek dosya iner — lookups/ klasörü inmez.
# ON_EMR'da mapping CSV, aws s3 sync ile yüklenmiş code/ kopyasından okunur.
MAPPING_CSV_EMR = f"{_S3_PREFIX}://s3-bbuckett/code/processing/silver/lookups/hal_market_mapping.csv"

# Mapping CSV'de geçerli sayılacak confidence değerleri
VALID_CONFIDENCE = ("exact", "kg_equivalent")


def read_mapping(spark):
    """Lookup CSV'yi oku ve broadcast'le."""
    if _ON_EMR:
        path = MAPPING_CSV_EMR
    else:
        if not MAPPING_CSV.exists():
            raise FileNotFoundError(
                f"{MAPPING_CSV} bulunamadı. Önce build_mapping_skeleton.py + "
                f"build_mapping_with_claude.py çalıştırın ve manuel review yapın."
            )
        path = f"file:///{MAPPING_CSV.as_posix()}"
    df = (
        spark.read.option("header", "true")
        .csv(path)
        .filter(F.col("confidence").isin(*VALID_CONFIDENCE))
        .withColumn("unit_conversion_factor", F.col("unit_conversion_factor").cast("double"))
        .select("hal_product", "market_product", "product_canonical", "unit_conversion_factor")
    )
    df = F.broadcast(df.cache())
    return df


def transform_market(df, mapping):
    """Market tarafı: /Kg filtrele, mapping ile join, product_canonical türet."""
    return (
        df
        .filter(F.lower(F.col("unit_price_str")).rlike(r"/\s*kg\s*$"))
        .filter((F.col("discount") == False) | F.col("discount").isNull())  # noqa: E712
        .filter(F.col("unit_price_value").isNotNull() & (F.col("unit_price_value") > 0))
        .withColumn("city_norm", normalize_city_expr(F.col("city")))
        .join(
            mapping.select(
                F.col("market_product").alias("_mkt_product"),
                F.col("product_canonical").alias("_canon"),
                F.col("unit_conversion_factor").alias("_uconv"),
            ),
            F.col("product_name") == F.col("_mkt_product"),
            "inner",  # mapping'de olmayanlar dışarı
        )
        .withColumn(
            "market_price_per_kg",
            F.col("unit_price_value") * F.coalesce(F.col("_uconv"), F.lit(1.0)),
        )
        .select(
            F.col("date"),
            F.col("city_norm").alias("city"),
            F.col("_canon").alias("product_canonical"),
            F.col("market_name"),
            F.col("market_price_per_kg"),
            F.col("source_type").alias("market_source_type"),
        )
    )


def transform_hal(df, mapping):
    """Hal tarafı: mapping üzerinden product_canonical türet."""
    # Mapping'de aynı hal_product için birden fazla market_product satırı olabilir;
    # bizim için hal_product → product_canonical mapping'i tek satır olmalı
    hal_map = (
        mapping
        .groupBy("hal_product")
        .agg(F.first("product_canonical").alias("product_canonical"))
    )

    return (
        df
        .filter(F.col("price_avg").isNotNull() & (F.col("price_avg") > 0))
        .withColumn("city_norm", normalize_city_expr(F.col("city")))
        .join(
            hal_map,
            F.col("product_name") == F.col("hal_product"),
            "inner",
        )
        .select(
            F.col("date"),
            F.col("city_norm").alias("city"),
            F.col("product_canonical"),
            F.col("price_avg").alias("hal_price_per_kg"),
            F.col("source_type").alias("hal_source_type"),
        )
    )


def join_market_hal(market_df, hal_df):
    """(date, city, product_canonical) anahtarında join; market günlük ortalamaya iner."""
    # Market: aynı (date, city, product, market_name) için unique olabilir ama
    # depot bazlı satırlar olduğu için ortalama alıyoruz
    market_agg = (
        market_df
        .groupBy("date", "city", "product_canonical", "market_name", "market_source_type")
        .agg(F.avg("market_price_per_kg").alias("market_price_per_kg"))
    )

    hal_agg = (
        hal_df
        .groupBy("date", "city", "product_canonical", "hal_source_type")
        .agg(F.avg("hal_price_per_kg").alias("hal_price_per_kg"))
    )

    joined = (
        market_agg
        .join(hal_agg, ["date", "city", "product_canonical"], "full_outer")
        .withColumn("margin_abs", F.col("market_price_per_kg") - F.col("hal_price_per_kg"))
        .withColumn(
            "margin_pct",
            F.when(
                F.col("hal_price_per_kg").isNotNull() & (F.col("hal_price_per_kg") > 0),
                (F.col("margin_abs") / F.col("hal_price_per_kg")) * 100,
            ),
        )
        .withColumn("year", F.year(F.col("date")))
        .withColumn("month", F.month(F.col("date")))
        .select(
            "date", "year", "month", "city", "product_canonical",
            "market_name", "market_price_per_kg", "hal_price_per_kg",
            "margin_abs", "margin_pct",
            "hal_source_type", "market_source_type",
        )
    )
    return joined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None,
                        help="YYYY-MM-DD; default: tüm Silver")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--debug-day", type=str, default=None,
                        help="Tek gün için çalıştır, write yapma, show göster")
    parser.add_argument("--mode", choices=("overwrite", "append"), default="overwrite")
    args = parser.parse_args()

    spark = get_spark_session("silver_joined")
    spark.conf.set("spark.sql.shuffle.partitions", "200")

    mapping = read_mapping(spark)
    n_mapping = mapping.count()
    print(f"Mapping satırı (confidence in {VALID_CONFIDENCE}): {n_mapping}")
    if n_mapping == 0:
        print("UYARI: Mapping boş. Önce hal_market_mapping.csv'yi doldurun.", file=sys.stderr)
        sys.exit(1)

    market = spark.read.parquet(SILVER_MARKET)
    hal = spark.read.parquet(SILVER_HAL)

    if args.debug_day:
        market = market.filter(F.col("date") == args.debug_day)
        hal = hal.filter(F.col("date") == args.debug_day)
    else:
        if args.start_date:
            market = market.filter(F.col("date") >= args.start_date)
            hal = hal.filter(F.col("date") >= args.start_date)
        if args.end_date:
            market = market.filter(F.col("date") <= args.end_date)
            hal = hal.filter(F.col("date") <= args.end_date)

    market_t = transform_market(market, mapping)
    hal_t = transform_hal(hal, mapping)
    joined = join_market_hal(market_t, hal_t)

    print("\n=== Çıktı schema ===")
    joined.printSchema()

    if args.debug_day:
        n = joined.count()
        print(f"\nDebug: {args.debug_day} → {n:,} satır")
        joined.show(20, truncate=False)
        print("\n=== margin_pct dolu olan satır sayısı ===")
        print(f"  {joined.filter(F.col('margin_pct').isNotNull()).count():,}")
    else:
        n = joined.count()
        print(f"\nToplam: {n:,} satır")
        (
            joined
            .write
            .mode(args.mode)
            .partitionBy("year", "month")
            .parquet(SILVER_OUT)
        )
        print(f"Yazıldı → {SILVER_OUT}")

    spark.stop()


if __name__ == "__main__":
    main()
