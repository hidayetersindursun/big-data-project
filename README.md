# Türkiye Gıda Tedarik Zinciri Şeffaflık Motoru

Türkiye'de hal (toptancı) ile perakende fiyatları arasındaki marjı analiz eden Big Data projesi. Temel araştırma soruları: asimetrik fiyat geçişkenliği ("Rockets & Feathers"), hava şokları → raf fiyatı gecikme süresi ve bölgesel marj farklılıkları.

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
└── epias/           # EPİAŞ saatlik elektrik verileri (eptr2)

infrastructure/      # Docker, Kafka, Airflow konfigürasyonları
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

## Gereksinimler

| Scraper | Kütüphaneler |
|---|---|
| market | `aiohttp` |
| tcmb | standart kütüphane |
| epias | `eptr2`, `pandas` |
| hal/istanbul | `pandas`, `selenium`, Chrome |
| hal/harman | `pandas`, `curl_cffi`, `beautifulsoup4` |

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
