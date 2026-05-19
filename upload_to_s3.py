"""
Lokal veriyi Hive-style Parquet'e çevirip S3 Bronze layer'a yükler.

Kullanım:
    python upload_to_s3.py --bucket s3-bbuckett
    python upload_to_s3.py --bucket s3-bbuckett --dry-run
    python upload_to_s3.py --bucket s3-bbuckett --source market

S3 yapısı (Hive-style, Spark partition pruning için):
    bronze/market/year=YYYY/month=MM/day=DD/part-0000.parquet
    bronze/hal_istanbul/year=YYYY/month=MM/day=DD/part-0000.parquet
    bronze/hal_harman/year=YYYY/month=MM/day=DD/part-0000.parquet
    bronze/gdelt/year=YYYY/month=MM/day=DD/part-0000.parquet
    bronze/akaryakit/year=YYYY/month=MM/day=DD/part-0000.parquet
    bronze/epias/{dataset}/year=YYYY/month=MM/part-0000.parquet
    bronze/commodities/year=YYYY/month=MM/part-0000.parquet
    bronze/tcmb/{series}/year=YYYY/month=MM/part-0000.parquet
    bronze/weather/year=YYYY/month=MM/part-0000.parquet
"""

import argparse
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import boto3
import pandas as pd
from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).parent
INGESTION_DIR = PROJECT_ROOT / "ingestion"

SOURCES = [
    "market", "hal_istanbul", "hal_harman", "hal_all", "gdelt",
    "akaryakit", "epias", "commodities", "tcmb", "weather",
]

SKIP_FILES = {"state.json", "geocode_cache.json", "osm_markets_tr.json"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def key_exists(key: str, bucket: str, s3_client, dry_run: bool) -> bool:
    if dry_run or s3_client is None:
        return False
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def upload_parquet(df: pd.DataFrame, key: str, bucket: str, s3_client, dry_run: bool) -> int:
    """DataFrame → geçici Parquet → S3. Boyut (KB) döndürür."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    df.to_parquet(tmp_path, index=False, engine="pyarrow")
    size_kb = tmp_path.stat().st_size // 1024
    if not dry_run and s3_client:
        s3_client.upload_file(str(tmp_path), bucket, key)
    tmp_path.unlink(missing_ok=True)
    return size_kb


def log(dry_run: bool, msg: str):
    prefix = "[DRY] " if dry_run else "OK:   "
    print(f"    {prefix}{msg}")


def hive_day(date_str: str) -> tuple[str, str, str] | None:
    """'YYYY-MM-DD' → ('YYYY', 'MM', 'DD'). Başarısız olursa None."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def hive_month(date_str: str) -> tuple[str, str] | None:
    """'YYYY-MM-DD' veya 'DD-MM-YYYY' veya 'YYYY-MM' → ('YYYY', 'MM')."""
    s = str(date_str).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s[:4], s[5:7]
    if re.match(r"^\d{2}-\d{2}-\d{4}$", s):
        return s[6:], s[3:5]
    if re.match(r"^\d{4}-\d{2}$", s):
        return s[:4], s[5:7]
    return None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _flatten_market(record: dict) -> list[dict]:
    depots = record.pop("productDepotInfoList", [])
    cats = record.pop("categories", [])
    record["categories"] = ", ".join(cats) if cats else None
    if not depots:
        return [record]
    return [{**record, **d} for d in depots]


def _flatten_gdelt(record: dict) -> dict:
    themes = record.get("themes", [])
    record["themes"] = ", ".join(themes) if isinstance(themes, list) else themes
    return record


def load_jsonl(path: Path, source: str) -> pd.DataFrame:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if source == "market":
                    records.extend(_flatten_market(rec))
                elif source == "gdelt":
                    records.append(_flatten_gdelt(rec))
                else:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(records) if records else pd.DataFrame()


def load_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "cp1254", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.DataFrame()


def load_xls(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="xlrd")


# ---------------------------------------------------------------------------
# Source processors  (her biri tuple[orig_kb, parquet_kb] döndürür)
# ---------------------------------------------------------------------------

def process_market(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {city_district}/{YYYY-MM-DD}/{category}.jsonl
    S3:    bronze/market/year=YYYY/month=MM/day=DD/part-0000.parquet
    Aynı güne ait tüm şehir+kategori dosyaları tek Parquet'e birleştirilir.
    """
    date_groups: dict[str, list[Path]] = defaultdict(list)
    for p in source_dir.rglob("*.jsonl"):
        if p.name in SKIP_FILES:
            continue
        date_str = p.parent.name  # YYYY-MM-DD
        if hive_day(date_str):
            date_groups[date_str].append(p)

    total_orig = total_parquet = 0
    for date_str, files in sorted(date_groups.items()):
        y, m, d = hive_day(date_str)
        key = f"bronze/market/year={y}/month={m}/day={d}/part-0000.parquet"
        if key_exists(key, bucket, s3_client, dry_run):
            print(f"    ATILDI: market {date_str}")
            continue
        dfs, orig_kb = [], 0
        for f in files:
            df = load_jsonl(f, "market")
            if not df.empty:
                dfs.append(df)
            orig_kb += f.stat().st_size // 1024
        if not dfs:
            continue
        merged = pd.concat(dfs, ignore_index=True)
        pk = upload_parquet(merged, key, bucket, s3_client, dry_run)
        total_orig += orig_kb
        total_parquet += pk
        log(dry_run, f"market {date_str} ({len(files)} dosya, {orig_kb}KB→{pk}KB)")
    return total_orig, total_parquet


def process_hal(source_name: str, source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {source}/istanbul_hal_fiyat_DD_MM_YYYY.csv
    S3:    bronze/{source_name}/year=YYYY/month=MM/day=DD/part-0000.parquet
    """
    total_orig = total_parquet = 0
    for csv_path in source_dir.rglob("*.csv"):
        # dosya adından tarihi çek: *_DD_MM_YYYY.csv
        m = re.search(r"_(\d{2})_(\d{2})_(\d{4})\.csv$", csv_path.name)
        if not m:
            print(f"    ATILDI: {csv_path.name} (tarih parse edilemedi)")
            continue
        d, mo, y = m.group(1), m.group(2), m.group(3)
        key = f"bronze/{source_name}/year={y}/month={mo}/day={d}/part-0000.parquet"
        if key_exists(key, bucket, s3_client, dry_run):
            print(f"    ATILDI: {source_name} {y}-{mo}-{d}")
            continue
        df = load_csv(csv_path)
        if df.empty:
            continue
        orig_kb = csv_path.stat().st_size // 1024
        pk = upload_parquet(df, key, bucket, s3_client, dry_run)
        total_orig += orig_kb
        total_parquet += pk
        log(dry_run, f"{source_name} {y}-{mo}-{d} ({orig_kb}KB→{pk}KB)")
    return total_orig, total_parquet


def process_gdelt(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {YYYY-MM-DD}.jsonl
    S3:    bronze/gdelt/year=YYYY/month=MM/day=DD/part-0000.parquet
    """
    total_orig = total_parquet = 0
    for p in sorted(source_dir.glob("*.jsonl")):
        if p.name in SKIP_FILES:
            continue
        parts = hive_day(p.stem)
        if not parts:
            continue
        y, m, d = parts
        key = f"bronze/gdelt/year={y}/month={m}/day={d}/part-0000.parquet"
        if key_exists(key, bucket, s3_client, dry_run):
            print(f"    ATILDI: gdelt {p.stem}")
            continue
        df = load_jsonl(p, "gdelt")
        if df.empty:
            continue
        orig_kb = p.stat().st_size // 1024
        pk = upload_parquet(df, key, bucket, s3_client, dry_run)
        total_orig += orig_kb
        total_parquet += pk
        log(dry_run, f"gdelt {p.stem} ({orig_kb}KB→{pk}KB)")
    return total_orig, total_parquet


def process_akaryakit(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {SEHIR}/{SEHIR}_YYYYMMDD_YYYYMMDD.xls  — Tarih kolonu: DD.MM.YYYY
    S3:    bronze/akaryakit/year=YYYY/month=MM/day=DD/part-0000.parquet
    Tüm XLS'ler birleştirilir, Tarih kolonuna göre gün bazlı yüklenir.
    """
    files = list(source_dir.rglob("*.xls"))
    if not files:
        return 0, 0

    print(f"    {len(files)} XLS okunuyor...")
    dfs, orig_kb = [], 0
    for f in files:
        try:
            df = load_xls(f)
            if not df.empty:
                dfs.append(df)
            orig_kb += f.stat().st_size // 1024
        except Exception as e:
            print(f"    HATA ({f.name}): {e}")

    if not dfs:
        return orig_kb, 0

    merged = pd.concat(dfs, ignore_index=True)
    merged["_dt"] = pd.to_datetime(merged["Tarih"], format="%d.%m.%Y", errors="coerce")
    merged = merged.dropna(subset=["_dt"])
    merged["_date_str"] = merged["_dt"].dt.strftime("%Y-%m-%d")

    total_parquet = 0
    dates = sorted(merged["_date_str"].unique())
    print(f"    {len(dates)} gün ({dates[0]} → {dates[-1]})")

    for date_str in dates:
        y, m, d = hive_day(date_str)
        key = f"bronze/akaryakit/year={y}/month={m}/day={d}/part-0000.parquet"
        if key_exists(key, bucket, s3_client, dry_run):
            continue
        day_df = merged[merged["_date_str"] == date_str].drop(columns=["_dt", "_date_str"])
        pk = upload_parquet(day_df, key, bucket, s3_client, dry_run)
        total_parquet += pk
        log(dry_run, f"akaryakit {date_str} ({pk}KB)")

    return orig_kb, total_parquet


def process_epias(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {dataset}/{YYYY-MM-DD}.jsonl
    S3:    bronze/epias/{dataset}/year=YYYY/month=MM/part-0000.parquet
    Dataset başına aylık birleştirme.
    """
    total_orig = total_parquet = 0
    for dataset_dir in sorted(d for d in source_dir.iterdir() if d.is_dir()):
        month_groups: dict[str, list[Path]] = defaultdict(list)
        for p in dataset_dir.glob("*.jsonl"):
            parts = hive_day(p.stem)
            if parts:
                y, m, _ = parts
                month_groups[f"{y}-{m}"].append(p)

        for ym, files in sorted(month_groups.items()):
            y, m = ym.split("-")
            key = f"bronze/epias/{dataset_dir.name}/year={y}/month={m}/part-0000.parquet"
            if key_exists(key, bucket, s3_client, dry_run):
                print(f"    ATILDI: epias/{dataset_dir.name} {ym}")
                continue
            dfs, orig_kb = [], 0
            for f in files:
                df = load_jsonl(f, "epias")
                if not df.empty:
                    dfs.append(df)
                orig_kb += f.stat().st_size // 1024
            if not dfs:
                continue
            merged = pd.concat(dfs, ignore_index=True)
            pk = upload_parquet(merged, key, bucket, s3_client, dry_run)
            total_orig += orig_kb
            total_parquet += pk
            log(dry_run, f"epias/{dataset_dir.name} {ym} ({len(files)} gün, {orig_kb}KB→{pk}KB)")

    return total_orig, total_parquet


def process_commodities(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {YYYY-MM-DD}.jsonl  — date alanı var
    S3:    bronze/commodities/year=YYYY/month=MM/part-0000.parquet
    """
    month_groups: dict[str, list[Path]] = defaultdict(list)
    for p in source_dir.glob("*.jsonl"):
        parts = hive_day(p.stem)
        if parts:
            y, m, _ = parts
            month_groups[f"{y}-{m}"].append(p)

    total_orig = total_parquet = 0
    for ym, files in sorted(month_groups.items()):
        y, m = ym.split("-")
        key = f"bronze/commodities/year={y}/month={m}/part-0000.parquet"
        if key_exists(key, bucket, s3_client, dry_run):
            print(f"    ATILDI: commodities {ym}")
            continue
        dfs, orig_kb = [], 0
        for f in files:
            df = load_jsonl(f, "commodities")
            if not df.empty:
                dfs.append(df)
            orig_kb += f.stat().st_size // 1024
        if not dfs:
            continue
        merged = pd.concat(dfs, ignore_index=True)
        pk = upload_parquet(merged, key, bucket, s3_client, dry_run)
        total_orig += orig_kb
        total_parquet += pk
        log(dry_run, f"commodities {ym} ({len(files)} gün, {orig_kb}KB→{pk}KB)")
    return total_orig, total_parquet


def process_tcmb(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {series}.jsonl  — date: "DD-MM-YYYY", value, series
    S3:    bronze/tcmb/{series}/year=YYYY/month=MM/part-0000.parquet
    """
    total_orig = total_parquet = 0
    for jsonl_path in sorted(source_dir.glob("*.jsonl")):
        if jsonl_path.name in SKIP_FILES:
            continue
        df = load_jsonl(jsonl_path, "tcmb")
        if df.empty or "date" not in df.columns:
            continue

        df["_ym"] = df["date"].astype(str).map(lambda s: hive_month(s))
        df = df.dropna(subset=["_ym"])

        series_name = jsonl_path.stem
        orig_kb = jsonl_path.stat().st_size // 1024
        total_orig += orig_kb

        for ym_tuple, group in df.groupby("_ym"):
            y, m = ym_tuple
            key = f"bronze/tcmb/{series_name}/year={y}/month={m}/part-0000.parquet"
            if key_exists(key, bucket, s3_client, dry_run):
                continue
            pk = upload_parquet(group.drop(columns=["_ym"]), key, bucket, s3_client, dry_run)
            total_parquet += pk
            log(dry_run, f"tcmb/{series_name} {y}-{m} ({pk}KB)")

    return total_orig, total_parquet


def process_weather(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: {city}/{year}.parquet  — time kolonu: datetime (günlük)
    S3:    bronze/weather/year=YYYY/month=MM/part-0000.parquet
    Tüm şehirler aynı yıl/ay için tek Parquet'e birleştirilir.
    """
    # Yıl-ay bazlı grupla: {(year, month): [parquet_path, ...]}
    ym_groups: dict[tuple, list[Path]] = defaultdict(list)
    for p in source_dir.rglob("*.parquet"):
        # path: {city}/{YYYY}.parquet
        year_str = p.stem
        if re.match(r"^\d{4}$", year_str):
            # 12 ay için hepsini bu yıla ekle; gerçek ay ayrımı okurken yapılır
            ym_groups[year_str].append(p)

    total_orig = total_parquet = 0
    for year_str, files in sorted(ym_groups.items()):
        print(f"    weather {year_str}: {len(files)} şehir okunuyor...")
        dfs, orig_kb = [], 0
        for f in files:
            try:
                df = pd.read_parquet(f)
                if not df.empty:
                    dfs.append(df)
                orig_kb += f.stat().st_size // 1024
            except Exception as e:
                print(f"    HATA ({f}): {e}")

        if not dfs:
            continue

        year_df = pd.concat(dfs, ignore_index=True)

        # time kolonundan ay çek
        if "time" not in year_df.columns:
            print(f"    UYARI: weather {year_str} — 'time' kolonu yok, atlanıyor")
            continue

        year_df["_time"] = pd.to_datetime(year_df["time"], errors="coerce")
        year_df["_month"] = year_df["_time"].dt.strftime("%m")
        year_df = year_df.dropna(subset=["_month"])

        for month_str, month_df in year_df.groupby("_month"):
            key = f"bronze/weather/year={year_str}/month={month_str}/part-0000.parquet"
            if key_exists(key, bucket, s3_client, dry_run):
                print(f"    ATILDI: weather {year_str}-{month_str}")
                continue
            out_df = month_df.drop(columns=["_time", "_month"])
            pk = upload_parquet(out_df, key, bucket, s3_client, dry_run)
            total_parquet += pk
            total_orig += orig_kb // 12  # yaklaşık
            log(dry_run, f"weather {year_str}-{month_str} ({len(month_df)} satır, {pk}KB)")

    return total_orig, total_parquet


# ---------------------------------------------------------------------------
# hal_all processor
# ---------------------------------------------------------------------------

def process_hal_all(source_dir: Path, bucket: str, s3_client, dry_run: bool):
    """
    Lokal: tum_hal_data/{şehir}/{YYYY}.csv
    S3:    bronze/hal_all/year=YYYY/month=MM/part-0000.parquet
    Tüm şehirler aynı ay dosyasında birleştirilir.
    """
    # year → month → list[DataFrame] toplanır
    from collections import defaultdict as _dd
    year_month_rows: dict[str, dict[str, list]] = _dd(lambda: _dd(list))

    city_dirs = [d for d in sorted(source_dir.iterdir()) if d.is_dir()]
    total_orig = 0

    for city_dir in city_dirs:
        for csv_file in sorted(city_dir.glob("*.csv")):
            total_orig += csv_file.stat().st_size // 1024
            try:
                df = pd.read_csv(csv_file, encoding="utf-8-sig", dtype=str)
            except Exception as e:
                print(f"    OKUNAMADI: {csv_file}: {e}")
                continue
            if "tarih" not in df.columns:
                continue
            df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
            df = df.dropna(subset=["tarih"])
            df["year"]  = df["tarih"].dt.year.astype(str).str.zfill(4)
            df["month"] = df["tarih"].dt.month.astype(str).str.zfill(2)
            df["tarih"] = df["tarih"].dt.strftime("%Y-%m-%d")
            for (y, m), grp in df.groupby(["year", "month"]):
                year_month_rows[y][m].append(grp)

    total_parquet = 0
    for y in sorted(year_month_rows):
        for m in sorted(year_month_rows[y]):
            key = f"bronze/hal_all/year={y}/month={m}/part-0000.parquet"
            if key_exists(key, bucket, s3_client, dry_run):
                print(f"    ATILDI: hal_all {y}-{m}")
                continue
            combined = pd.concat(year_month_rows[y][m], ignore_index=True)
            pk = upload_parquet(combined, key, bucket, s3_client, dry_run)
            total_parquet += pk
            log(dry_run, f"hal_all {y}-{m}  {len(combined):>7} satır  {pk}KB")

    return total_orig, total_parquet


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

DISPATCHERS = {
    "market":       lambda dirs, b, c, dr: process_market(dirs["market"], b, c, dr),
    "hal_istanbul": lambda dirs, b, c, dr: process_hal("hal_istanbul", dirs["hal_istanbul"], b, c, dr),
    "hal_harman":   lambda dirs, b, c, dr: process_hal("hal_harman", dirs["hal_harman"], b, c, dr),
    "hal_all":      lambda dirs, b, c, dr: process_hal_all(dirs["hal_all"], b, c, dr),
    "gdelt":        lambda dirs, b, c, dr: process_gdelt(dirs["gdelt"], b, c, dr),
    "akaryakit":    lambda dirs, b, c, dr: process_akaryakit(dirs["akaryakit"], b, c, dr),
    "epias":        lambda dirs, b, c, dr: process_epias(dirs["epias"], b, c, dr),
    "commodities":  lambda dirs, b, c, dr: process_commodities(dirs["commodities"], b, c, dr),
    "tcmb":         lambda dirs, b, c, dr: process_tcmb(dirs["tcmb"], b, c, dr),
    "weather":      lambda dirs, b, c, dr: process_weather(dirs["weather"], b, c, dr),
}

SOURCE_DIRS = {
    "market":       INGESTION_DIR / "market" / "data",
    "hal_istanbul": INGESTION_DIR / "hal" / "istanbul",
    "hal_harman":   INGESTION_DIR / "hal" / "harman",
    "hal_all":      INGESTION_DIR / "hal" / "tum_hal_data",
    "gdelt":        INGESTION_DIR / "gdelt" / "data",
    "akaryakit":    INGESTION_DIR / "akaryakit" / "data",
    "epias":        INGESTION_DIR / "epias" / "data",
    "commodities":  INGESTION_DIR / "commodities" / "data",
    "tcmb":         INGESTION_DIR / "tcmb" / "data",
    "weather":      INGESTION_DIR / "weather" / "data",
}


LOG_FILE = PROJECT_ROOT / "upload_log.jsonl"


def append_log(entry: dict):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--source", default="all",
                        help=f"Kaynak (all veya: {', '.join(SOURCES)})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    s3_client = None if args.dry_run else boto3.client("s3")
    sources_to_run = SOURCES if args.source == "all" else [args.source]

    if args.source != "all" and args.source not in DISPATCHERS:
        print(f"Bilinmeyen kaynak: {args.source}. Seçenekler: {SOURCES}")
        return

    tag = "[DRY-RUN] " if args.dry_run else ""
    print(f"{tag}S3 Bronze yukleme -> s3://{args.bucket}/bronze/\n")

    import datetime as _dt
    for source in sources_to_run:
        d = SOURCE_DIRS[source]
        if not d.exists():
            print(f"  [{source}] klasör yok ({d}), atlanıyor.\n")
            continue
        print(f"  [{source}] işleniyor...")
        try:
            orig_kb, parquet_kb = DISPATCHERS[source](SOURCE_DIRS, args.bucket, s3_client, args.dry_run)
            ratio = round(orig_kb / parquet_kb, 1) if parquet_kb else 0
            print(f"  [{source}] {orig_kb // 1024}MB → {parquet_kb // 1024}MB  ({ratio}x)\n")
            if not args.dry_run:
                append_log({
                    "ts": _dt.datetime.now().isoformat(),
                    "source": source,
                    "bucket": args.bucket,
                    "orig_mb": round(orig_kb / 1024, 1),
                    "parquet_mb": round(parquet_kb / 1024, 1),
                    "compression_x": ratio,
                })
        except Exception as e:
            print(f"  [{source}] HATA: {e}\n")

    print("Tamamlandı.")


if __name__ == "__main__":
    main()
