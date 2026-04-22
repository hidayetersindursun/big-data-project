# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Turkey Food Supply Chain Transparency and Spatial Margin Analysis Engine** — a Big Data project analyzing price margins between wholesale markets (hal) and retail stores across Turkish cities. Core research questions: asymmetric price transmission ("Rockets and Feathers"), shock propagation speed from weather events to shelf prices, and location-based speculation.

## Running the Scrapers

### Market retail prices (marketfiyati.org.tr)

```bash
# From project root — scrapes stale data only (default: 24h threshold)
python ingestion/market/scraper.py

# Force full re-scrape
python ingestion/market/scraper.py --force

# Filters: --city, --district, --category (combinable)
python ingestion/market/scraper.py --city İstanbul --category Meyve
```

Targets `marketfiyati.org.tr` — two API bases:
- `https://api.marketfiyati.org.tr/api/v2` — product search and depot discovery
- `https://harita.marketfiyati.org.tr/Service/api/v1` — geolocation/autocomplete

Output: `ingestion/market/data/{şehir}_{ilçe}/{tarih}/{kategori}.jsonl` — one product JSON per line.
State: `state.json` at project root tracks last-scraped timestamps.

### TCMB EVDS (FX rates + inflation)

```bash
python ingestion/tcmb/tcmb_evds.py            # fetch stale series
python ingestion/tcmb/tcmb_evds.py --force    # force full re-fetch
python ingestion/tcmb/tcmb_evds.py --discover # list available series
python ingestion/tcmb/plot_tcmb.py            # generate HTML dashboard
```

Output: `ingestion/tcmb/data/*.jsonl`, dashboards: `ingestion/tcmb/plots/`

### Hal wholesale prices

```bash
python ingestion/hal/istanbul/ist_gunluk_hal_fiyat_scraber.py   # Istanbul Hal
python ingestion/hal/harman/harman_gunluk_hal_fiyat_scraber.py  # Harman Hal
```

### Adding a new city (market scraper)
Edit `ingestion/market/config.py` → `CITIES` dict only. No other file changes needed.

### Market ingestion modules
- `ingestion/market/config.py` — cities, categories, API constants, timing settings
- `ingestion/market/client.py` — raw HTTP calls (coordinates, depots, paginated product fetch)
- `ingestion/market/state.py` — load/save/check staleness of `state.json`
- `ingestion/market/scraper.py` — orchestration entrypoint
- `ingestion/market/depot_grid.py` — grid search to build a complete depot database (see below)

### Scrape Algorithm

marketfiyati.org.tr API'si konum bazlı çalışır — "bana bu koordinata yakın depotları ver" mantığıyla. Bu nedenle tek bir ilçe merkezi koordinatından sorgu yapmak yetersizdir; ilçenin farklı mahalleleri farklı depotlar döndürür.

**Ürün scrape akışı (`scraper.py`)**

```
İlçe merkezi koordinatı
    → /AutoSuggestion/Search  →  (lat, lon)
    → /nearest(lat, lon, radius=1km)  →  depot listesi
    → her kategori için /searchByCategories(depot_ids, page=0,1,2,…)
    → sayfalama: page_size=25 (API hard limit), toplam ürüne ulaşana kadar döner
    → JSONL: ingestion/market/data/{şehir}_{ilçe}/{tarih}/{kategori}.jsonl
```

**Kısıtlar keşfedildi:**
- API sayfa başına max 25 ürün döndürür (`size` parametresi görmezden gelinir)
- `/nearest` yalnızca sorgu noktasına yakın depotları döndürür — tek noktadan sorgulayınca ilçenin uzak mahalleleri eksik kalır
- API rate limiting: arka arkaya çok sorgu atılınca `RemoteDisconnected` hatası verir → exponential backoff (10s, 20s, 40s, 80s, 160s + jitter)

**Depot grid search (`depot_grid.py`)**

Tek noktadan sorgulama eksikliğini gidermek için ilçenin bounding box'ı grid noktalarına bölünür, her noktadan `/nearest` sorgusu atılır, sonuçlar `depotId` ile deduplicate edilir:

```
İlçe merkezi ± span derece  →  grid noktaları (step=0.005°, ~500m aralık)
    → her noktadan /nearest(radius=1km)
    → depotId key'li dict ile deduplicate
    → depots.json: {id, name, market, lat, lon}
```

Örnek: Bayrampaşa merkezi koordinatından `/nearest` → 10 depot.
Aynı ilçe için grid search (156 nokta) → **629 unique depot**.

**Çıktı formatı (tarih bazlı partition)**

```
ingestion/market/data/
└── {şehir}_{ilçe}/
    └── YYYY-MM-DD/
        └── {kategori}.jsonl   ← her satır bir ürün JSON'u
```

Aynı gün iki kez çalışırsa üzerine yazar. Farklı günlerde yeni klasör açılır. Spark'ta `WHERE date=...` ile verimli okuma sağlar.

## Architecture

### Data Sources
| Source | Method | Frequency |
|---|---|---|
| marketfiyati.org.tr (retail prices) | REST API (scraper.py) | Daily / Intraday |
| İBB Hal prices | Swagger REST API | Daily |
| İzmir Hal prices | API + CSV | Daily |
| Open-Meteo (weather) | REST API | Hourly stream |
| GDELT (news) | S3 / API | 15-min stream |
| EPİAŞ (electricity) | Transparency API | Hourly stream |
| TCMB EVDS (FX + indices) | EVDS API | Daily/Monthly |

### Pipeline Architecture (Medallion)
- **Bronze Layer**: Raw data from Kafka topics (`raw_weather`, `raw_gdelt`, `raw_market_prices`) and Airflow batch pulls → Delta Lake, no transformation
- **Silver Layer**: Apache Flink / Spark Structured Streaming — entity resolution (fuzzy match between hal product names and market slugs), unit standardization to KG, null cleaning, spatial alignment
- **Gold Layer**: `daily_margin_by_city_and_market`, `shock_propagation_index` — aggregated business-ready tables

### Key Engineering Challenges
1. **Entity Resolution**: No shared IDs between hal and market systems. Must fuzzy-match (TF-IDF + cosine similarity) e.g. `"Domates Sofralık Sera"` ↔ `"salkim-domates-1-kg"`
2. **Unit Standardization**: Hal prices in "Kasa/Çuval/Bağ", retail in "Gram/Adet/Paket" → UDFs to normalize to 1 KG
3. **Temporal & Spatial Alignment**: As-of joins across GDELT (15-min), EPİAŞ (hourly), Hal (daily), Tonaj (monthly); spatial join of city retail data to nearest hal

### Tech Stack
- **Message Broker**: Apache Kafka
- **Stream Processing**: Apache Flink
- **Storage**: Delta Lake on MinIO or AWS S3
- **Orchestration**: Apache Airflow (02:00 nightly DAGs for İBB/İzmir Hal, TCMB)
- **Query Engine**: Trino (Presto)
- **Visualization**: Apache Superset
- **Deployment**: Docker / Docker Compose

## Team
Azmi Yağlı, Abdullah Zengin, Hidayet Ersin Dursun
