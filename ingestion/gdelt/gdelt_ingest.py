import os
import sys
import json
import argparse
import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from google.cloud import bigquery
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / '.env')

GDELT_DIR = project_root / 'ingestion' / 'gdelt'
DATA_DIR = GDELT_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = GDELT_DIR / 'state.json'


def get_bq_client():
    try:
        return bigquery.Client()
    except Exception as e:
        print(f"BigQuery Client başlatılamadı: {e}", file=sys.stderr)
        sys.exit(1)


def query_gdelt_day(client, target_date: datetime.date):
    """Tek bir gün için GDELT sorgusu — orijinal DATE filtresi korundu (BQ optimizasyonu)."""
    date_prefix = target_date.strftime("%Y%m%d")
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
                V2Locations LIKE '%Turkey%' OR V2Locations LIKE '%TU%' OR
                V2Locations LIKE '%Russia%' OR V2Locations LIKE '%RS%' OR
                V2Locations LIKE '%Ukraine%' OR V2Locations LIKE '%UP%' OR
                V2Locations LIKE '%Germany%' OR V2Locations LIKE '%GM%' OR
                V2Locations LIKE '%Iraq%'    OR V2Locations LIKE '%IZ%' OR
                V2Locations LIKE '%Syria%'   OR V2Locations LIKE '%SY%' OR
                V2Locations LIKE '%Iran%'    OR V2Locations LIKE '%IR%' OR
                V2Locations LIKE '%Brazil%'  OR V2Locations LIKE '%BR%' OR
                V2Locations LIKE '%Argentina%' OR V2Locations LIKE '%AR%' OR
                V2Locations LIKE '%Netherlands%' OR V2Locations LIKE '%NL%' OR
                V2Locations LIKE '%Spain%'   OR V2Locations LIKE '%SP%' OR
                V2Locations LIKE '%Egypt%'   OR V2Locations LIKE '%EG%'
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
    print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] BQ sorgusu: {target_date}")
    return client.query(query).result()


def parse_v2tone(tone_str):
    if not tone_str:
        return None
    try:
        return float(tone_str.split(',')[0])
    except Exception:
        return None


def save_day_results(results, date_str: str, state: dict, dry_run: bool) -> int:
    """Tek günün sonuçlarını JSONL'e yaz, state güncelle."""
    ingested_at = datetime.datetime.now().isoformat()
    records = []
    for row in results:
        record = dict(row)
        themes_str = record.get('V2Themes', '') or ''
        records.append({
            'id': record.get('GKGRECORDID'),
            'date': record.get('Date'),
            'source': record.get('SourceCollectionIdentifier'),
            'url': record.get('DocumentIdentifier'),
            'tone': parse_v2tone(record.get('V2Tone')),
            'themes': [t for t in themes_str.split(';') if t],
            '_ingested_at': ingested_at,
        })
    if not dry_run:
        out_file = DATA_DIR / f"{date_str}.jsonl"
        with open(out_file, 'w', encoding='utf-8') as f:
            for item in records:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        state[date_str] = {'status': 'success', 'timestamp': ingested_at}
    return len(records)


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_one_day(target_date: datetime.date, dry_run: bool):
    """Tek gün için bağımsız BQ client ile çek — thread-safe."""
    client = bigquery.Client()
    date_str = str(target_date)
    results = query_gdelt_day(client, target_date)
    records = []
    ingested_at = datetime.datetime.now().isoformat()
    for row in results:
        record = dict(row)
        themes_str = record.get('V2Themes', '') or ''
        records.append({
            'id': record.get('GKGRECORDID'),
            'date': record.get('Date'),
            'source': record.get('SourceCollectionIdentifier'),
            'url': record.get('DocumentIdentifier'),
            'tone': parse_v2tone(record.get('V2Tone')),
            'themes': [t for t in themes_str.split(';') if t],
            '_ingested_at': ingested_at,
        })
    if not dry_run and records:
        out_file = DATA_DIR / f"{date_str}.jsonl"
        with open(out_file, 'w', encoding='utf-8') as f:
            for item in records:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return date_str, len(records)


def main():
    parser = argparse.ArgumentParser(description="GDELT V2 GKG Veri Çekme Botu")
    parser.add_argument('--start-date', type=str, help='Başlangıç tarihi (YYYY-MM-DD)')
    parser.add_argument('--end-date',   type=str, help='Bitiş tarihi (YYYY-MM-DD)')
    parser.add_argument('--workers',    type=int, default=4, help='Paralel sorgu sayisi (default: 4)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.start_date:
        start_date = datetime.date.fromisoformat(args.start_date)
    else:
        start_date = datetime.date.today() - datetime.timedelta(days=1)

    if args.end_date:
        end_date = datetime.date.fromisoformat(args.end_date)
    else:
        end_date = datetime.date.today() - datetime.timedelta(days=1)

    print(f"Hedef: {start_date} -> {end_date} | workers: {args.workers}")
    if args.dry_run:
        print("DRY RUN: dosya yazilmayacak.")

    state = load_state()

    # Çekilmemiş günler
    all_days = []
    current = start_date
    while current <= end_date:
        date_str = str(current)
        if state.get(date_str, {}).get('status') == 'success':
            print(f"  ATILDI: {date_str} (zaten mevcut)")
        else:
            all_days.append(current)
        current += datetime.timedelta(days=1)

    print(f"Cekılecek: {len(all_days)} gun")

    total_records = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_one_day, d, args.dry_run): d for d in all_days}
        for future in as_completed(futures):
            target_date = futures[future]
            date_str = str(target_date)
            try:
                date_str, cnt = future.result()
                state[date_str] = {'status': 'success', 'timestamp': datetime.datetime.now().isoformat()}
                save_state(state)
                tag = "[DRY] " if args.dry_run else ""
                print(f"  {tag}KAYDEDILDI: {date_str}  {cnt:>6} kayit")
                total_records += cnt
            except Exception as e:
                print(f"  HATA {date_str}: {e}")
                state[date_str] = {'status': 'error', 'error': str(e), 'timestamp': datetime.datetime.now().isoformat()}
                save_state(state)

    print(f"\nTamamlandi. Toplam: {total_records:,} kayit.")


if __name__ == "__main__":
    main()
