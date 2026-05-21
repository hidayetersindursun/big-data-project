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

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "silver"))   # utils.spark_session burada
sys.path.insert(0, os.path.join(_HERE, ".."))             # es.config bulunabilsin

import pandas as pd
from elasticsearch import helpers
from pyspark.sql import functions as F
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
    "gidaradar_macro_corr":             {"path": "macro_price_corr", "city_field": None},
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


def _row_to_clean_dict(row, city_field):
    d = row.asDict(recursive=True)
    # city_geo'yu lat/lon'dan inşa et (broadcast join sonrası)
    if city_field and d.get("lat") is not None and d.get("lon") is not None:
        d["city_geo"] = {"lat": float(d["lat"]), "lon": float(d["lon"])}
    for k in ("lat", "lon", "region"):
        d.pop(k, None)
    # None / NaN sanitize + datetime → ISO
    clean = {}
    for k, v in d.items():
        if v is None:
            clean[k] = None
        elif isinstance(v, float) and v != v:  # NaN
            clean[k] = None
        elif hasattr(v, "isoformat"):
            clean[k] = v.isoformat()
        else:
            clean[k] = v
    return clean


def push_index(spark, es, index_name, src, coords_pdf, dry_run):
    """Spark df'i streaming bulk indexle — toPandas() yok, RAM-safe."""
    path = f"{GOLD_BASE}/{src['path']}"
    print(f"\n=== {index_name} ←  {path} ===")
    try:
        df = spark.read.parquet(path)
    except Exception as e:
        print(f"  ATLANIYOR (parquet okunamadı: {e})")
        return
    n = df.count()
    print(f"  Spark satır: {n:,}")
    if n == 0:
        print("  ATLANIYOR (boş)")
        return

    city_field = src.get("city_field")
    if city_field and city_field in df.columns:
        coords_spark = spark.createDataFrame(coords_pdf)
        # right side'daki city'yi rename ki conflict olmasın
        coords_spark = coords_spark.withColumnRenamed("city", "_geo_city")
        df = df.join(
            F.broadcast(coords_spark),
            df[city_field] == coords_spark["_geo_city"],
            "left",
        ).drop("_geo_city")

    if dry_run:
        print(f"  [DRY] {n:,} satır bulk olarak yazılacaktı")
        df.show(2, truncate=False)
        return

    def yield_actions():
        for row in df.toLocalIterator():
            yield {"_index": index_name, "_source": _row_to_clean_dict(row, city_field)}

    success, errors = helpers.bulk(
        es, yield_actions(), chunk_size=ES_BULK_BATCH,
        raise_on_error=False, raise_on_exception=False,
    )
    print(f"  Bulk: {success}/{n} başarılı, hata: {len(errors) if isinstance(errors, list) else errors}")


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
