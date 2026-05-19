# Pipeline Mimarisi

## Baştan Sona Akış

### 1. Ingestion (NiFi)

NiFi tüm scraper'ları tetikler ve veriyi iki farklı yola yönlendirir:

**Günlük batch kaynaklar → direkt S3:**
- Market fiyatları (marketfiyati.org.tr)
- Hal fiyatları (İstanbul, Harman)
- TCMB (kur, enflasyon)
- Commodities (yfinance)

**Streaming kaynaklar → önce Kafka, sonra S3:**
- GDELT (15 dakikada bir)
- EPİAŞ (saatlik elektrik)

Kafka burada tampon görevi görür — veri üretilince Kafka kuyruğuna düşer, Spark hazır olduğunda oradan alır. Spark'ın her 15 dakikada bir S3'e bakmasına gerek kalmaz, Kafka "mesaj geldi" diye haber verir.

---

### 2. Bronze Layer (S3)

Ham veri, flatten edilmiş Parquet formatında saklanır.

```
s3://bucket/bronze/
  market/year=YYYY/month=MM/day=DD/part-0000.parquet
  market_synthetic/year=YYYY/month=MM/part-0000.parquet          (geçmiş aylar)
  market_synthetic/year=YYYY/month=MM/day=DD/part-0000.parquet   (cari ay)
  hal_all/year=YYYY/month=MM/part-0000.parquet                          (81 il, 2016-2026, gercek+sentetik)
  gdelt/year=YYYY/month=MM/day=DD/part-0000.parquet
  epias/{dataset}/year=YYYY/month=MM/part-0000.parquet
  tcmb/{series}/year=YYYY/month=MM/part-0000.parquet
  commodities/year=YYYY/month=MM/part-0000.parquet
  akaryakit/year=YYYY/month=MM/day=DD/part-0000.parquet
  weather/year=YYYY/month=MM/part-0000.parquet
```

**Niye Hive-style partition?** Spark `WHERE year=2024 AND month=1` yazdığında sadece o klasörü okur, tüm Bronze'u taramaz. EMR maliyeti doğrudan buna bağlı.

**Kaynak başına granülarite:**

| Kaynak | Partition | Neden |
|---|---|---|
| `market/` | year/month/day | Günlük gerçek çekim, gün bazlı margin hesabı yapılacak |
| `market_synthetic/` | year/month (cari ay: year/month/day) | Geçmiş dönem için sentetik market fiyatı (TÜFE + mevsim modeli); cari ay günlük, geçmiş aylar aylık tek dosya; `_synthetic=True` flag ile işaretli |
| `hal_all/` | year/month | 81 il × 2016-2026 backfill; gerçek+sentetik karma, `veri_turu` kolonu ile işaretli; Silver'da birincil hal kaynağı |
| `gdelt/` | year/month/day | 15dk kayıtlar gün bazlı birleştirilir — küçük dosya sorununu önler |
| `akaryakit/` | year/month/day | Günlük fiyat değişimi |
| `epias/{dataset}/` | year/month | Saatlik → aylık birleştirme (26 dataset × aylık = yönetilebilir dosya sayısı) |
| `tcmb/{series}/` | year/month | Seri bazlı aylık; her seri ayrı prefix altında |
| `commodities/` | year/month | Yeterli granülarite |
| `weather/` | year/month | Tüm şehirler aynı ay için tek dosyada (81 şehir × aylık) |

**Niye Parquet?** JSON/CSV'ye göre 5-10x daha küçük, sütun bazlı okunduğu için çok daha hızlı. 200GB JSON → ~25GB Parquet.

**Flatten ne demek?** Market verisindeki iç içe listeler açılır, her depot için ayrı satır olur:

```
Önce (JSON):  {"title": "Domates", "depots": [{"id": "bim-1", "price": 45}, ...]}
Sonra (flat): title="Domates" | depot_id="bim-1" | price=45 | city="İstanbul"
```

**Parquet yazma (boto3/Spark):**

```python
df.coalesce(1).write \
  .mode("append") \
  .partitionBy("year", "month", "day") \
  .parquet("s3://bucket/bronze/market/")
```

---

### 2b. Backfill Stratejisi

Scraper'ların geçmiş verisi önce bu PC'ye çekilir, ardından boto3 ile doğrudan S3'e yüklenir. NiFi sadece güncel (canlı) veriyi yönetir; backfill tek seferlik manuel işlemdir.

**Yükleme akışı:**

```
Yerel PC (ham CSV/JSON)
    → pandas ile oku
    → Parquet'e dönüştür (Hive partition sütunları ekle: year, month, day)
    → boto3 / s3fs ile s3://bucket/bronze/{kaynak}/year=.../month=.../day=.../ yükle
```

**Backfill öncelik sırası (pandemi gap analizi için kritik):**

| Öncelik | Dönem | Neden |
|---|---|---|
| 1 | 2019-01 → 2020-02 | Pandemi öncesi baseline |
| 2 | 2020-03 → 2021-12 | Pandemi dönemi — fiyat şoku |
| 3 | 2022-01 → 2023-12 | Enflasyon zirvesi |
| 4 | 2024-01 → bugün | Güncel, scraper zaten çekiyor |

**Chunk boyutu:** 1 ay = 1 yükleme turu. Hocanın beklentisi: EMR açılır, 1 aylık Bronze işlenir, EMR kapanır. Chunk çok büyük olursa EMR açık kalma süresi ve maliyeti artar.

**Hedef dosya boyutu:** Her Parquet dosyası 128MB–512MB arası olmalı (Spark block size ile uyumlu). Günlük hal/market verisi bunun altında kalıyorsa `coalesce(1)` ile tek dosya yaz, birleştirme yapma.

---

### 3. Silver Layer (Spark → S3)

Spark S3 Bronze'dan okur, DataFrame olarak işler (RAM'de geçici tablo gibi), temizlenmiş veriyi S3 Silver'a yazar.

İşlemler:
- **Hal merge** — `hal_istanbul` (geçmiş backfill) + `hal_harman` (çok şehirli, güncel) birleştirilir; aynı `date + city + product` için `hal_harman` öncelikli; `source` kolonu eklenir
- **Entity resolution** — hal `"Domates Sofralık Sera"` ↔ market `"Domates 1 Kg"` eşleştirmesi (embedding tabanlı, Qwen/sentence-transformers)
- **Unit normalizasyon** — `"Kasa"`, `"Bağ"`, `"350 Gr"` → KG'a çevrim
- **Join** — tüm kaynaklar (hal + market + GDELT + EPİAŞ + TCMB) tarih ve şehir bazında birleştirilir

```
s3://bucket/silver/
  hal/year=YYYY/month=MM/day=DD/*.parquet       <- hal_istanbul + hal_harman merge
  margin_enriched/YYYY-MM-DD/*.parquet
```

---

### 4. Gold Layer (Spark → S3)

Spark Silver'dan okur, analiz hazır tablolar üretir:

- **Margin tablosu** — hal fiyatı vs. raf fiyatı farkı, şehir ve ürün bazında
- **Shock propagation index** — GDELT haberi ile hal/market fiyatı arasındaki gecikme süresi
- **Zaman serisi** — Prophet ile fiyat tahmini, pandemi öncesi/sonrası gap analizi

```
s3://bucket/gold/
  daily_margin/*.parquet
  shock_index/*.parquet
  price_forecast/*.parquet
```

---

### 5. Elasticsearch

Gold layer Parquet'leri Elasticsearch'e index'lenir. Kalıcı sorgulama ve arama buradan yapılır.

---

### 6. Superset Dashboard

Elasticsearch'e bağlı görselleştirme. Margin haritaları, fiyat trend grafikleri, shock event timeline.

---

## Özet

```
NiFi → [Kafka] → S3 Bronze (ham Parquet)
                      ↓
                   Spark
              (entity resolution,
               unit norm, join)
                      ↓
               S3 Silver (temiz Parquet)
                      ↓
                   Spark
              (margin, shock index,
               tahmin)
                      ↓
               S3 Gold (analiz Parquet)
                      ↓
              Elasticsearch → Superset
```

**Spark'ta DB var mı?** Hayır, kalıcı DB değil. Spark Parquet'i okuyunca RAM'de geçici tablo (DataFrame) oluşturur, SQL yazılabilir, işlem bitince S3'e yazar, kapanır. Elasticsearch ise kalıcı sorgulama DB'si.
