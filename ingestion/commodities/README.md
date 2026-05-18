# Küresel Emtia Borsaları Modülü (ingestion/commodities)

Bu modül, Türkiye Gıda Tedarik Zinciri modelindeki dışsal girdi şoklarını (Imported Inflation) ölçebilmek amacıyla küresel emtia (tarım ve enerji) borsalarındaki günlük (Tick-Level) kapanış fiyatlarını çeker.

Veriler `yfinance` kütüphanesi kullanılarak Yahoo Finance API'si üzerinden alınır. Herhangi bir API anahtarı veya yetkilendirme gerektirmez.

## Çekilen Emtialar (Tickers)
Aşağıdaki emtiaların Vadeli İşlem (Futures) kontrat fiyatları takip edilmektedir:
- `ZW=F`: Buğday (Wheat)
- `ZC=F`: Mısır (Corn)
- `ZS=F`: Soya Fasulyesi (Soybeans)
- `BZ=F`: Brent Petrol (Brent Crude Oil)
- `NG=F`: Doğalgaz (Natural Gas)
- `SB=F`: Şeker (Sugar)
- `CT=F`: Pamuk (Cotton)
- `KC=F`: Kahve (Coffee)
- `LE=F`: Canlı Hayvan/Sığır (Live Cattle)
- `ZL=F`: Soya Yağı (Soybean Oil)

## Gereksinimler

- `yfinance`
- `pandas`

## Kullanım

Veri çekme botu varsayılan olarak **dünün** (son kapanan işlem gününün) verisini çeker. Hafta sonları borsalar kapalı olduğu için veri dönmeyebilir.

```bash
# Varsayılan çalışma (dünün verisini çeker)
python ingestion/commodities/commodities_ingest.py

# Belirli bir tarih aralığını çekmek için
python ingestion/commodities/commodities_ingest.py --start-date 2026-05-10 --end-date 2026-05-15
```

## Çıktı Formatı

Betiğin başarılı çalışması sonucunda `ingestion/commodities/data/{YYYY-MM-DD}.jsonl` dosyası oluşur. Her satır bir JSON objesidir:

```json
{
  "date": "2026-05-15",
  "ticker": "ZW=F",
  "commodity_name": "Wheat",
  "open": 650.25,
  "high": 655.50,
  "low": 648.00,
  "close": 652.75,
  "volume": 125000.0,
  "_ingested_at": "2026-05-16T08:00:00.123456"
}
```
