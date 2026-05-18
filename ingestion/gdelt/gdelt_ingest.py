import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from google.cloud import bigquery
from dotenv import load_dotenv

# Proje kök dizinini bulup .env dosyasını yükle
# Bu script ingestion/gdelt altında çalışacak, proje kökü ../../
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

GDELT_DIR = project_root / 'ingestion' / 'gdelt'
DATA_DIR = GDELT_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = GDELT_DIR / 'state.json'

def get_bq_client():
    """BigQuery client'ı başlatır."""
    try:
        client = bigquery.Client()
        return client
    except Exception as e:
        print(f"BigQuery Client başlatılamadı. GOOGLE_APPLICATION_CREDENTIALS ortam değişkenini kontrol edin: {e}", file=sys.stderr)
        sys.exit(1)

def query_gdelt_data(client, start_date, end_date):
    """
    Belirtilen tarih aralığında GDELT GKG_partitioned tablosundan
    Türkiye odaklı ve belirli temaları içeren haber verilerini çeker.
    """
    start_str = start_date.strftime("%Y%m%d%H%M%S")
    end_str = end_date.strftime("%Y%m%d%H%M%S")

    # BigQuery sorgusu
    query = f"""
        SELECT 
            GKGRECORDID,
            CAST(DATE AS STRING) as Date,
            SourceCollectionIdentifier,
            DocumentIdentifier,
            V2Themes,
            V2Tone
        FROM 
            `gdelt-bq.gdeltv2.gkg_partitioned`
        WHERE 
            (_PARTITIONTIME BETWEEN TIMESTAMP('{start_date.strftime("%Y-%m-%d")}') AND TIMESTAMP('{end_date.strftime("%Y-%m-%d")}'))
            AND (
                V2Locations LIKE '%Turkey%' OR V2Locations LIKE '%TU%' OR
                V2Locations LIKE '%Russia%' OR V2Locations LIKE '%RS%' OR
                V2Locations LIKE '%Ukraine%' OR V2Locations LIKE '%UP%' OR
                V2Locations LIKE '%Germany%' OR V2Locations LIKE '%GM%' OR
                V2Locations LIKE '%Iraq%' OR V2Locations LIKE '%IZ%' OR
                V2Locations LIKE '%Syria%' OR V2Locations LIKE '%SY%' OR
                V2Locations LIKE '%Iran%' OR V2Locations LIKE '%IR%' OR
                V2Locations LIKE '%Brazil%' OR V2Locations LIKE '%BR%' OR
                V2Locations LIKE '%Argentina%' OR V2Locations LIKE '%AR%' OR
                V2Locations LIKE '%Netherlands%' OR V2Locations LIKE '%NL%' OR
                V2Locations LIKE '%Spain%' OR V2Locations LIKE '%SP%' OR
                V2Locations LIKE '%Egypt%' OR V2Locations LIKE '%EG%'
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
            AND CAST(DATE AS STRING) LIKE '{start_str[:8]}%'
    """
    
    print(f"[{datetime.datetime.now()}] BigQuery sorgusu çalıştırılıyor: {start_date.date()} - {end_date.date()}")
    
    job_config = bigquery.QueryJobConfig()
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    return results

def parse_v2tone(tone_str):
    """
    V2Tone alanı virgüllerle ayrılmış değerler içerir.
    Sadece ilk değeri (genel Tone) float olarak döndürür.
    """
    if not tone_str:
        return None
    try:
        parts = tone_str.split(',')
        if parts:
            return float(parts[0])
    except:
        pass
    return None

def save_results(results, target_date):
    """Sonuçları günlük JSONL dosyasına kaydeder."""
    date_str = target_date.strftime("%Y-%m-%d")
    out_file = DATA_DIR / f"{date_str}.jsonl"
    
    count = 0
    with open(out_file, 'w', encoding='utf-8') as f:
        for row in results:
            record = dict(row)
            
            tone_val = parse_v2tone(record.get('V2Tone'))
            
            themes_str = record.get('V2Themes', '')
            themes_list = [t for t in themes_str.split(';') if t] if themes_str else []
            
            item = {
                'id': record.get('GKGRECORDID'),
                'date': record.get('Date'),
                'source': record.get('SourceCollectionIdentifier'),
                'url': record.get('DocumentIdentifier'),
                'tone': tone_val,
                'themes': themes_list,
                '_ingested_at': datetime.datetime.now().isoformat()
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            count += 1
            
    print(f"[{datetime.datetime.now()}] {count} kayıt {out_file} dosyasına kaydedildi.")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def main():
    parser = argparse.ArgumentParser(description="GDELT V2 GKG Veri Çekme Botu")
    parser.add_argument('--start-date', type=str, help='Başlangıç tarihi (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='Bitiş tarihi (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Veri kaydetmeden sadece çalışmayı test eder')
    args = parser.parse_args()

    client = get_bq_client()

    if args.start_date and args.end_date:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=1)
        
    print(f"Hedeflenen zaman aralığı: {start_date.date()} - {end_date.date()}")
    
    if args.dry_run:
        print("DRY RUN: Veri kaydedilmeyecek.")
    
    current_date = start_date
    state = load_state()
    
    while current_date <= end_date:
        c_date_str = current_date.strftime("%Y-%m-%d")
        
        if c_date_str in state and state[c_date_str].get('status') == 'success' and not args.start_date:
             print(f"{c_date_str} zaten çekilmiş, atlanıyor...")
             current_date += datetime.timedelta(days=1)
             continue
        
        c_start = current_date.replace(hour=0, minute=0, second=0)
        c_end = current_date.replace(hour=23, minute=59, second=59)
        
        try:
            results = query_gdelt_data(client, c_start, c_end)
            if not args.dry_run:
                save_results(results, current_date)
                
                state[c_date_str] = {
                    'status': 'success',
                    'timestamp': datetime.datetime.now().isoformat()
                }
                save_state(state)
        except Exception as e:
            print(f"[{datetime.datetime.now()}] {c_date_str} tarihi için sorgu hatası: {e}")
            if not args.dry_run:
                state[c_date_str] = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.datetime.now().isoformat()
                }
                save_state(state)
            
        current_date += datetime.timedelta(days=1)

if __name__ == "__main__":
    main()
