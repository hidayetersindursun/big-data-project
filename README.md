# Türkiye Gıda Tedarik Zinciri Şeffaflık Motoru

Türkiye'de hal (toptancı) ile perakende fiyatları arasındaki marjı analiz eden Big Data projesi. Temel araştırma soruları: asimetrik fiyat geçişkenliği ("Rockets & Feathers"), hava şokları → raf fiyatı gecikme süresi ve bölgesel marj farklılıkları.

## Hızlı Başlangıç (Local Stack)

Repo'yu klonladıktan sonra tek komutla bütün NiFi + Kafka + MinIO stack'i ayağa kalkar:

```bash
git clone <repo>
cd big-data-project/infrastructure
./setup.sh
```

Gereksinimler: **Docker + Docker Compose v2** (Docker Desktop Mac/Win, `sudo apt install docker.io docker-compose` Linux), **8 GB RAM**, **10 GB disk**.

Açılan arayüzler:

| Servis | URL | Login |
|---|---|---|
| **NiFi UI** | http://localhost:8080/nifi | yok (HTTP modu) |
| **Kafka UI** | http://localhost:8090 | — |
| **MinIO** | http://localhost:9001 | `admin` / `admin12345` |

Detaylı kullanım + NiFi flow template import + troubleshooting: [`infrastructure/README.md`](infrastructure/README.md).

Ödev (Apache NiFi + Kafka): [`HW_NiFi_Kafka.md`](HW_NiFi_Kafka.md).

Stack'i durdur: `cd infrastructure && ./teardown.sh`.

## Proje Yapısı

```
ingestion/
├── market/          # marketfiyati.org.tr perakende fiyat scraperi
├── tcmb/            # TCMB EVDS: döviz kurları + enflasyon endeksleri
├── hal/
│   ├── istanbul/    # İBB İstanbul Hal fiyatları (Selenium)
│   └── harman/      # Harmanapps hal fiyatları (curl_cffi)
├── weather/         # Open-Meteo — yakında
├── gdelt/           # GDELT haber verisi — yakında
├── commodities/     # Küresel Emtia (Yahoo Finance) verisi
└── epias/           # EPİAŞ saatlik elektrik verileri (eptr2)

infrastructure/      # Docker stack (NiFi, Kafka, MinIO) + setup.sh / teardown.sh
                     # + nifi_flow_template.xml (import-edilebilir NiFi flow)
processing/          # Flink / Spark job'ları
orchestration/       # Airflow DAG'ları
```

## Scraperlar

### Market perakende fiyatları (`ingestion/market/`)

`marketfiyati.org.tr` API'sini asenkron olarak sorgular; ilçe × kategori × sayfalama.

```bash
pip install aiohttp

# Proje kökünden
python ingestion/market/scraper.py                              # sadece bayat veri
python ingestion/market/scraper.py --force                      # tüm veriyi yeniden çek
python ingestion/market/scraper.py --city İstanbul --category Meyve
```

Çıktı: `ingestion/market/data/{şehir}_{ilçe}/YYYY-MM-DD/{kategori}.jsonl`
State: proje kökündeki `state.json`

### TCMB EVDS (`ingestion/tcmb/`)

T.C. Merkez Bankası EVDS API'sinden döviz kurları (USD/EUR/GBP) ve enflasyon endeksleri çeker.

```bash
python ingestion/tcmb/tcmb_evds.py            # bayat serileri güncelle
python ingestion/tcmb/tcmb_evds.py --force    # tüm geçmişi yeniden çek
python ingestion/tcmb/tcmb_evds.py --discover # mevcut serileri listele
python ingestion/tcmb/plot_tcmb.py            # HTML dashboard oluştur
```

Çıktı: `ingestion/tcmb/data/*.jsonl`, dashboard: `ingestion/tcmb/plots/`

### EPİAŞ (`ingestion/epias/`)

EPİAŞ Şeffaflık Platformu'ndan `eptr2` ile elektrik piyasası verilerini çeker.

Şu an başarıyla çekebildiğimiz dataset'ler:

- `price_and_cost` — saatlik `mcp`, `wap`, `smp`, `pos_imb_price`, `neg_imb_price`, `system_direction`, `kupst_cost`
- `consumption` — saatlik `load_plan`, `uecm`, `rt_cons`, `consumption`
- `real_time_generation` — saatlik kaynak bazlı gerçek zamanlı üretim
- `injection_quantity` — saatlik `total`, `naturalGas`, `dam`, `lignite`, `importedCoal`, `wind`, `sun`
- `renewable_injection_quantity` — saatlik `toplam`, `ruzgar`, `jeotermal`, `rezervuarli`, `gunes`, `biyokutle`
- `wind_forecast` — 10 dakikalık `generation`, `forecast`, `quarter1`, `quarter2`, `quarter3`, `quarter4`
- `renewable_unit_cost` — `supplierUnitCost`, `unitCost`, `ptf`, `version`
- `renewable_total_cost` — `toplam`, `ruzgar`, `gunes`, `jeotermal`, `biyokutle`
- `zero_balance_adjustment` — `zeroBalanceAdjustment`, `downRegulation`, `upRegulation`, `negativeImbalance`, `kupst`
- `transmission_loss_factor` — `firstVersionValue`, `lastVersionValue`, `difference`
- `primary_frequency_capacity` — `amount`, `price`
- `secondary_frequency_capacity` — `amount`, `price`

Her kayıtta ortak alanlar bulunur: `timestamp`, `_dataset`, `_source`, `_ingested_at`, `contract`

Not: bazı EPİAŞ servisleri aylık / gecikmeli yayımlandığı için çok yeni tarih aralıklarında boş dönebilir.

Önce proje kökünde `.env` dosyasına EPİAŞ bilgilerini koy:

```bash
EPTR_USERNAME=epias-kullanici-eposta
EPTR_PASSWORD=epias-sifre
```

Ardından çalıştır:

```bash
pip install eptr2 pandas

python ingestion/epias/epias_ingest.py
python ingestion/epias/epias_ingest.py --dataset price_and_cost
python ingestion/epias/epias_ingest.py --start-date 2026-01-01 --end-date 2026-01-31
python ingestion/epias/epias_ingest.py --force
```

Çıktı: `ingestion/epias/data/{dataset}/YYYY-MM-DD.jsonl`
State: `ingestion/epias/state.json`

### İstanbul Hal fiyatları (`ingestion/hal/istanbul/`)

`tarim.ibb.istanbul` adresinden Selenium ile günlük hal fiyatlarını çeker (headless Chrome, "Meyve", "Sebze", "İthal Ürünler" kategorileri).

```bash
pip install pandas selenium

python ingestion/hal/istanbul/ist_gunluk_hal_fiyat_scraber.py
```

Çıktı: `ingestion/hal/istanbul/istanbul_hal_fiyat_gg_aa_yyyy.csv`

### Harman hal fiyatları (`ingestion/hal/harman/`)

`harmanapps.com` sitesinden `curl_cffi` ile Cloudflare atlatarak hal fiyatlarını çeker. Tüm şehirleri ve sayfalamayı otomatik izler.

```bash
pip install pandas curl_cffi beautifulsoup4

python ingestion/hal/harman/harman_gunluk_hal_fiyat_scraber.py
```

Çıktı: `ingestion/hal/harman/harman_hal_fiyat_gg_aa_yyyy.csv`

### Küresel Emtia Borsaları (`ingestion/commodities/`)

Tedarik zinciri maliyet şoklarını ölçmek için `yfinance` üzerinden küresel emtia (Buğday, Mısır, Brent Petrol, Gübre gazı vb.) kapanış fiyatlarını çeker.

```bash
pip install yfinance pandas

# Dünün kapanış verisini çekmek için
python ingestion/commodities/commodities_ingest.py

# Belirli bir tarihi çekmek için
python ingestion/commodities/commodities_ingest.py --start-date 2026-05-10 --end-date 2026-05-15
```

Çıktı: `ingestion/commodities/data/YYYY-MM-DD.jsonl`

## Gereksinimler

| Scraper | Kütüphaneler |
|---|---|
| market | `aiohttp` |
| tcmb | standart kütüphane |
| epias | `eptr2`, `pandas` |
| hal/istanbul | `pandas`, `selenium`, Chrome |
| hal/harman | `pandas`, `curl_cffi`, `beautifulsoup4` |
| commodities | `yfinance`, `pandas` |

## Mimari

```
Ham Kaynak → Bronze (Delta Lake) → Silver (Flink/Spark) → Gold → Superset
```

- **Bronze**: Kafka topic'lerinden ham veri; dönüşüm yok
- **Silver**: Entity resolution (hal ↔ market eşleştirme), birim normalizasyonu (kg)
- **Gold**: `daily_margin_by_city`, `shock_propagation_index`

**Tech stack:** Kafka · Apache Flink · Delta Lake (MinIO/S3) · Airflow · Trino · Superset · Docker

## Ekip

Azmi Yağlı · Abdullah Zengin · Hidayet Ersin Dursun
