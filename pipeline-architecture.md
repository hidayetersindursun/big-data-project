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
  market/YYYY-MM-DD/*.parquet
  hal/YYYY-MM-DD/*.parquet
  gdelt/YYYY-MM-DD/*.parquet
  epias/YYYY-MM-DD/*.parquet
  tcmb/YYYY-MM-DD/*.parquet
```

**Niye Parquet?** JSON/CSV'ye göre 5-10x daha küçük, sütun bazlı okunduğu için çok daha hızlı. 200GB JSON → ~25GB Parquet.

**Flatten ne demek?** Market verisindeki iç içe listeler açılır, her depot için ayrı satır olur:

```
Önce (JSON):  {"title": "Domates", "depots": [{"id": "bim-1", "price": 45}, ...]}
Sonra (flat): title="Domates" | depot_id="bim-1" | price=45 | city="İstanbul"
```

---

### 3. Silver Layer (Spark → S3)

Spark S3 Bronze'dan okur, DataFrame olarak işler (RAM'de geçici tablo gibi), temizlenmiş veriyi S3 Silver'a yazar.

İşlemler:
- **Entity resolution** — hal `"Domates Sofralık Sera"` ↔ market `"Domates 1 Kg"` eşleştirmesi (embedding tabanlı, Qwen/sentence-transformers)
- **Unit normalizasyon** — `"Kasa"`, `"Bağ"`, `"350 Gr"` → KG'a çevrim
- **Join** — tüm kaynaklar (hal + market + GDELT + EPİAŞ + TCMB) tarih ve şehir bazında birleştirilir

```
s3://bucket/silver/
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
