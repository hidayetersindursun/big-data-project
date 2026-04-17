# ingestion/

marketfiyati.org.tr'den perakende fiyat verisi çeken asenkron paralel scraper.

## Kurulum

```bash
pip install curl_cffi tenacity
```

## İlk Kurulum (Bir Kez)

Günlük scraping'den önce her ilçenin tam depot listesini oluştur:

```bash
# İstanbul'un tüm ilçeleri için depot veritabanı kur
python ingestion/setup_depots.py --city İstanbul

# Tüm şehirler
python ingestion/setup_depots.py

# Depot listesi eskidiyse yenile
python ingestion/setup_depots.py --city İstanbul --force
```

Bu adım `ingestion/depots/` klasörüne her ilçe için bir JSON dosyası üretir (örn. `İstanbul_Beşiktaş.json`). İlçe merkezinden tek noktadan sorgu yapılsaydı Beşiktaş için 14 depot görülürdü; grid search ile **629 unique depot** elde edilir.

> **Not:** setup_depots.py üç fazda çalışır:
> 1. **Nominatim (sequential)** — ilçe başına gerçek OSM bbox'ı çeker (1.1s aralık, rate limit uyumlu)
> 2. **Koordinat fallback (parallel)** — bbox alınamayan ilçeler için merkez koordinatı
> 3. **Grid search (parallel)** — adaptif grid ile /nearest sorguları

## Günlük Çalıştırma

```bash
# Tüm şehirleri çek (24 saatten bayat olanları günceller, taze olanları atlar)
python ingestion/scraper.py

# İstanbul — tüm ilçeler paralel
python ingestion/scraper.py --city İstanbul

# Eşzamanlı HTTP istek sayısını ayarla (default: 10)
python ingestion/scraper.py --city İstanbul --concurrency 10

# Her şeyi zorla yeniden çek
python ingestion/scraper.py --force

# Filtreler (kombinlenebilir)
python ingestion/scraper.py --city İstanbul --district Beşiktaş
python ingestion/scraper.py --city İzmir --district Bornova --category Sebze
python ingestion/scraper.py --category Meyve
```

## Modüller

| Dosya | Sorumluluk |
|---|---|
| `config.py` | İller, ilçeler, kategoriler, API URL'leri ve zamanlama ayarları |
| `client.py` | HTTP API çağrıları — sync (depot_grid) ve async (scraper) versiyonlar |
| `state.py` | `state.json`'ı okur/yazar; verinin bayatlığını kontrol eder |
| `setup_depots.py` | Bir kez çalıştırılan grid search — ilçe başına tam depot listesi üretir |
| `scraper.py` | Ana orkestratör — async paralel scraping, JSONL yazar |
| `depot_grid.py` | Tekil ilçe için interaktif grid search (setup_depots.py'nin alt yapısı) |

## Scraping Mimarisi

### Neden Depot Listesi Ayrı Çekiliyor?

`/searchByCategories` endpoint'i `depots` parametresini zorunlu tutar:

```json
POST /searchByCategories
{
  "keywords": "Meyve",
  "depots": ["migros-4941", "migros-3821", ...],  ← zorunlu
  "pages": 0
}
```

Depot listesi olmadan ürün fiyatı çekilemiyor. `setup_depots.py` bu listeyi bir kez oluşturur; `scraper.py` her gün JSON'dan okuyarak direkt `/searchByCategories`'e geçer — günlük depot discovery maliyeti sıfır.

### Cross-İlçe Duplicate (Bronze → Silver)

Bir market şubesi ilçe sınırında olabilir — hem Beşiktaş hem Şişli grid search'ünde aynı `depotId` yakalanır. Scraper bunu olduğu gibi yazar:

```
İstanbul_Beşiktaş/2026-04-10/Meyve.jsonl  ← migros-4941 fiyatları
İstanbul_Şişli/2026-04-10/Meyve.jsonl     ← aynı migros-4941 fiyatları
```

**Bronze'da duplicate kasıtlı tutulur** — ham veri değiştirilmez.

**Silver'da temizlenir:**
```sql
SELECT DISTINCT depot_id, product_id, price, date
FROM bronze.market_prices
```

`_district` etiketi deponun gerçek konumunu değil, hangi scrape job'ından geldiğini gösterir. Deponun gerçek konumu için `depot.lat / depot.lon` kullanılır.

### Neden Grid Search?

marketfiyati.org.tr API'si konum bazlı çalışır: "bana bu koordinata yakın depotları ver." Tek bir ilçe merkezi koordinatından sorgu yapılırsa ilçenin yalnızca merkezi görülür, uzak mahalleler kaçar.

```
İlçe merkezi (tek nokta) → /nearest(radius=1km) → 14 depot   ❌ eksik
Grid search (örn. 169 pt) → /nearest → 629 depot             ✓ tam kapsam
```

### Adaptif Grid (setup_depots.py)

Sabit bounding box (±0.03°) tüm ilçelere uygulanamaz — ilçe boyutları çok farklıdır:

| İlçe | Alan | Sabit ±0.03° kapsam |
|---|---|---|
| Beyoğlu | ~9 km² | Fazlasıyla yeterli, gereksiz istek |
| Beşiktaş | ~16 km² | Yeterli |
| Beykoz | ~302 km² | ~%5 görünür — büyük kayıp |
| Çatalca | ~1.400 km² | ~%1 görünür — neredeyse boş |

**Çözüm:** Nominatim (OSM) ile gerçek ilçe bbox'ı alınır, ardından adaptif grid:

```
Bbox alanı (km²) → step = max(0.005°, √(alan / 150))
                 → radius = max(1km, step_km)   ← gap garantisi: radius ≥ step
                 → grid noktaları yalnız bbox içinde
```

- Küçük ilçe (9 km²): ~9 nokta, r=1km
- Orta ilçe (100 km²): ~100 nokta, r=1km
- Büyük ilçe (1400 km²): ~150 nokta, r≈3km (kaba ama tam kapsam)

**Gap garantisi:** `radius = step` olduğunda, her kare hücrenin köşegeni `step × √2/2 < step` olduğundan tüm noktalar en az bir daire tarafından kapsanır.

### Scrape Akışı

```
[setup_depots.py — bir kez]
Phase 1 (sequential): Nominatim → gerçek bbox / ilçe  [1.1s aralık]
Phase 2 (parallel):   koordinat API fallback (bbox alınamayan ilçeler)
Phase 3 (parallel):   adaptif grid noktaları → /nearest(radius=adaptif)
    → depotId ile deduplicate
    → depots/{şehir}_{ilçe}.json

[scraper.py — günlük]
depots/{şehir}_{ilçe}.json  ←─ varsa kullan (hızlı, tam kapsam)
    yoksa → /AutoSuggestion + /nearest fallback (14 depot, sadece merkez)
    → her kategori için /searchByCategories(depot_ids, page=0,1,2,…)  [tüm kategoriler paralel]
    → sayfalama: page_size=25 (API hard limit), toplam ürüne ulaşana kadar
    → JSONL: ingestion/data/{şehir}_{ilçe}/YYYY-MM-DD/{kategori}.jsonl
```

### Paralellik

- **İlçe düzeyi**: tüm ilçeler `asyncio.gather` ile eş zamanlı başlar
- **Kategori düzeyi**: aynı ilçedeki 7 kategori de eş zamanlı çalışır
- **Throttling**: `asyncio.Semaphore(concurrency)` ile max eşzamanlı HTTP isteği sınırlanır
- **TLS Fingerprint**: `curl_cffi` ile Chrome124 impersonation — anti-bot korumasını geçer
- **Rate limit**: `tenacity` exponential backoff (3s→6s→12s…), 429 HTTP ayrıca tespit edilir

### API Kısıtları

- Sayfa başına max 25 ürün (`size` parametresi API tarafından görmezden gelinir)
- `/nearest` yalnızca sorgu noktasına yakın depotları döndürür → grid search zorunluluğu
- Rate limiting: arka arkaya çok sorgu → `RemoteDisconnected` → exponential backoff

## Çıktı Formatı

```
ingestion/data/
└── {şehir}_{ilçe}/
    └── YYYY-MM-DD/
        ├── Meyve.jsonl
        ├── Sebze.jsonl
        └── ...
```

Her satır bir ürün kaydı:

```json
{
  "id": "1CTA",
  "title": "Nutella&go ...",
  "brand": "Nutella",
  "refinedVolumeOrWeight": "28 GR",
  "categories": [...],
  "main_category": "...",
  "productDepotInfoList": [
    {"depotId": "migros-4941", "price": 25.5, "unitPrice": "910,71 ₺/Kg"}
  ],
  "_district": "Beşiktaş",
  "_city": "İstanbul",
  "_scraped_at": "2026-04-10T14:30:00"
}
```

Tarih bazlı partition (`YYYY-MM-DD/`) Spark'ta `WHERE date=...` ile verimli okuma sağlar.

## Depot Veritabanı

```
ingestion/depots/
├── İstanbul_Beşiktaş.json   # 629 unique depot
├── İstanbul_Kadıköy.json
└── ...
```

Her kayıt:
```json
{"id": "migros-4941", "name": "Migros Beşiktaş", "market": "Migros", "lat": 41.05, "lon": 29.01}
```

## State Yönetimi

`state.json` (proje kökünde) hangi `(ilçe, şehir, kategori)` kombinasyonunun ne zaman çekildiğini tutar. Varsayılan tazelik süresi: **24 saat** (`config.py` → `STALE_HOURS`).

Tekrar çalıştırıldığında taze veriler atlanır; sadece bayat olanlar güncellenir.

## Yeni İl Eklemek

`config.py`'deki `CITIES` dict'ine bir satır ekle, ardından setup_depots'u çalıştır:

```python
# config.py
CITIES = {
    "İstanbul": [...],
    "İzmir":    [...],
    "Ankara":   ["Çankaya", "Keçiören", "Mamak", "Yenimahalle"],  # ← yeni
}
```

```bash
python ingestion/setup_depots.py --city Ankara
python ingestion/scraper.py --city Ankara
```
