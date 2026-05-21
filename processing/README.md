# Processing — Bronze → Silver → Gold → Elasticsearch → Kibana

GıdaRadar'ın işleme katmanı. Ham veriyi (Bronze) temizlenmiş tablolara (Silver),
oradan analiz sonuçlarına (Gold) dönüştürür; sonuçları Elasticsearch'e indeksleyip
Kibana'da görselleştirir. Tüm dönüşümler PySpark 3.5 ile yazılmıştır.

## Medallion akışı

```
  KAYNAKLAR              BRONZE                SILVER                  GOLD                   ES / KIBANA
  ─────────              ──────                ──────                  ────                   ───────────
  marketfiyati  ─┐
  İBB / Harman Hal├──► s3://s3-bbuckett ──► processing/silver/ ──► processing/gold/ ──► Elasticsearch
  GDELT  TCMB    │     /bronze/             *_silver.py            7+1 analiz         9 index
  Open-Meteo     │     (ham parquet,        (tip dönüşümü,         (marj, asimetrik    + Kibana
  EPİAŞ          │      kaynak başına       birim normalizasyon,   ECM, şok, Prophet,  5 dashboard
  Akaryakit  ────┘      partition'lı)       entity resolution)     korelasyon)
```

- **Bronze**: ham veri, dönüşüm yok. `ingestion/` altındaki scraper'lar yazar.
- **Silver**: tipli, temiz, birim-normalize, entity-resolved tablolar.
- **Gold**: iş sorusuna cevap veren analiz tabloları.
- **ES/Kibana**: Gold tabloları indekslenir, dashboard'larda sunulur.

## Veri kaynağı izlenebilirlik tablosu

9 veri kaynağının tamamı bir Gold analizine ve bir ES index'ine bağlıdır.

| Kaynak | Bronze | Silver script | Silver tablo | Gold analiz | ES index |
|---|---|---|---|---|---|
| Market (perakende) | `bronze/market` + `bronze/market_synthetic` | `market_silver.py` | `silver/market_prices` | daily_margin, price_inequality, rockets_feathers | `gidaradar_daily_margin`, `gidaradar_price_inequality_market` |
| Hal (toptan) | `bronze/hal_all` | `hal_silver.py` | `silver/hal_prices` | price_inequality, prophet_forecast | `gidaradar_price_inequality_hal`, `gidaradar_forecast` |
| Market ⋈ Hal | — | `silver_joined.py` | `silver/market_hal_joined` | daily_margin, rockets_feathers, shock_propagation, pandemic_gap, news_price_corr, macro_price_corr | — (trunk tablo) |
| GDELT (haber) | `bronze/gdelt` | `gdelt_silver.py` | `silver/gdelt_daily` | news_price_corr | `gidaradar_news_corr` |
| Hava (Open-Meteo) | `bronze/weather` | `weather_silver.py` | `silver/weather_daily` | shock_propagation | `gidaradar_shocks` |
| Akaryakit | `bronze/akaryakit` | `akaryakit_silver.py` | `silver/akaryakit` | macro_price_corr | `gidaradar_macro_corr` |
| TCMB (kur + enflasyon) | `bronze/tcmb` | `tcmb_silver.py` | `silver/tcmb` | macro_price_corr | `gidaradar_macro_corr` |
| Emtia (yfinance) | `bronze/commodities` | `commodities_silver.py` | `silver/commodities` | macro_price_corr | `gidaradar_macro_corr` |
| EPİAŞ (elektrik) | `bronze/epias` | `epias_silver.py` | `silver/epias/{26 dataset}` | macro_price_corr | `gidaradar_macro_corr` |

## Dizin yapısı

```
processing/
├── silver/        Bronze → Silver dönüşüm scriptleri (bkz. silver/README.md)
│   ├── utils/     birim, şehir, Spark oturumu yardımcıları
│   └── lookups/   entity resolution mapping CSV'leri
├── gold/          Silver → Gold analiz scriptleri (bkz. gold/README.md)
└── es/            Gold → Elasticsearch + Kibana (bkz. es/README.md)

orchestration/
├── run_gold_ec2.sh           gdelt_silver + 7 Gold scripti sıralı
├── run_epias_silver_ec2.sh   epias_silver 4 grup halinde
└── run_gold_ec2.sh           tam pipeline batch
```

## EC2'da çalıştırma

Pipeline EC2 (t3.large, 8 GB) üzerinde çalışır. Elasticsearch + Kibana Docker
container'ları ~4 GB RAM kullandığı için Spark'a ~2.5-3 GB kalır.

**Kural: aynı anda yalnızca tek Spark job.** Batch runner'lar (`run_gold_ec2.sh`,
`run_epias_silver_ec2.sh`) scriptleri sıralı çalıştırır — her `spark-submit`
ayrı JVM açıp kapatır, böylece RAM birikmesi sıfırlanır.

Çalıştırma sırası:

```bash
# 1. EPİAŞ Silver (Gold'dan önce — macro_price_corr'a girdi)
nohup bash orchestration/run_epias_silver_ec2.sh A > /tmp/run_epias.log 2>&1 &

# 2. gdelt_silver + Gold analizleri
nohup bash orchestration/run_gold_ec2.sh > /tmp/run_gold.log 2>&1 &

# 3. Elasticsearch indeksleme
python processing/es/index_to_es.py --recreate

# 4. Kibana data view + dashboard
bash processing/es/create_data_views.sh
python processing/es/build_dashboards.py
```

## Demo subset

`silver_joined` ve Gold analizleri demo döneminde **1 yıl** (2025-05-20 →
2026-05-20) ile çalışır — EC2 RAM kısıtı. Aynı scriptler `--start-date` /
`--end-date` ile tam aralıkta da koşar.

## Bağımlılıklar

PySpark 3.5.1, Java 11, `hadoop-aws:3.3.4` + `aws-java-sdk-bundle:1.12.262`
(S3A connector). Gold analizleri ek: `statsmodels`, `prophet`, `scipy`, `pandas`.
ES indeksleme: `elasticsearch>=8,<9`. AWS kimlik bilgileri proje kökündeki
`.env`'den okunur.
