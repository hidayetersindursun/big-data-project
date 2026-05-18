"""
Mevcut JSONL ve CSV dosyalarını Parquet'e çevirip S3 Bronze layer'a yükler.

Kullanım:
    python upload_to_s3.py --bucket my-bucket-name
    python upload_to_s3.py --bucket my-bucket-name --dry-run   # S3'e yüklemeden test et
    python upload_to_s3.py --bucket my-bucket-name --source market  # sadece bir kaynak

S3 yapısı:
    bronze/market/{şehir_ilçe}/{tarih}/{kategori}.parquet  (dosya bazlı)
    bronze/epias/{dataset}.parquet                          (dataset bazlı birleşik)
    bronze/commodities/all.parquet                          (tek birleşik dosya)
    bronze/tcmb/{seri_adı}.parquet                         (dosya bazlı)
    bronze/gdelt/{tarih}.parquet                            (dosya bazlı)
    bronze/hal_istanbul/{dosya_adı}.parquet
    bronze/hal_harman/{dosya_adı}.parquet
    bronze/akaryakit/{şehir}.parquet                        (şehir bazlı birleşik)

Not: EPİAŞ ve commodities küçük dosyalar içerdiğinden birleştirilir.
Parquet her dosyaya sabit overhead ekler — çok sayıda küçük dosyada şişme olur.
"""

import argparse
import json
import tempfile
from pathlib import Path

import boto3
import pandas as pd

PROJECT_ROOT = Path(__file__).parent
INGESTION_DIR = PROJECT_ROOT / "ingestion"

SOURCES = {
    "market":       (INGESTION_DIR / "market" / "data",      "jsonl", "per_file"),
    "hal_istanbul": (INGESTION_DIR / "hal" / "istanbul",     "csv",   "per_file"),
    "hal_harman":   (INGESTION_DIR / "hal" / "harman",       "csv",   "per_file"),
    "tcmb":         (INGESTION_DIR / "tcmb" / "data",        "jsonl", "per_file"),
    "gdelt":        (INGESTION_DIR / "gdelt" / "data",       "jsonl", "per_file"),
    "epias":        (INGESTION_DIR / "epias" / "data",       "jsonl", "by_subdir"),  # dataset bazında birleştir
    "commodities":  (INGESTION_DIR / "commodities" / "data", "jsonl", "merge_all"),  # tek dosya
    "akaryakit":    (INGESTION_DIR / "akaryakit" / "data",   "xls",   "by_subdir"),  # şehir bazında birleştir
}

# Bu dosyalar JSONL değil, atlanacak
SKIP_FILES = {"state.json", "geocode_cache.json", "osm_markets_tr.json"}


def flatten_market_record(record: dict) -> list[dict]:
    """productDepotInfoList iç içe listesini açar — her depot için ayrı satır."""
    depots = record.pop("productDepotInfoList", [])
    categories = record.pop("categories", [])
    record["categories"] = ", ".join(categories) if categories else None
    if not depots:
        return [record]
    return [{**record, **depot} for depot in depots]


def flatten_gdelt_record(record: dict) -> dict:
    """themes listesini virgülle ayrılmış string'e çevirir."""
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
                record = json.loads(line)
                if source == "market":
                    records.extend(flatten_market_record(record))
                elif source == "gdelt":
                    records.append(flatten_gdelt_record(record))
                else:
                    records.append(record)
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(records) if records else pd.DataFrame()


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_xls(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="xlrd")


def collect_files(source_dir: Path, fmt: str) -> list[Path]:
    if fmt == "jsonl":
        return [
            p for p in source_dir.rglob("*")
            if p.suffix == ".jsonl" and p.name not in SKIP_FILES
        ]
    elif fmt == "csv":
        return list(source_dir.rglob("*.csv"))
    elif fmt == "xls":
        return list(source_dir.rglob("*.xls"))
    return []


def s3_key(source_name: str, local_path: Path, source_dir: Path) -> str:
    """Lokal klasör yapısını birebir S3'e yansıtır, sadece uzantı .parquet olur."""
    relative = local_path.relative_to(source_dir)
    stem = relative.with_suffix("").as_posix()
    return f"bronze/{source_name}/{stem}.parquet"


def upload_parquet(df: pd.DataFrame, key: str, bucket: str, s3_client, dry_run: bool) -> int:
    """DataFrame'i geçici Parquet'e yazar, S3'e yükler, boyutu döndürür (KB)."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    df.to_parquet(tmp_path, index=False, engine="pyarrow")
    size_kb = tmp_path.stat().st_size // 1024
    if not dry_run:
        s3_client.upload_file(str(tmp_path), bucket, key)
    tmp_path.unlink()
    return size_kb


def load_file(path: Path, source_name: str, fmt: str) -> pd.DataFrame:
    if fmt == "jsonl":
        return load_jsonl(path, source_name)
    elif fmt == "csv":
        return load_csv(path)
    elif fmt == "xls":
        return load_xls(path)
    return pd.DataFrame()


def process_per_file(source_name: str, source_dir: Path, fmt: str,
                     bucket: str, s3_client, dry_run: bool) -> tuple[int, int]:
    """Her dosyayı ayrı Parquet olarak yükler. Klasör yapısı korunur."""
    files = collect_files(source_dir, fmt)
    total_orig, total_parquet = 0, 0
    for file_path in files:
        try:
            df = load_file(file_path, source_name, fmt)
            if df.empty:
                continue
            key = s3_key(source_name, file_path, source_dir)
            orig_kb = file_path.stat().st_size // 1024
            parquet_kb = upload_parquet(df, key, bucket, s3_client, dry_run)
            total_orig += orig_kb
            total_parquet += parquet_kb
            tag = "[DRY-RUN] " if dry_run else "YÜKLENDI: "
            print(f"    {tag}{file_path.name} → s3://{bucket}/{key}  ({orig_kb}KB → {parquet_kb}KB)")
        except Exception as e:
            print(f"    HATA ({file_path.name}): {e}")
    return total_orig, total_parquet


def process_by_subdir(source_name: str, source_dir: Path, fmt: str,
                      bucket: str, s3_client, dry_run: bool) -> tuple[int, int]:
    """Her alt klasördeki dosyaları birleştirip tek Parquet olarak yükler (EPİAŞ, akaryakıt için)."""
    subdirs = [d for d in source_dir.iterdir() if d.is_dir()]
    total_orig, total_parquet = 0, 0
    for subdir in subdirs:
        files = collect_files(subdir, fmt)
        if not files:
            continue
        dfs, orig_kb = [], 0
        for f in files:
            try:
                df = load_file(f, source_name, fmt)
                if not df.empty:
                    dfs.append(df)
                orig_kb += f.stat().st_size // 1024
            except Exception as e:
                print(f"    HATA ({f.name}): {e}")
        if not dfs:
            continue
        merged = pd.concat(dfs, ignore_index=True)
        key = f"bronze/{source_name}/{subdir.name}.parquet"
        parquet_kb = upload_parquet(merged, key, bucket, s3_client, dry_run)
        total_orig += orig_kb
        total_parquet += parquet_kb
        tag = "[DRY-RUN] " if dry_run else "YÜKLENDI: "
        print(f"    {tag}{subdir.name}/ ({len(files)} dosya) → s3://{bucket}/{key}  ({orig_kb}KB → {parquet_kb}KB)")
    return total_orig, total_parquet


def process_merge_all(source_name: str, source_dir: Path,
                      bucket: str, s3_client, dry_run: bool) -> tuple[int, int]:
    """Tüm dosyaları tek Parquet'e birleştirir (commodities için)."""
    files = [p for p in source_dir.rglob("*.jsonl") if p.name not in SKIP_FILES]
    if not files:
        return 0, 0
    dfs, orig_kb = [], 0
    for f in files:
        try:
            df = load_jsonl(f, source_name)
            if not df.empty:
                dfs.append(df)
            orig_kb += f.stat().st_size // 1024
        except Exception as e:
            print(f"    HATA ({f.name}): {e}")
    if not dfs:
        return orig_kb, 0
    merged = pd.concat(dfs, ignore_index=True)
    key = f"bronze/{source_name}/all.parquet"
    parquet_kb = upload_parquet(merged, key, bucket, s3_client, dry_run)
    tag = "[DRY-RUN] " if dry_run else "YÜKLENDI: "
    print(f"    {tag}{len(files)} dosya birleştirildi → s3://{bucket}/{key}  ({orig_kb}KB → {parquet_kb}KB)")
    return orig_kb, parquet_kb


def process_and_upload(source_name: str, source_dir: Path, fmt: str, mode: str,
                       bucket: str, s3_client, dry_run: bool) -> None:
    print(f"  [{source_name}] işleniyor...")

    if mode == "per_file":
        total_orig, total_parquet = process_per_file(source_name, source_dir, fmt, bucket, s3_client, dry_run)
    elif mode == "by_subdir":
        total_orig, total_parquet = process_by_subdir(source_name, source_dir, fmt, bucket, s3_client, dry_run)
    elif mode == "merge_all":
        total_orig, total_parquet = process_merge_all(source_name, source_dir, bucket, s3_client, dry_run)
    else:
        total_orig, total_parquet = 0, 0

    ratio = round(total_orig / total_parquet, 1) if total_parquet else 0
    print(f"  [{source_name}] Toplam: {total_orig // 1024}MB → {total_parquet // 1024}MB  ({ratio}x küçüldü)\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="S3 bucket adı")
    parser.add_argument("--source", default="all",
                        help=f"Kaynak (all veya: {', '.join(SOURCES)})")
    parser.add_argument("--dry-run", action="store_true", help="S3'e yüklemeden test et")
    args = parser.parse_args()

    s3_client = None if args.dry_run else boto3.client("s3")

    sources_to_run = SOURCES if args.source == "all" else {
        k: v for k, v in SOURCES.items() if k == args.source
    }

    if not sources_to_run:
        print(f"Bilinmeyen kaynak: {args.source}. Seçenekler: {list(SOURCES.keys())}")
        return

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}S3 Bronze yükleme başlıyor → s3://{args.bucket}/bronze/\n")

    for source_name, (source_dir, fmt, mode) in sources_to_run.items():
        if not source_dir.exists():
            print(f"  [{source_name}] Klasör yok, atlanıyor.")
            continue
        process_and_upload(source_name, source_dir, fmt, mode, args.bucket, s3_client, args.dry_run)

    print("Tamamlandı.")


if __name__ == "__main__":
    main()
