"""
Hal ↔ Market entity resolution için aday üretici.

İki mod:
  --source silver  : silver/hal_prices + silver/market_prices'tan oku (Spark)
  --source bronze  : bronze/hal_all + bronze/market(+_synthetic) direkt boto3+pandas ile oku
                     (Silver yokken kullanışlı; çok daha hızlı)

Akış:
  1. Distinct (hal urun, kategori) + COUNT
  2. Distinct (market title, kategori) + COUNT (sadece unit_price '/Kg' olanlar)
  3. Pre-filter aday: hal urun adının ilk anlamlı kelimesi market title'larıyla eşleşenler
  4. Çıktı: lookups/hal_market_candidates.json
       {hal_product: {"hal_count": N, "candidates": [{"market_product": ..., "market_count": ...}, ...]}}

Kullanım:
  python processing/silver/build_mapping_skeleton.py --source bronze
  python processing/silver/build_mapping_skeleton.py --source silver
  python processing/silver/build_mapping_skeleton.py --source bronze --top-candidates 20 --min-hal-count 5
"""

import argparse
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

LOOKUP_DIR = Path(__file__).resolve().parent / "lookups"
OUT_FILE = LOOKUP_DIR / "hal_market_candidates.json"

# Pre-filter için Türkçe karakter çevirisi
_TR_TRANSLATE = str.maketrans("çğıiİöşüÇĞIİÖŞÜ", "cgiiiosuCGIIOSU")
_STOPWORDS = {"adet", "kg", "gr", "gram", "lt", "ml", "paket", "kutu", "tane", "torba",
              "ekonomik", "yerli", "tabak"}


def normalize_word(s: str) -> str:
    if not s:
        return ""
    return s.lower().translate(_TR_TRANSLATE)


def first_token(name: str) -> str:
    if not name:
        return ""
    tokens = re.findall(r"\w+", normalize_word(name))
    for tok in tokens:
        if len(tok) >= 3 and tok not in _STOPWORDS and not tok.isdigit():
            return tok
    return tokens[0] if tokens else ""


def all_tokens(name: str) -> set:
    if not name:
        return set()
    tokens = re.findall(r"\w+", normalize_word(name))
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS and not t.isdigit()}


def read_distinct_from_bronze():
    """Bronze'dan distinct hal + market ürün üret. Spark gerekmez."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    import boto3
    import pandas as pd

    s3 = boto3.client("s3", region_name="eu-central-1")
    bucket = "s3-bbuckett"

    # --- Hal: bronze/hal_all (en yeni 12 ay yeterli — ürün listesi uniform) ---
    print("Bronze hal_all listeleniyor...")
    paginator = s3.get_paginator("list_objects_v2")
    hal_keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix="bronze/hal_all/year=2024/"):
        hal_keys.extend(o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet"))
    for page in paginator.paginate(Bucket=bucket, Prefix="bronze/hal_all/year=2025/"):
        hal_keys.extend(o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet"))
    print(f"  {len(hal_keys)} parquet dosya okunacak")

    hal_counts = Counter()
    hal_categories = {}
    for k in hal_keys:
        obj = s3.get_object(Bucket=bucket, Key=k)
        df = pd.read_parquet(io.BytesIO(obj["Body"].read()), columns=["urun", "kategori"])
        for urun, kat in zip(df["urun"], df["kategori"]):
            if pd.isna(urun):
                continue
            # initcap(lower)
            name = str(urun).strip().lower().title()
            hal_counts[name] += 1
            if name not in hal_categories and pd.notna(kat):
                hal_categories[name] = kat
    print(f"  Hal distinct urun: {len(hal_counts)}")

    # --- Market: bronze/market son 7 gün + bronze/market_synthetic 2 örnek ay ---
    print("Bronze market listeleniyor...")
    market_keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix="bronze/market/"):
        market_keys.extend(o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet"))
    # Synthetic'ten 2 ay
    synth_keys = []
    for prefix in ["bronze/market_synthetic/year=2024/month=06/",
                   "bronze/market_synthetic/year=2025/month=12/"]:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            synth_keys.extend(o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet"))
    market_keys.extend(synth_keys)
    print(f"  {len(market_keys)} parquet dosya okunacak")

    market_counts = Counter()
    market_categories = {}
    for k in market_keys:
        obj = s3.get_object(Bucket=bucket, Key=k)
        df = pd.read_parquet(io.BytesIO(obj["Body"].read()),
                             columns=["title", "main_category", "unitPrice"])
        # sadece /Kg ile bitenler
        mask = df["unitPrice"].astype(str).str.lower().str.rstrip().str.endswith("/kg")
        df = df.loc[mask]
        for title, cat in zip(df["title"], df["main_category"]):
            if pd.isna(title):
                continue
            t = str(title).strip()
            market_counts[t] += 1
            if t not in market_categories and pd.notna(cat):
                market_categories[t] = cat
    print(f"  Market distinct title (/Kg): {len(market_counts)}")

    return hal_counts, hal_categories, market_counts, market_categories


def read_distinct_from_silver():
    """Silver'dan oku (Spark)."""
    import os
    os.environ.setdefault("PYSPARK_SUBMIT_ARGS",
                          "--packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 pyspark-shell")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from pyspark.sql import functions as F
    from utils.spark_session import get_spark_session

    _S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
    SILVER_HAL = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"
    SILVER_MARKET = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"

    spark = get_spark_session("build_mapping_skeleton")

    hal_df = (
        spark.read.parquet(SILVER_HAL)
        .groupBy("product_name", "category")
        .agg(F.count("*").alias("c"))
        .orderBy(F.col("c").desc())
    )
    hal_counts = Counter()
    hal_categories = {}
    for r in hal_df.collect():
        hal_counts[r["product_name"]] = r["c"]
        if r["category"]:
            hal_categories[r["product_name"]] = r["category"]

    mkt_df = (
        spark.read.parquet(SILVER_MARKET)
        .filter(F.lower(F.col("unit_price_str")).rlike(r"/\s*kg\s*$"))
        .groupBy("product_name", "category")
        .agg(F.count("*").alias("c"))
    )
    market_counts = Counter()
    market_categories = {}
    for r in mkt_df.collect():
        market_counts[r["product_name"]] = r["c"]
        if r["category"]:
            market_categories[r["product_name"]] = r["category"]

    spark.stop()
    return hal_counts, hal_categories, market_counts, market_categories


def build_candidates(hal_counts, hal_categories, market_counts, market_categories,
                     top_candidates, min_hal_count):
    market_index = []
    for name, cnt in market_counts.items():
        market_index.append({
            "name": name,
            "category": market_categories.get(name),
            "count": cnt,
            "tokens": all_tokens(name),
            "first": first_token(name),
        })

    out = {}
    for hal_name, hal_cnt in hal_counts.items():
        if hal_cnt < min_hal_count:
            continue
        hal_first = first_token(hal_name)
        hal_tokens = all_tokens(hal_name)
        if not hal_first:
            continue

        candidates = []
        for m in market_index:
            if hal_first in m["tokens"] or m["first"] in hal_tokens:
                overlap = len(hal_tokens & m["tokens"])
                candidates.append({
                    "market_product": m["name"],
                    "market_category": m["category"],
                    "market_count": m["count"],
                    "token_overlap": overlap,
                })

        candidates.sort(key=lambda c: (-c["token_overlap"], -c["market_count"]))
        candidates = candidates[:top_candidates]

        out[hal_name] = {
            "hal_category": hal_categories.get(hal_name),
            "hal_count": hal_cnt,
            "candidates": candidates,
        }

    return dict(sorted(out.items(), key=lambda kv: -kv[1]["hal_count"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("bronze", "silver"), default="bronze",
                        help="Bronze direkt okuma (hızlı) veya Silver Spark (default: bronze)")
    parser.add_argument("--top-candidates", type=int, default=15)
    parser.add_argument("--min-hal-count", type=int, default=3)
    parser.add_argument("--out", type=str, default=str(OUT_FILE))
    args = parser.parse_args()

    LOOKUP_DIR.mkdir(parents=True, exist_ok=True)

    if args.source == "bronze":
        hal_c, hal_cat, mkt_c, mkt_cat = read_distinct_from_bronze()
    else:
        hal_c, hal_cat, mkt_c, mkt_cat = read_distinct_from_silver()

    print("\nAday eşleştirme (pre-filter)...")
    out = build_candidates(hal_c, hal_cat, mkt_c, mkt_cat,
                           args.top_candidates, args.min_hal_count)

    no_cand = sum(1 for v in out.values() if not v["candidates"])
    avg_cand = sum(len(v["candidates"]) for v in out.values()) / max(len(out), 1)
    print(f"  Toplam hal ürün     : {len(out)}")
    print(f"  Aday bulunamayan    : {no_cand}")
    print(f"  Ortalama aday/ürün  : {avg_cand:.1f}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  Yazıldı             : {args.out}")


if __name__ == "__main__":
    main()
