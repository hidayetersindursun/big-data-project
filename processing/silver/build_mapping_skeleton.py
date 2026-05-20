"""
Hal ↔ Market entity resolution için aday üretici.

Akış:
  1. Spark ile silver/hal_prices distinct(product_name, category) + COUNT(*)
  2. Spark ile silver/market_prices distinct(product_name, category) + COUNT(*)
     (sadece unit_price_str '%/Kg' olan satırlar — kg-eşdeğeri ürünler)
  3. Her hal ürünü için pre-filter:
       - hal urun adının ilk anlamlı kelimesi (örn. DOMATES)
       - market title'larında bu kelimeyi içerenler aday
  4. Çıktı: lookups/hal_market_candidates.json
       {hal_product: {"hal_count": N, "candidates": [{"market_product": ..., "market_count": ...}, ...]}}

Bu dosya Haiku'ya gönderilmeden önce çağrı sayısını çok azaltır — full cross-product yerine sadece
kelime-overlap olan adaylar.

Kullanım:
  python processing/silver/build_mapping_skeleton.py
  python processing/silver/build_mapping_skeleton.py --top-candidates 20 --min-hal-count 5
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_HAL = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"
SILVER_MARKET = f"{_S3_PREFIX}://s3-bbuckett/silver/market_prices"

LOOKUP_DIR = Path(__file__).resolve().parent / "lookups"
OUT_FILE = LOOKUP_DIR / "hal_market_candidates.json"

# Pre-filter için Türkçe karakter çevirisi
_TR_TRANSLATE = str.maketrans("çğıiİöşüÇĞIİÖŞÜ", "cgiiiosuCGIIOSU")
_STOPWORDS = {"adet", "kg", "gr", "gram", "lt", "ml", "paket", "kutu", "tane", "torba"}


def normalize_word(s: str) -> str:
    if not s:
        return ""
    return s.lower().translate(_TR_TRANSLATE)


def first_token(name: str) -> str:
    """Ürün adının ilk anlamlı kelimesini al (stopwords hariç)."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-candidates", type=int, default=15,
                        help="Her hal ürünü için maks aday sayısı (default: 15)")
    parser.add_argument("--min-hal-count", type=int, default=3,
                        help="Bu sayının altındaki hal ürünleri atlanır (default: 3)")
    parser.add_argument("--out", type=str, default=str(OUT_FILE))
    args = parser.parse_args()

    LOOKUP_DIR.mkdir(parents=True, exist_ok=True)

    spark = get_spark_session("build_mapping_skeleton")

    print("=== silver/hal_prices distinct ===")
    hal_df = (
        spark.read.parquet(SILVER_HAL)
        .groupBy("product_name", "category")
        .agg(F.count("*").alias("hal_count"))
        .filter(F.col("hal_count") >= args.min_hal_count)
        .orderBy(F.col("hal_count").desc())
    )
    hal_rows = hal_df.collect()
    print(f"  Hal distinct urun: {len(hal_rows)}  (>={args.min_hal_count} kayıt)")

    print("\n=== silver/market_prices distinct (/Kg only) ===")
    mkt_df = (
        spark.read.parquet(SILVER_MARKET)
        .filter(F.lower(F.col("unit_price_str")).rlike(r"/\s*kg\s*$"))
        .groupBy("product_name", "category")
        .agg(F.count("*").alias("market_count"))
        .orderBy(F.col("market_count").desc())
    )
    mkt_rows = mkt_df.collect()
    print(f"  Market distinct urun (/Kg): {len(mkt_rows)}")

    # Driver tarafında pre-filter (data küçük, ~1500 hal × ~2000 market = 3M comparison)
    market_index = []
    for r in mkt_rows:
        name = r["product_name"]
        market_index.append({
            "name": name,
            "category": r["category"],
            "count": r["market_count"],
            "tokens": all_tokens(name),
            "first": first_token(name),
        })

    print("\n=== Aday eşleştirme (pre-filter) ===")
    out = {}
    for r in hal_rows:
        hal_name = r["product_name"]
        hal_first = first_token(hal_name)
        hal_tokens = all_tokens(hal_name)
        if not hal_first:
            continue

        candidates = []
        for m in market_index:
            # Heuristic: ilk-kelime eşleşmesi OR token overlap >= 1
            if hal_first in m["tokens"] or m["first"] in hal_tokens:
                overlap = len(hal_tokens & m["tokens"])
                candidates.append({
                    "market_product": m["name"],
                    "market_category": m["category"],
                    "market_count": m["count"],
                    "token_overlap": overlap,
                })

        # Aday sayısına göre sırala: önce token overlap, sonra market_count
        candidates.sort(key=lambda c: (-c["token_overlap"], -c["market_count"]))
        candidates = candidates[:args.top_candidates]

        out[hal_name] = {
            "hal_category": r["category"],
            "hal_count": r["hal_count"],
            "candidates": candidates,
        }

    # Hal ürünlerini hacme göre sırala (CSV'de Pareto görünür)
    out_sorted = dict(sorted(out.items(), key=lambda kv: -kv[1]["hal_count"]))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_sorted, f, ensure_ascii=False, indent=2)

    no_cand = sum(1 for v in out.values() if not v["candidates"])
    avg_cand = sum(len(v["candidates"]) for v in out.values()) / max(len(out), 1)
    print(f"  Toplam hal ürün     : {len(out)}")
    print(f"  Aday bulunamayan    : {no_cand}")
    print(f"  Ortalama aday/ürün  : {avg_cand:.1f}")
    print(f"  Yazıldı             : {args.out}")

    spark.stop()


if __name__ == "__main__":
    main()
