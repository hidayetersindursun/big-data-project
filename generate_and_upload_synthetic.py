"""
Sentetik market verisi üretip direkt S3 Bronze'a Parquet olarak yükler.
Yerel JSONL dosyası oluşturmaz.

Kullanım:
    python generate_and_upload_synthetic.py --bucket s3-bbuckett --days 7
    python generate_and_upload_synthetic.py --bucket s3-bbuckett --days 7 --dry-run
    python generate_and_upload_synthetic.py --bucket s3-bbuckett --days 365 --source-date 2026-05-17
"""

import argparse
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import boto3
import pandas as pd

PROJECT_ROOT = Path(__file__).parent
MARKET_DATA = PROJECT_ROOT / "ingestion" / "market" / "data"
TCMB_DATA = PROJECT_ROOT / "ingestion" / "tcmb" / "data"

DAILY_VARIANCE = 0.05

# Kaynak: gktd.org mevsim rehberi — hangi aylarda ucuz (arz yüksek)
# Her ürün grubu için 12 aylık çarpan (1=Ocak, 12=Aralık)
# Mevsimi olan ay → 0.80 (ucuz), olmayan ay → 1.25 (pahalı), geçiş → 1.00
def _profile(cheap_months: list[int]) -> dict[int, float]:
    """Mevsim aylarında 0.80, diğerlerinde 1.25, geçişte 1.00 çarpan üretir."""
    cheap = set(cheap_months)
    profile = {}
    for m in range(1, 13):
        prev_m = 12 if m == 1 else m - 1
        next_m = 1 if m == 12 else m + 1
        if m in cheap:
            profile[m] = 0.80
        elif prev_m in cheap or next_m in cheap:
            profile[m] = 1.00  # geçiş ayı
        else:
            profile[m] = 1.25
    return profile

# Ürün adında geçen anahtar kelime → mevsim profili
# Daha spesifik eşleşmeler önce gelir (domates, biber önce; genel sebze sonda)
PRODUCT_SEASONAL_PROFILES: list[tuple[list[str], dict[int, float]]] = [
    # Yazlık sebzeler
    (["domates"],                    _profile([7, 8, 9, 10])),
    (["salatalık", "hıyar"],         _profile([6, 7, 8])),
    (["patlıcan"],                   _profile([6, 7, 8, 9])),
    (["kabak"],                      _profile([6, 7, 8, 9])),
    (["biber", "dolmalık", "sivri"], _profile([7, 8, 9, 10])),
    (["bamya"],                      _profile([7, 8])),
    (["mısır"],                      _profile([8, 9])),
    (["bezelye"],                    _profile([4, 5, 6])),
    (["bakla"],                      _profile([4, 5])),
    (["enginar"],                    _profile([3, 4, 5])),
    # Kışlık sebzeler
    (["ıspanak", "ispanak"],         _profile([1, 2, 3, 11, 12])),
    (["lahana"],                     _profile([1, 2, 11, 12])),
    (["brokoli", "karnabahar"],      _profile([1, 2, 3, 10, 11, 12])),
    (["havuç"],                      _profile([1, 2, 3, 4, 10, 11, 12])),
    (["pırasa"],                     _profile([1, 2, 3, 12])),
    (["balkabağı", "bal kabağı"],    _profile([1, 2, 10, 11, 12])),
    (["kereviz"],                    _profile([1, 2, 3, 11, 12])),
    # Narenciye
    (["portakal"],                   _profile([1, 2, 3, 12])),
    (["mandalina"],                  _profile([1, 2, 11, 12])),
    (["greyfurt"],                   _profile([1, 10, 11, 12])),
    (["limon"],                      _profile([3, 12])),
    (["nar"],                        _profile([1, 2, 12])),
    # İlkbahar meyveleri
    (["çilek"],                      _profile([4, 5, 6])),
    (["kiraz"],                      _profile([6, 7])),
    (["kayısı"],                     _profile([6, 7, 8])),
    (["şeftali"],                    _profile([6, 7, 8])),
    (["erik"],                       _profile([5, 6, 7, 8])),
    # Yaz meyveleri
    (["karpuz"],                     _profile([7, 8, 9])),
    (["kavun"],                      _profile([7, 8, 9])),
    (["üzüm"],                       _profile([7, 8, 9])),
    (["vişne"],                      _profile([7, 8])),
    (["incir"],                      _profile([8, 9, 10])),
    # Sonbahar/kış meyveleri
    (["elma"],                       _profile([1, 2, 3, 10, 11, 12])),
    (["armut"],                      _profile([1, 2, 10, 11, 12])),
    (["ayva"],                       _profile([1, 2, 11, 12])),
    (["kestane"],                    _profile([1, 2, 10, 11])),
    # Görece stabil
    (["muz"],                        _profile([3, 4, 5, 6, 7, 8, 9, 10, 11, 12])),
]

# Ürün adında eşleşme yoksa fallback
SEASONAL_DEFAULT = {
    1: 1.20, 2: 1.15, 3: 1.05,
    4: 0.95, 5: 0.90, 6: 0.85,
    7: 0.82, 8: 0.83, 9: 0.88,
    10: 0.95, 11: 1.08, 12: 1.18,
}


def get_seasonal_profile(title: str) -> dict[int, float]:
    """Ürün başlığına göre mevsim profili döndürür."""
    title_lower = title.lower()
    for keywords, profile in PRODUCT_SEASONAL_PROFILES:
        if any(kw in title_lower for kw in keywords):
            return profile
    return SEASONAL_DEFAULT


def load_tufe() -> dict[int, float]:
    """Taze meyve-sebze YoY TÜFE'sini yıl → ortalama oran olarak döndürür."""
    # Önce spesifik seriyi dene, yoksa genel gıda serisiyle fallback
    for fname in ("tufe_taze_meyve_sebze_yoy.jsonl", "tufe_gida_alkolsuz_yoy.jsonl", "tufe_gida_yoy.jsonl"):
        path = TCMB_DATA / fname
        if not path.exists():
            continue
        from collections import defaultdict
        yearly = defaultdict(list)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    year = int(str(rec["date"]).split("-")[0])
                    val = rec.get("value")
                    if val is not None:
                        yearly[year].append(float(val) / 100)
                except (KeyError, ValueError, json.JSONDecodeError):
                    continue
        if yearly:
            print(f"  TÜFE serisi: {fname}")
            return {y: sum(v) / len(v) for y, v in yearly.items()}
    return {y: 0.30 for y in range(2020, 2027)}


def deflation_factor(base_date: date, target_date: date, inflation: dict) -> float:
    """base_date → target_date için fiyat çarpanı (target < base ise <1)."""
    if target_date >= base_date:
        return 1.0
    days_diff = (base_date - target_date).days
    # Günlük bileşik deflasyon: yıllık oranı güne böl
    factor = 1.0
    current = target_date
    while current < base_date:
        annual = inflation.get(current.year, 0.30)
        daily_rate = annual / 365
        factor *= (1 + daily_rate)
        current += timedelta(days=1)
        if (current - target_date).days > 400:
            # Uzun aralık için yaklaşım — tam gün döngüsü yerine yıl bazlı
            remaining_days = (base_date - current).days
            if remaining_days > 30:
                years_remaining = remaining_days / 365
                avg_annual = sum(
                    inflation.get(current.year + i, 0.30)
                    for i in range(int(years_remaining) + 1)
                ) / (int(years_remaining) + 1)
                factor *= (1 + avg_annual) ** years_remaining
                break
    return 1.0 / factor


def synthetic_price(orig: float, base_date: date, target_date: date,
                    inflation: dict, product_title: str, seed: int) -> float:
    df = deflation_factor(base_date, target_date, inflation)
    profile = get_seasonal_profile(product_title)
    seasonal_adj = profile[target_date.month] / profile[base_date.month]
    noise = 1.0 + random.Random(seed).uniform(-DAILY_VARIANCE, DAILY_VARIANCE)
    return round(max(orig * df * seasonal_adj * noise, 0.01), 2)


def flatten_record(rec: dict) -> list[dict]:
    depots = rec.pop("productDepotInfoList", [])
    cats = rec.pop("categories", [])
    rec["categories"] = ", ".join(cats) if cats else None
    if not depots:
        return [rec]
    return [{**rec, **d} for d in depots]


def load_base_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def apply_synthetic_to_records(preloaded: list[tuple[str, list[dict]]],
                               base_date: date, target_date: date,
                               inflation: dict,
                               _cache: dict = {}) -> pd.DataFrame:
    """Bellekteki kayıtlara hedef tarih için sentetik fiyat uygular."""
    # Deflasyon faktörü ay bazında cache'le (aynı ay için tekrar hesaplama)
    cache_key = (base_date, target_date.year, target_date.month)
    if cache_key not in _cache:
        _cache[cache_key] = deflation_factor(base_date, target_date, inflation)
    df_factor = _cache[cache_key]

    scraped_at = f"{target_date}T08:00:00"
    base_date_str = base_date.isoformat()
    index_time = f"{target_date.strftime('%d.%m.%Y')} 08:00"
    target_month = target_date.month
    target_date_iso = target_date.isoformat()

    rows = []
    for file_stem, records in preloaded:
        for i, rec in enumerate(records):
            product_title = rec.get("title", "")
            cats = rec.get("categories", [])
            cats_str = ", ".join(cats) if isinstance(cats, list) else (cats or "")

            profile = get_seasonal_profile(product_title)
            base_month = base_date.month
            seasonal_adj = profile[target_month] / profile[base_month]

            base_row = {
                k: v for k, v in rec.items()
                if k not in ("productDepotInfoList", "categories")
            }
            base_row["categories"] = cats_str
            base_row["_scraped_at"] = scraped_at
            base_row["_synthetic"] = True
            base_row["_base_date"] = base_date_str

            depots = rec.get("productDepotInfoList") or []
            if not depots:
                rows.append(base_row)
                continue

            for j, depot in enumerate(depots):
                orig = depot.get("price")
                new_depot = dict(depot)
                if orig is not None:
                    seed = hash((file_stem, target_date_iso, i, j)) & 0xFFFFFFFF
                    noise = 1.0 + random.Random(seed).uniform(-DAILY_VARIANCE, DAILY_VARIANCE)
                    new_p = round(max(orig * df_factor * seasonal_adj * noise, 0.01), 2)
                    new_depot["price"] = new_p
                    new_depot["unitPriceValue"] = new_p
                    new_depot["unitPrice"] = f"{new_p:.2f} ₺/Kg"
                    new_depot["indexTime"] = index_time
                rows.append({**base_row, **new_depot})

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def key_exists(s3, bucket: str, key: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def upload_parquet(df: pd.DataFrame, key: str, bucket: str, s3, dry_run: bool) -> int:
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    df.to_parquet(tmp_path, index=False, engine="pyarrow")
    size_kb = tmp_path.stat().st_size // 1024
    if not dry_run:
        s3.upload_file(str(tmp_path), bucket, key)
    tmp_path.unlink()
    return size_kb


def collect_base_files(source_date: str | None) -> list[tuple[Path, str]]:
    result = []
    for city_dir in MARKET_DATA.iterdir():
        if not city_dir.is_dir():
            continue
        date_dirs = sorted(d for d in city_dir.iterdir() if d.is_dir())
        if not date_dirs:
            continue
        if source_date:
            match = [d for d in date_dirs if d.name == source_date]
            base_dir = match[0] if match else date_dirs[-1]
        else:
            base_dir = date_dirs[-1]
        for jsonl in base_dir.glob("*.jsonl"):
            result.append((jsonl, base_dir.name))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--source-date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inflation = load_tufe()
    print(f"TÜFE yüklendi: {len(inflation)} yıl")

    base_files = collect_base_files(args.source_date)
    if not base_files:
        print("Baz dosya bulunamadı.")
        return

    base_date_str = args.source_date or max(bd for _, bd in base_files)
    base_date = date.fromisoformat(base_date_str)
    base_files = [(p, bd) for p, bd in base_files if bd == base_date_str]

    print(f"Baz tarih: {base_date_str} | {len(base_files)} dosya")
    print(f"Hedef: {base_date - timedelta(days=args.days)} -> {base_date - timedelta(days=1)}")
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}S3: s3://{args.bucket}/bronze/market/\n")

    # Tüm JSONL dosyalarını bir kez belleğe al
    print("Baz kayıtlar belleğe yükleniyor...", end=" ", flush=True)
    preloaded: list[tuple[str, list[dict]]] = []
    for jsonl_path, _ in base_files:
        records = load_base_jsonl(jsonl_path)
        if records:
            preloaded.append((jsonl_path.stem, records))
    print(f"{len(preloaded)} dosya yüklendi.")

    s3 = None if args.dry_run else boto3.client("s3")

    # Tüm günleri ay bazında grupla: {(year, month): [date, ...]}
    from collections import defaultdict
    month_groups: dict[tuple, list[date]] = defaultdict(list)
    for day_offset in range(1, args.days + 1):
        target_date = base_date - timedelta(days=day_offset)
        month_groups[(target_date.year, target_date.month)].append(target_date)

    from datetime import date as date_cls
    current_year, current_month = date_cls.today().year, date_cls.today().month

    for (year, month), days in sorted(month_groups.items()):
        y = f"{year:04d}"
        m = f"{month:02d}"
        # Cari ay (henüz bitmemiş) → günlük dosya; geçmiş aylar → aylık tek dosya
        is_current_month = (year == current_year and month == current_month)

        if is_current_month:
            for target_date in sorted(days):
                d = f"{target_date.day:02d}"
                key = f"bronze/market_synthetic/year={y}/month={m}/day={d}/part-0000.parquet"
                if not args.dry_run and key_exists(s3, args.bucket, key):
                    print(f"  ATILDI:   {target_date}  (zaten mevcut)")
                    continue
                df = apply_synthetic_to_records(preloaded, base_date, target_date, inflation)
                if df.empty:
                    continue
                day_kb = upload_parquet(df, key, args.bucket, s3, args.dry_run)
                tag = "[DRY-RUN] " if args.dry_run else "YÜKLENDI: "
                print(f"  {tag}{target_date}  {len(df):>8,} satır  {day_kb:>6} KB")
        else:
            key = f"bronze/market_synthetic/year={y}/month={m}/part-0000.parquet"
            if not args.dry_run and key_exists(s3, args.bucket, key):
                print(f"  ATILDI:   {y}-{m}  (zaten mevcut)")
                continue
            month_dfs = []
            for target_date in sorted(days):
                df = apply_synthetic_to_records(preloaded, base_date, target_date, inflation)
                if not df.empty:
                    month_dfs.append(df)
            if not month_dfs:
                continue
            merged = pd.concat(month_dfs, ignore_index=True)
            month_kb = upload_parquet(merged, key, args.bucket, s3, args.dry_run)
            tag = "[DRY-RUN] " if args.dry_run else "YÜKLENDI: "
            print(f"  {tag}{y}-{m}  {len(days)} gün  {len(merged):>8,} satır  {month_kb:>6} KB")

    print("\nTamamlandı.")


if __name__ == "__main__":
    main()
