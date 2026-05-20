# Akaryakıt — günlük yakıt fiyatları (81 şehir)

## Ne işe yarar?

Türkiye'nin 81 şehri için günlük benzin, motorin, LPG fiyatlarını çeker. Veri kaynağı: `hasanadiguzel.com.tr/api/akaryakit/sehir={şehir}` (resmi olmayan ama yıllardır stabil bir mirror).

## Projemizdeki rolü

Akaryakıt fiyatları **gizli bir maliyet kalemidir** ve fiyat zincirinin her aşamasında etki eder:

- **Üretici → hal lojistiği**: Sera/tarladan hale taşıma maliyeti.
- **Hal → market**: Soğuk zincir (kamyon, depo) maliyeti.
- **Şehirler arası fiyat farkı**: Uzak şehirler (Hakkâri, Şırnak) merkeze daha pahalı.

Gold tarafında `shock_propagation` ve potansiyel `transportation_cost_passthrough` analizlerinde kullanılır — yakıt fiyatı sıçramasının kaç gün sonra raf fiyatına yansıdığı.

## Çalıştırma

```bash
python ingestion/akaryakit/gunluk_akaryakit_scraper.py
```

Çıktı: `ingestion/akaryakit/data/akaryakit_{tarih}.json`

## Schema

Bronze Parquet `bronze/akaryakit/year=YYYY/month=MM/day=DD/`:

| Alan | Tip | Açıklama |
|---|---|---|
| Tarih | string DD.MM.YYYY | scrape tarihi |
| İl | string (ALL CAPS) | il adı (İSTANBUL, ANKARA, ...) |
| Marka | string | Petrol Ofisi / OPET / Shell / BP / Total |
| Yakıt Tipi | string | Kurşunsuz 95, Motorin EuroDiesel, LPG, ... |
| Fiyat | double | TL/litre |
| _ingested_at | string ISO | scrape timestamp |

## Bilinen kısıtlar

- API bazı şehir isimlerini Türkçe karakter, bazılarını latinize halinde kabul ediyor. `cities_map` script içinde sabit.
- Tarihsel veri sadece XLS dosyaları olarak mevcut; ilk scrape sonrası sadece güncel veri çekilir.
- Rate limit yok ama nazik ol — 81 şehir için her şehir arası 0.5-1 saniye delay konulmuş.

## Backfill

XLS dosyaları daha önce manuel olarak `data/` altına indirilmiş; `upload_to_s3.py process_akaryakit()` bunları Parquet'e çevirip Bronze'a yükler.
