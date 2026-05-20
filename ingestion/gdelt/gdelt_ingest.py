"""
GDELT V2 GKG → S3 Bronze (Parquet)

Kullanım:
    python ingestion/gdelt/gdelt_ingest.py --bucket s3-bbuckett
    python ingestion/gdelt/gdelt_ingest.py --bucket s3-bbuckett --start-date 2021-01-01
    python ingestion/gdelt/gdelt_ingest.py --bucket s3-bbuckett --workers 4 --dry-run

Özellikler:
  - BQ'dan günlük sorgular çeker, doğrudan S3'e Parquet olarak yükler (disk'e sıfır veri)
  - Windows uyku engeli: bilgisayar uykuya girmez
  - state.json ile kaldığı yerden devam eder (sadece meta-veri, veri dosyası değil)
  - Hem konsol hem dosyaya renkli log yazar (gdelt_ingest.log)
"""

import ctypes
import io
import json
import logging
import sys

# Windows konsolunda UTF-8 zorunlu (cp1254 -> UnicodeEncodeError olmaz)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from google.cloud import bigquery

# ---------------------------------------------------------------------------
# Paths & env
# ---------------------------------------------------------------------------

project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / '.env')

GDELT_DIR = project_root / 'ingestion' / 'gdelt'
STATE_FILE = GDELT_DIR / 'state.json'
LOG_FILE = GDELT_DIR / 'gdelt_ingest.log'

# ---------------------------------------------------------------------------
# Windows sleep prevention
# ---------------------------------------------------------------------------

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def prevent_sleep():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
        logging.info("Uyku engellendi (Windows SetThreadExecutionState)")


def allow_sleep():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        logging.info("Uyku engeli kaldırıldı")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    fmt = '%(asctime)s [%(levelname)s] %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
        ],
    )


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def key_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def upload_df_to_s3(df: pd.DataFrame, key: str, bucket: str, s3, dry_run: bool) -> int:
    """DataFrame → in-memory Parquet bytes → S3. Boyut (KB) döndürür."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine='pyarrow')
    size_kb = len(buf.getvalue()) // 1024
    if not dry_run:
        buf.seek(0)
        s3.upload_fileobj(buf, bucket, key)
    return size_kb


# ---------------------------------------------------------------------------
# BigQuery
# ---------------------------------------------------------------------------

def query_gdelt_day(client, target_date: datetime.date):
    date_prefix = target_date.strftime('%Y%m%d')
    query = f"""
        SELECT
            GKGRECORDID,
            CAST(DATE AS STRING) as Date,
            SourceCollectionIdentifier,
            DocumentIdentifier,
            V2Themes,
            V2Tone
        FROM `gdelt-bq.gdeltv2.gkg_partitioned`
        WHERE
            _PARTITIONTIME = TIMESTAMP('{target_date}')
            AND (
                V2Locations LIKE '%Turkey%'      OR V2Locations LIKE '%TU%' OR
                V2Locations LIKE '%Russia%'      OR V2Locations LIKE '%RS%' OR
                V2Locations LIKE '%Ukraine%'     OR V2Locations LIKE '%UP%' OR
                V2Locations LIKE '%Germany%'     OR V2Locations LIKE '%GM%' OR
                V2Locations LIKE '%Iraq%'        OR V2Locations LIKE '%IZ%' OR
                V2Locations LIKE '%Syria%'       OR V2Locations LIKE '%SY%' OR
                V2Locations LIKE '%Iran%'        OR V2Locations LIKE '%IR%' OR
                V2Locations LIKE '%Brazil%'      OR V2Locations LIKE '%BR%' OR
                V2Locations LIKE '%Argentina%'   OR V2Locations LIKE '%AR%' OR
                V2Locations LIKE '%Netherlands%' OR V2Locations LIKE '%NL%' OR
                V2Locations LIKE '%Spain%'       OR V2Locations LIKE '%SP%' OR
                V2Locations LIKE '%Egypt%'       OR V2Locations LIKE '%EG%'
            )
            AND (
                V2Themes LIKE '%FOOD_SECURITY%' OR
                V2Themes LIKE '%ECON_INFLATION%' OR
                V2Themes LIKE '%ECON_COSTOFLIFE%' OR
                V2Themes LIKE '%ECON_PRICECONTROLS%' OR
                V2Themes LIKE '%FUELPRICES%' OR
                V2Themes LIKE '%ENV_DROUGHT%' OR
                V2Themes LIKE '%ECON_OILPRICE%' OR
                V2Themes LIKE '%ENV_NATURALGAS%' OR
                V2Themes LIKE '%TAX_ECON_PRICE%' OR
                V2Themes LIKE '%AGRICULTURE%' OR
                V2Themes LIKE '%ECON_DIESELPRICE%' OR
                V2Themes LIKE '%WB_135_TRANSPORT%' OR
                V2Themes LIKE '%SUPPLY_CHAIN%' OR
                V2Themes LIKE '%NATURAL_DISASTER_FLOODS%' OR
                V2Themes LIKE '%ENV_CLIMATECHANGE%' OR
                V2Themes LIKE '%NATURAL_DISASTER_EXTREME_WEATHER%' OR
                V2Themes LIKE '%ECON_CURRENCY_EXCHANGE_RATE%' OR
                V2Themes LIKE '%ECON_INTEREST_RATES%' OR
                V2Themes LIKE '%TAX_FOODSTAPLES_WHEAT%' OR
                V2Themes LIKE '%TAX_FOODSTAPLES_MEAT%' OR
                V2Themes LIKE '%WB_175_FERTILIZERS%' OR
                V2Themes LIKE '%UNEMPLOYMENT%' OR
                V2Themes LIKE '%WB_2670_JOBS%' OR
                V2Themes LIKE '%TAX_DISEASE_OUTBREAK%' OR
                V2Themes LIKE '%SMUGGLING%' OR
                V2Themes LIKE '%CORRUPTION%' OR
                V2Themes LIKE '%BLOCKADE%' OR
                V2Themes LIKE '%SANCTIONS%'
            )
            AND CAST(DATE AS STRING) LIKE '{date_prefix}%'
    """
    return client.query(query).result()


def parse_v2tone(tone_str):
    if not tone_str:
        return None
    try:
        return float(tone_str.split(',')[0])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core: fetch one day → upload to S3
# ---------------------------------------------------------------------------

def fetch_and_upload_day(
    target_date: datetime.date,
    bucket: str,
    dry_run: bool,
) -> tuple[str, int]:
    """
    BQ'dan bir günü çekip S3'e Parquet olarak yükler.
    Döndürür: (date_str, record_count)  — -1 = zaten S3'te mevcut, atlandı.
    """
    date_str = str(target_date)
    y = target_date.strftime('%Y')
    m = target_date.strftime('%m')
    d = target_date.strftime('%d')
    s3_key = f"bronze/gdelt/year={y}/month={m}/day={d}/part-0000.parquet"

    s3 = boto3.client('s3')

    if not dry_run and key_exists(s3, bucket, s3_key):
        logging.info(f"ATILDI (S3 mevcut): {date_str}")
        return date_str, -1

    bq_client = bigquery.Client()
    logging.info(f"BQ sorgusu: {date_str}")
    results = query_gdelt_day(bq_client, target_date)

    ingested_at = datetime.datetime.now().isoformat()
    records = []
    for row in results:
        rec = dict(row)
        themes_str = rec.get('V2Themes', '') or ''
        records.append({
            'id': rec.get('GKGRECORDID'),
            'date': rec.get('Date'),
            'source': rec.get('SourceCollectionIdentifier'),
            'url': rec.get('DocumentIdentifier'),
            'tone': parse_v2tone(rec.get('V2Tone')),
            'themes': ', '.join(t for t in themes_str.split(';') if t),
            '_ingested_at': ingested_at,
        })

    if not records:
        logging.warning(f"BOŞ: {date_str} — 0 kayıt, S3'e yüklenmedi")
        return date_str, 0

    df = pd.DataFrame(records)
    size_kb = upload_df_to_s3(df, s3_key, bucket, s3, dry_run)
    tag = '[DRY] ' if dry_run else ''
    logging.info(
        f"{tag}YUKLENDI: {date_str}  {len(records):>6} kayit  "
        f"{size_kb}KB  -> s3://{bucket}/{s3_key}"
    )
    return date_str, len(records)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='GDELT V2 GKG → S3 Bronze (5 yıl, Parquet)')
    parser.add_argument('--bucket', default='s3-bbuckett', help='S3 bucket adı')
    parser.add_argument('--start-date', type=str, default=None,
                        help='Başlangıç tarihi YYYY-MM-DD (varsayılan: 5 yıl önce)')
    parser.add_argument('--end-date', type=str, default=None,
                        help='Bitiş tarihi YYYY-MM-DD (varsayılan: dün)')
    parser.add_argument('--workers', type=int, default=8,
                        help='Paralel BQ sorgu sayisi (varsayilan: 8)')
    parser.add_argument('--dry-run', action='store_true',
                        help='S3\'e yükleme yapma, sadece logla')
    args = parser.parse_args()

    setup_logging()

    today = datetime.date.today()
    start_date = (
        datetime.date.fromisoformat(args.start_date)
        if args.start_date
        else today - datetime.timedelta(days=5 * 365)
    )
    end_date = (
        datetime.date.fromisoformat(args.end_date)
        if args.end_date
        else today - datetime.timedelta(days=1)
    )

    logging.info('=' * 60)
    logging.info('GDELT ingest başlatıldı')
    logging.info(f'Donem : {start_date}  ->  {end_date}')
    logging.info(f'Bucket: s3://{args.bucket}/bronze/gdelt/')
    logging.info(f'Workers: {args.workers}')
    if args.dry_run:
        logging.info('DRY RUN — S3\'e yükleme yapılmayacak')
    logging.info('=' * 60)

    prevent_sleep()

    state = load_state()

    all_days: list[datetime.date] = []
    current = start_date
    while current <= end_date:
        date_str = str(current)
        if state.get(date_str, {}).get('status') == 'success':
            pass  # state'de başarılı → atla (arka planda S3 check yok, hız için)
        else:
            all_days.append(current)
        current += datetime.timedelta(days=1)

    total_span = (end_date - start_date).days + 1
    already_done = total_span - len(all_days)
    logging.info(
        f'Toplam {total_span} gün | '
        f'Tamamlanmış: {already_done} | '
        f'Çekilecek: {len(all_days)}'
    )

    total_records = 0
    completed = 0
    errors = 0
    start_ts = datetime.datetime.now()

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(fetch_and_upload_day, d, args.bucket, args.dry_run): d
                for d in all_days
            }
            for future in as_completed(futures):
                target_date = futures[future]
                date_str = str(target_date)
                try:
                    _, cnt = future.result()
                    ts_now = datetime.datetime.now().isoformat()
                    if cnt >= 0:
                        if cnt > 0:
                            total_records += cnt
                        if not args.dry_run:
                            state[date_str] = {
                                'status': 'success',
                                'timestamp': ts_now,
                                'records': cnt,
                            }
                    else:
                        # S3'te zaten mevcuttu
                        if not args.dry_run:
                            state[date_str] = {
                                'status': 'success',
                                'timestamp': ts_now,
                                'source': 's3_existing',
                            }
                    completed += 1
                except Exception as e:
                    logging.error(f'HATA {date_str}: {e}')
                    if not args.dry_run:
                        state[date_str] = {
                            'status': 'error',
                            'error': str(e),
                            'timestamp': datetime.datetime.now().isoformat(),
                        }
                    errors += 1
                finally:
                    if not args.dry_run:
                        save_state(state)

                # İlerleme özeti her 50 günde bir
                done_total = completed + errors
                if done_total % 50 == 0 or done_total == len(all_days):
                    elapsed = (datetime.datetime.now() - start_ts).total_seconds()
                    rate = done_total / elapsed if elapsed > 0 else 0
                    remaining = len(all_days) - done_total
                    eta_s = remaining / rate if rate > 0 else 0
                    eta_str = str(datetime.timedelta(seconds=int(eta_s)))
                    pct = done_total / len(all_days) * 100 if all_days else 100
                    logging.info(
                        f'[İlerleme] {done_total}/{len(all_days)} ({pct:.1f}%)  '
                        f'Hız: {rate:.2f} gün/sn  ETA: {eta_str}  '
                        f'Hata: {errors}'
                    )
    finally:
        allow_sleep()

    elapsed_total = datetime.datetime.now() - start_ts
    logging.info('=' * 60)
    logging.info('TAMAMLANDI')
    logging.info(f'Toplam kayıt : {total_records:,}')
    logging.info(f'Başarılı gün : {completed}')
    logging.info(f'Hatalı gün   : {errors}')
    logging.info(f'Geçen süre   : {elapsed_total}')
    logging.info('=' * 60)


if __name__ == '__main__':
    main()
