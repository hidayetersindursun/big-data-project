# Market Silver Geçişi — Notlar

## Bronze Kaynaklar

| Path | Kapsam | Partition | Boyut | Satır |
|---|---|---|---|---|
| `s3://s3-bbuckett/bronze/market` | 2026+ gerçek scrape | `year/month/day` | ~15 MB | ~875K |
| `s3://s3-bbuckett/bronze/market_synthetic` | 2019-2025 sentetik | `year/month` | ~5.5 GB | ~tahmin 100M+ |

**Not**: `market_synthetic` diğer tüm kaynaklardan çok daha büyük — gold join'larında performansa dikkat.

---

## Bronze Şema Karşılaştırması

| Kolon (bronze) | market | market_synthetic | Silver'da |
|---|---|---|---|
| `id` | ✅ | ✅ | **Atıldı** (scraper iç ID) |
| `title` | ✅ | ✅ | → `product_name` |
| `brand` | ✅ | ✅ | korundu |
| `imageUrl` | ✅ | ✅ | **Atıldı** |
| `refinedVolumeOrWeight` | ✅ | ✅ | → `volume_weight` |
| `main_category` | ✅ | ✅ | → `category` |
| `menu_category` | ✅ | ✅ | **Atıldı** (`main_category` yeterli) |
| `_district` | ✅ | ✅ | → `district` |
| `_city` | ✅ | ✅ | → `city` |
| `_scraped_at` | ✅ | ✅ | → `date` (DATE), sonra **Atıldı** |
| `categories` | ✅ | ✅ | **Atıldı** (verbose breadcrumb string) |
| `depotId` | ✅ | ✅ | korundu |
| `depotName` | ✅ | ✅ | korundu |
| `price` | ✅ | ✅ | korundu (TL, ürünün satış fiyatı) |
| `unitPrice` | ✅ | ✅ | → `unit_price_str` ("270,00 ₺/Kg" gibi) |
| `unitPriceValue` | ✅ | ✅ | → `unit_price_value` (numeric) |
| `marketAdi` | ✅ | ✅ | → `market_name` |
| `percentage` | ✅ | ✅ | **Atıldı** (gözlemlenen tüm satırlarda 0.0) |
| `longitude` / `latitude` | ✅ | ✅ | korundu (spatial join için) |
| `indexTime` | ✅ | ✅ | **Atıldı** (`_scraped_at` ile aynı, farklı format) |
| `discount` | ✅ | ✅ | korundu (indirim flag'i — fiyat sinyali kalitesi) |
| `discountRatio` | ✅ | ✅ | **Atıldı** (büyük çoğunluk null) |
| `promotionText` | ✅ | ✅ | **Atıldı** (büyük çoğunluk null) |
| `refinedQuantityUnit` | ✅ | ✅ | **Atıldı** (büyük çoğunluk null) |
| `_synthetic` | ❌ | ✅ (True) | → `source_type` ("real"/"synthetic"), sonra **Atıldı** |
| `_base_date` | ❌ | ✅ | **Atıldı** (sentetik üretim referans tarihi) |
| `year` / `month` / `day` | ✅ (partition) | ✅ (partition) | `date`'den yeniden üretildi |

---

## Silver Hedef Şema

```
silver/market_prices/
  year={yıl}/month={ay}/part-*.parquet
```

| Kolon | Tip | Açıklama |
|---|---|---|
| `date` | DATE | Scrape tarihi |
| `year` | int | Partition |
| `month` | int | Partition |
| `city` | string | Şehir (scraper'dan geldiği haliyle) |
| `district` | string | İlçe |
| `product_name` | string | Ürün adı (ham, Title Case değil) |
| `brand` | string | Marka |
| `category` | string | Ana kategori (`main_category`) |
| `market_name` | string | Zincir adı (`bim`, `a101`, vb.) |
| `depotId` | string | Mağaza ID |
| `depotName` | string | Mağaza adı |
| `price` | double | Ürün fiyatı (TL) |
| `unit_price_value` | double | Birim fiyat numeric (TL/Kg veya TL/adet) |
| `unit_price_str` | string | Birim fiyat string ("270,00 ₺/Kg") — birim tipini taşır |
| `volume_weight` | string | Ürün hacim/ağırlık ("50 GR", "1 KG", "6 ADET") |
| `discount` | boolean | İndirimde mi? |
| `latitude` | double | Mağaza enlemi |
| `longitude` | double | Mağaza boylamı |
| `source_type` | string | `"real"` veya `"synthetic"` |
| `source` | string | `"market"` (sabit) |

---

## Önemli Tespitler

### `unit_price_value` nedir?
`unitPriceValue`, scraper'ın API'den çektiği birim fiyat değeridir. **Her ürünün ağırlık/hacmine normalize edilmiş TL fiyatıdır** — "Soğan 1 Kg → 2.25 ₺/Kg", "Hindi Salam 50 Gr → 270 ₺/Kg" gibi. Bu değer **hal fiyatları ile doğrudan karşılaştırılabilir** ve Gold'daki margin hesabının temelidir.

Ancak bazı ürünler "Adet" veya "Paket" bazındadır. `unit_price_str` kolonu bu ayrımı taşır. Gold'da `hal_prices` ile join yaparken yalnızca `"₺/Kg"` içeren satırlar kullanılmalı.

### `product_name` standardizasyonu
Ham ürün adı Silver'da değiştirilmedi — Title Case bile uygulanmadı. Hal ürün adları ile fuzzy match (TF-IDF) Gold'da yapılacak. Silver'da müdahale edilirse eşleşme kalitesi düşer.

### Sentetik veri payı
`market_synthetic` gerçek veriden çok daha büyük (~100M+ satır tahmin). Gold'da analizlerde `source_type = "real"` filtresi kritik — sentetik veriler yalnızca 2019-2025 gap'ini doldurmak için kullanılır.

### `discount = True` satırları
İndirimli fiyatlar gerçek piyasa fiyatını yansıtmaz. Gold'da margin analizi için `discount = False` filtresi uygulanmalı.

---

## Atılan Kolonlar — Nedenler

| Kolon | Neden atıldı |
|---|---|
| `id` | Scraper'ın iç ID'si, analitik değeri yok |
| `imageUrl` | Görsel URL, analiz için gereksiz |
| `indexTime` | `_scraped_at` ile birebir aynı, farklı format ("12.05.2026 07:50") |
| `percentage` | Tüm gözlemlenen satırlarda 0.0 |
| `categories` | Uzun breadcrumb string ("10-meyve Sebze, Meyve Ve Sebzeler..."), `category` yeterli |
| `menu_category` | `main_category` ile örtüşüyor, fazlalık |
| `discountRatio` | Büyük çoğunluk null |
| `promotionText` | Büyük çoğunluk null |
| `refinedQuantityUnit` | Büyük çoğunluk null |
| `_base_date` | Sentetik verinin üretildiği referans tarih — `source_type` yeterli |

---

## Süre Tahmini

`market_synthetic` 5.5 GB sıkıştırılmış Parquet — işlenmiş hali ~20-30 GB olabilir. Local Spark ile **30-60 dakika** arasında sürmesi beklenir. Bu script için EMR Serverless düşünülebilir; diğer scriptlerle kıyaslandığında açık ara en uzun sürecek olan budur.

---

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/market_silver.py
```

---

## Gold'a Geçiş İçin Notlar

- **Ana join**: `silver/market_prices` ↔ `silver/hal_prices` — `product_name` ↔ `hal.product_name` fuzzy match
- **Fiyat sinyali**: `unit_price_value` WHERE `unit_price_str LIKE '%/Kg'` AND `discount = False`
- **Margin hesabı**: `(unit_price_value - hal.price_avg) / hal.price_avg` — perakende-hal marjı
- **Sentetik filtresi**: Historik trend analizi için `source_type IN ('real', 'synthetic')`, anlık analiz için `source_type = 'real'`
- **Spatial join**: `latitude`/`longitude` → en yakın hal ile eşleştirme (Haversine distance)
- **Rockets & Feathers testi**: Hal fiyatı artışında `unit_price_value` ne kadar hızlı yukarı gidiyor, düşüşte ne kadar yavaş?
