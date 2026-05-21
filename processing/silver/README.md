# Silver Layer — Bronze → Silver Dönüşümleri

Ham Bronze verisini tipli, temiz, birim-normalize ve entity-resolved Silver
tablolarına dönüştüren PySpark scriptleri. Her script `s3://s3-bbuckett/bronze/...`
okur, `s3://s3-bbuckett/silver/...` yazar.

## Script kataloğu

| Script | Bronze girdi | Silver çıktı | Ne yapar |
|---|---|---|---|
| `market_silver.py` | `market` + `market_synthetic` | `silver/market_prices` | İki kaynağı union eder, tarih parse, kolon standardizasyonu, `source_type` (real/synthetic) türetir. Karma partition derinliğini (year/month vs year/month/day) ayrı okuyup birleştirir. |
| `hal_silver.py` | `hal_all` | `silver/hal_prices` | String fiyatları double'a çevirir, `price_avg = (min+max)/2` türetir, ürün/kategori adlarını normalize eder. |
| `gdelt_silver.py` | `gdelt` | `silver/gdelt_daily` (+ `gdelt_articles`) | YYYYMMDDHHMMSS tarihi parse, GKG temalarından `food_related` / `turkey_related` bayrakları, günlük aggregate (haber sayısı, ortalama tone). `--skip-articles` ile makale tablosu yazılmaz. |
| `weather_silver.py` | `weather` | `silver/weather_daily` | Open-Meteo kolonlarını okunaklı + birim-etiketli adlara çevirir (t2m_max → temp_max_c), tamamen-null `cloud_amt` kolonunu atar. |
| `tcmb_silver.py` | `tcmb` | `silver/tcmb` | 26 seriyi tek tall tabloda toplar, çift tarih formatı parse eder (günlük DD-MM-YYYY döviz, aylık YYYY-MM TÜFE). |
| `epias_silver.py` | `epias` | `silver/epias/{dataset}` | 26 elektrik piyasa dataset'ini ayrı Silver klasörlerine yazar. 5 dataset'te schema-evolution (int↔double) `mergeSchema` ile çözülür. `--datasets` ile grup grup çalışır. |
| `akaryakit_silver.py` | `akaryakit` | `silver/akaryakit` | Tarih parse, şehir adını Title Case'e normalize, kolon rename (Marka→brand, Fiyat→price_tl). |
| `commodities_silver.py` | `commodities` | `silver/commodities` | yfinance OHLCV verisi, tarih parse, emtia adı temizliği (alt çizgi → boşluk). |
| `silver_joined.py` | `market_prices` + `hal_prices` + mapping CSV | `silver/market_hal_joined` | **Trunk tablo.** Market ve Hal'ı `product_canonical` üzerinden join eder, birim dönüşümü uygular, `margin_abs` / `margin_pct` hesaplar. Tüm Gold analizlerinin temeli. |
| `build_mapping_skeleton.py` | market + hal distinct ürünler | `lookups/hal_market_candidates.json` | Entity resolution için aday üretici — token-overlap pre-filter ile her hal ürününe market adayları eşler. |
| `merge_mapping.py` | `lookups/_chunks/*.csv` | `lookups/hal_market_mapping.csv` | Claude Haiku subagent çıktısı chunk'ları birleştirir, `product_canonical` tekleştirir, slug normalize eder. |

## Trunk tablo: `silver_joined.py`

Market ve Hal sistemlerinde ortak ürün ID'si yok. `silver_joined`:
1. `lookups/hal_market_mapping.csv`'yi broadcast eder (entity resolution sonucu).
2. Market'i `/Kg` birimli + indirimsiz satırlara filtreler, `unit_conversion_factor` uygular.
3. Market ve Hal'ı `(date, city, product_canonical)` üzerinden FULL OUTER JOIN eder.
4. `margin_abs = market - hal`, `margin_pct = margin_abs / hal * 100` türetir.

## Entity resolution

Hal ürün adları (`DOMATES SOFRALIK`) ile market başlıkları (`salkim-domates-1-kg`)
arasında eşleşme: `build_mapping_skeleton.py` aday üretir → Claude Haiku subagent'leri
adayları skorlar → `merge_mapping.py` sonucu `hal_market_mapping.csv`'de birleştirir.

## utils/

- `units.py` — fiyatları ₺/kg'a normalize eder (`price_per_kg`, `parse_weight_kg`).
- `cities.py` — 81 il adını standart Türkçe Title Case'e getirir (`normalize_city_expr`).
- `spark_session.py` — lokal (s3a) + EMR (s3) uyumlu Spark oturumu; `.env`'den AWS kimliği yükler.

## Çalıştırma örnekleri

```bash
SUBMIT="$HOME/spark/bin/spark-submit --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 --driver-memory 3g"

# Tek kaynak
$SUBMIT processing/silver/hal_silver.py
$SUBMIT processing/silver/market_silver.py --start-date 2025-05-20 --end-date 2026-05-20

# gdelt — büyük makale tablosunu atla
$SUBMIT processing/silver/gdelt_silver.py --skip-articles --start-date 2016-01-01 --end-date 2026-05-19

# epias — grup grup (EC2 RAM kısıtı; bkz. orchestration/run_epias_silver_ec2.sh)
$SUBMIT processing/silver/epias_silver.py --datasets price_and_cost,natural_gas_spot

# Trunk
$SUBMIT processing/silver/silver_joined.py --start-date 2025-05-20 --end-date 2026-05-20
```
