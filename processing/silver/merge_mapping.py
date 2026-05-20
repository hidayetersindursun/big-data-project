"""
Haiku subagent chunk çıktılarını (lookups/_chunks/mapping_*.csv) birleştirir.

Çıktı:
  lookups/hal_market_mapping_draft.csv  → tüm satırlar (reject dahil), manuel review için
  lookups/hal_market_mapping.csv        → sadece confidence in (exact, kg_equivalent),
                                            silver_joined.py'ın okuduğu üretim CSV'si

Kullanım:
  python processing/silver/merge_mapping.py
  python processing/silver/merge_mapping.py --include-weak   # weak'leri de production'a kat
"""

import argparse
import glob
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd


def clean_slug(s: str) -> str:
    """Canonical slug'ı normalize et: Türkçe/combining karakter → ascii, lowercase, _."""
    if not isinstance(s, str):
        return s
    # Türkçe özel harfler
    s = s.translate(str.maketrans("çğıİöşüÇĞIÖŞÜ", "cgiiosuCGIOSU"))
    # combining karakterleri (örn i + U+0307) ayrıştırıp at
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

LOOKUP_DIR = Path(__file__).resolve().parent / "lookups"
CHUNK_DIR = LOOKUP_DIR / "_chunks"
DRAFT_OUT = LOOKUP_DIR / "hal_market_mapping_draft.csv"
PROD_OUT = LOOKUP_DIR / "hal_market_mapping.csv"

PROD_CONFIDENCE = ["exact", "kg_equivalent"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-weak", action="store_true",
                        help="weak eşleşmeleri de production CSV'ye dahil et")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    files = sorted(glob.glob(str(CHUNK_DIR / "mapping_*.csv")))
    if not files:
        print(f"HATA: {CHUNK_DIR} altında mapping_*.csv yok.", file=sys.stderr)
        sys.exit(1)

    dfs = []
    for f in files:
        d = pd.read_csv(f)
        dfs.append(d)
        print(f"  {Path(f).name}: {len(d)} satır")

    df = pd.concat(dfs, ignore_index=True)

    # Temizlik: boş hal_product / market_product satırlarını at
    df = df.dropna(subset=["hal_product", "market_product", "confidence"])
    df["confidence"] = df["confidence"].str.strip().str.lower()
    # Tam yinelenen satırları kaldır
    df = df.drop_duplicates(subset=["hal_product", "market_product"])

    df.to_csv(DRAFT_OUT, index=False, encoding="utf-8")
    print(f"\nDraft yazıldı → {DRAFT_OUT}  ({len(df)} satır)")
    print("confidence dağılımı:")
    print(df["confidence"].value_counts().to_string())

    keep = PROD_CONFIDENCE + (["weak"] if args.include_weak else [])
    prod = df[df["confidence"].isin(keep)].copy()

    # Slug temizliği: combining char / Türkçe karakter → ascii (join tutarlılığı)
    prod["product_canonical"] = prod["product_canonical"].map(clean_slug)

    # Canonical tekleştirme: bir hal_product birden fazla canonical'a dağılmış olabilir
    # (subagent'lar varyetelere ayrı canonical verince). silver_joined'da hal tarafı
    # F.first(canonical), market tarafı satır-bazlı canonical alır — uyumsuzluk join'i
    # bozar. Her hal_product'ın TÜM satırlarını en sık görülen canonical'a sabitle.
    canon_map = (
        prod.groupby("hal_product")["product_canonical"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
    )
    multi = (prod.groupby("hal_product")["product_canonical"].nunique() > 1).sum()
    prod["product_canonical"] = prod["hal_product"].map(canon_map)
    print(f"\nCanonical tekleştirme: {multi} hal ürününde çoklu canonical düzeltildi")

    prod.to_csv(PROD_OUT, index=False, encoding="utf-8")
    print(f"Production yazıldı → {PROD_OUT}  ({len(prod)} satır)")
    print(f"  distinct hal_product      : {prod['hal_product'].nunique()}")
    print(f"  distinct product_canonical: {prod['product_canonical'].nunique()}")


if __name__ == "__main__":
    main()
