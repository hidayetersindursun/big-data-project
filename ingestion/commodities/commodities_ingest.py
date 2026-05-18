import yfinance as yf
import pandas as pd
import json
import os
import argparse
import datetime
from pathlib import Path

# Çekilecek temel emtialar (Yahoo Finance Ticker Sembolleri)
# ZW=F: Buğday (Wheat)
# ZC=F: Mısır (Corn)
# ZS=F: Soya Fasulyesi (Soybeans)
# BZ=F: Brent Petrol (Brent Crude Oil)
# NG=F: Doğalgaz (Natural Gas)
# SB=F: Şeker (Sugar)
# CT=F: Pamuk (Cotton)
# KC=F: Kahve (Coffee)
# LE=F: Canlı Hayvan/Sığır (Live Cattle)
# ZL=F: Soya Yağı (Soybean Oil)

COMMODITIES = {
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
    "ZS=F": "Soybeans",
    "BZ=F": "Brent_Oil",
    "NG=F": "Natural_Gas",
    "SB=F": "Sugar",
    "CT=F": "Cotton",
    "KC=F": "Coffee",
    "LE=F": "Live_Cattle",
    "ZL=F": "Soybean_Oil"
}

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR / "data"

def setup_directories():
    os.makedirs(DATA_DIR, exist_ok=True)

def fetch_commodities(start_date: datetime.date, end_date: datetime.date):
    """
    Belirtilen tarih aralığı için küresel emtia fiyatlarını yfinance üzerinden çeker.
    """
    tickers = list(COMMODITIES.keys())
    print(f"[{datetime.datetime.now()}] {len(tickers)} adet emtia verisi çekiliyor: {start_date} - {end_date}")
    
    # yfinance end_date'i exclusive (hariç) alır, bu yüzden end_date'e 1 gün ekliyoruz.
    fetch_end_date = end_date + datetime.timedelta(days=1)
    
    try:
        # group_by='ticker' ile her ticker için ayrı sütun grupları alırız
        data = yf.download(
            tickers, 
            start=start_date.strftime("%Y-%m-%d"), 
            end=fetch_end_date.strftime("%Y-%m-%d"),
            group_by='ticker',
            progress=False
        )
        
        if data.empty:
            print(f"[{datetime.datetime.now()}] Veri bulunamadı. (Borsalar kapalı olabilir)")
            return []

        records = []
        # Eğer tek bir ticker varsa yfinance DataFrame yapısı farklı olur, onu handle etmek için:
        if len(tickers) == 1:
            ticker = tickers[0]
            for date, row in data.iterrows():
                if pd.isna(row['Close']):
                    continue
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "commodity_name": COMMODITIES[ticker],
                    "open": float(row['Open']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "close": float(row['Close']),
                    "volume": float(row['Volume']),
                    "_ingested_at": datetime.datetime.now().isoformat()
                })
        else:
            for ticker in tickers:
                if ticker not in data.columns.levels[0]:
                    continue
                    
                ticker_data = data[ticker]
                for date, row in ticker_data.iterrows():
                    if pd.isna(row['Close']):
                        continue
                    records.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "ticker": ticker,
                        "commodity_name": COMMODITIES[ticker],
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": float(row['Volume']),
                        "_ingested_at": datetime.datetime.now().isoformat()
                    })
                    
        return records

    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        return []

def save_records(records, target_date: datetime.date):
    """
    Kayıtları belirtilen günün JSONL dosyasına kaydeder.
    """
    if not records:
        return

    # Verileri tarihe göre grupla (Çünkü çoklu gün çekilmiş olabilir)
    records_by_date = {}
    for r in records:
        d = r['date']
        if d not in records_by_date:
            records_by_date[d] = []
        records_by_date[d].append(r)

    for date_str, daily_records in records_by_date.items():
        output_file = DATA_DIR / f"{date_str}.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in daily_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"[{datetime.datetime.now()}] {len(daily_records)} kayıt {output_file} dosyasına kaydedildi.")

def main():
    parser = argparse.ArgumentParser(description="Küresel Emtia Fiyatları (Yahoo Finance) Scraper")
    parser.add_argument("--start-date", type=str, help="Başlangıç tarihi (YYYY-MM-DD)", default=None)
    parser.add_argument("--end-date", type=str, help="Bitiş tarihi (YYYY-MM-DD)", default=None)
    
    args = parser.parse_args()
    setup_directories()

    # Eğer tarih verilmemişse sadece dünü çek (borsa kapanış fiyatları için dün en güvenlisidir)
    if not args.start_date:
        end_date = datetime.date.today() - datetime.timedelta(days=1)
        start_date = end_date
    else:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else start_date

    records = fetch_commodities(start_date, end_date)
    save_records(records, end_date)

if __name__ == "__main__":
    main()
