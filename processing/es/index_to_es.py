"""
Gold parquet → Elasticsearch indexleme.

Akış:
  1. index_mappings.json'dan mappings'i oku.
  2. CLI flag --recreate: drop + create indexler.
  3. Her Gold tablosu için Spark ile parquet oku → toPandas()
     → (gerekirse) city_coords join → city_geo alanı ekle
     → elasticsearch.helpers.bulk ile push.

CLI:
  python processing/es/index_to_es.py                       # tüm indexler
  python processing/es/index_to_es.py --index gidaradar_daily_margin
  python processing/es/index_to_es.py --recreate            # önce drop+create
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from elasticsearch import helpers
from utils.spark_session import get_spark_session
from es.config import get_es_client, ES_BULK_BATCH

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
GOLD_BASE = f"{_S3_PREFIX}://s3-bbuckett/gold"

MAPPINGS_FILE = Path(__file__).resolve().parent / "index_mappings.json"
COORDS_FILE = Path(__file__).resolve().parent.parent / "silver" / "lookups" / "city_coords.csv"

# index_name → {gold_table_path, city_field_name (geo enrich için, varsa)}
INDEX_SOURCES = {
    "gidaradar_daily_margin":           {"path": "daily_margin", "city_field": "city"},
    "gidaradar_price_inequality_hal":   {"path": "price_inequality_hal", "city_field": None},
    "gidaradar_price_inequality_market":{"path": "price_inequality_market", "city_field": None},
    "gidaradar_rockets_feathers":       {"path": "rockets_feathers", "city_field": None},
    "gidaradar_shocks":                 {"path": "shock_propagation", "city_field": "city"},
    "gidaradar_pandemic_gap":           {"path": "pandemic_gap", "city_field": None},
    "gidaradar_news_corr":              {"path": "news_price_corr", "city_field": None},
    "gidaradar_forecast":               {"path": "price_forecast", "city_field": None},
}


def load_mappings():
    with open(MAPPINGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_city_coords():
    return pd.read_csv(COORDS_FILE)


def recreate_index(es, name, body):
    if es.indices.exists(index=name):
        print(f"  Dropping: {name}")
        es.indices.delete(index=name)
    print(f"  Creating: {name}")
    es.indices.create(index=name, **body)


def enrich_geo(pdf: pd.DataFrame, coords: pd.DataFrame, city_field: str) -> pd.DataFrame:
    """city kolonuna karşılık city_geo {lat, lon} alanı ekle."""
    df = pdf.merge(coords, left_on=city_field, right_on="city", how="left", suffixes=("", "_coord"))
    df["city_geo"] = df.apply(
        lambda r: {"lat": r["lat"], "lon": r["lon"]} if pd.notna(r.get("lat")) else None,
        axis=1,
    )
    # cleanup
    drop_cols = [c for c in ["lat", "lon", "region", "city_coord"] if c in df.columns]
    df = df.drop(columns=drop_cols)
    return df


def df_to_bulk_actions(df: pd.DataFrame, index_name: str):
    """DataFrame'i ES bulk action iterator'a çevir."""
    for record in df.to_dict(orient="records"):
        # NaN'leri None'a çevir (ES JSON serializer NaN sevmiyor)
        clean = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        # ISO date için pandas timestamp → string
        for k, v in clean.items():
            if hasattr(v, "isoformat"):
                clean[k] = v.isoformat()
        yield {
            "_index": index_name,
            "_source": clean,
        }


def push_index(spark, es, index_name, src, coords, dry_run):
    path = f"{GOLD_BASE}/{src['path']}"
    print(f"\n=== {index_name} ←  {path} ===")
    df = spark.read.parquet(path)
    n = df.count()
    print(f"  Spark satır: {n:,}")
    if n == 0:
        print("  ATLANIYOR (boş)")
        return

    pdf = df.toPandas()
    if src["city_field"] and src["city_field"] in pdf.columns:
        pdf = enrich_geo(pdf, coords, src["city_field"])

    if dry_run:
        print(f"  [DRY] {len(pdf):,} satır bulk olarak yazılacaktı")
        print(pdf.head(2))
        return

    actions = df_to_bulk_actions(pdf, index_name)
    success, errors = helpers.bulk(
        es, actions, chunk_size=ES_BULK_BATCH, raise_on_error=False, raise_on_exception=False
    )
    print(f"  Bulk: {success} başarılı, hata: {len(errors) if isinstance(errors, list) else errors}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=str, default=None,
                        help="Tek bir index push'la (default: tümü)")
    parser.add_argument("--recreate", action="store_true",
                        help="Index'i drop edip mappings'ten yeniden oluştur")
    parser.add_argument("--recreate-only", action="store_true",
                        help="Sadece index'leri oluştur, veri push'lama")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mappings = load_mappings()
    coords = load_city_coords()
    es = get_es_client()

    targets = [args.index] if args.index else list(INDEX_SOURCES.keys())

    if args.recreate or args.recreate_only:
        print("=== Index recreate ===")
        for name in targets:
            if name not in mappings:
                print(f"  UYARI: {name} mappings'te yok")
                continue
            recreate_index(es, name, mappings[name])
        if args.recreate_only:
            return

    spark = get_spark_session("index_to_es")

    for name in targets:
        src = INDEX_SOURCES.get(name)
        if not src:
            print(f"  UYARI: {name} INDEX_SOURCES'ta yok")
            continue
        try:
            push_index(spark, es, name, src, coords, args.dry_run)
        except Exception as e:
            print(f"  HATA [{name}]: {e}")

    spark.stop()


if __name__ == "__main__":
    main()
