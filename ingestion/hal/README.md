# Hal — Toptan sebze meyve fiyatları

## Ne işe yarar?

Türkiye'nin hal (toptan) fiyatlarını toplar — domates, salatalık, biber, elma, vb. ürünlerin **toptan satış fiyatı** (genelde kg cinsinden). Bu fiyat, market raf fiyatının "girdi" tarafıdır; marjı hesaplayabilmek için kritik.

## Yapısı

Üç alt klasör var, her biri farklı kaynaktan veri çeker:

### 1. `istanbul/` — İBB Tarım'ın günlük yayını

- Kaynak: https://tarim.ibb.istanbul/ (Selenium + headless Chrome)
- Kapsam: İstanbul Bayrampaşa + Ataşehir hali, günlük
- Tarihsel: 2016-2026 tam
- Çalıştırma: `python ingestion/hal/istanbul/ist_gunluk_hal_fiyat_scraber.py`
- Çıktı: çalıştığı klasöre `istanbul_hal_fiyat_{tarih}.csv`

### 2. `harman/` — Harmanapps multi-city

- Kaynak: https://harmanapps.com (`curl_cffi` ile Cloudflare bypass)
- Kapsam: 10 şehir (Bursa, İstanbul, İzmir, Gaziantep, Konya, Adana, Manisa, Antalya, Kocaeli, Tekirdağ)
- Tarihsel: değişken — Bursa/İzmir/Gaziantep/Konya 2016+, Adana 2019+, Manisa 2020+, Antalya/Kocaeli/Tekirdağ 2021+
- Çalıştırma: `python ingestion/hal/harman/harman_gunluk_hal_fiyat_scraber.py`
- Çıktı: `harman_hal_fiyat_{DD_MM_YYYY}.csv`

### 3. `tum_hal_data/` — 81 şehir canonical tablo (real + synthetic)

Bu, **Silver/Gold için kullanılan asıl Bronze kaynağıdır**.

- Yapı: `tum_hal_data/{şehir}/{yıl}.csv`
- Kapsam: **81 şehir × 2016-2026 = 891 CSV** (~19M satır)
- 10 şehir gerçek veri (istanbul + harman üzerinden), 71 şehir sentetik
- Sentetik: gerçek 10 şehrin yıl/ürün/ay ortalaması + TÜFE deflation + mevsim profilleri + noise
- `veri_turu` kolonu ile gerçek/sentetik ayrımı yapılır

#### Şehir kapsama (gerçek veri)

| Şehir | Yıllar |
|---|---|
| Bursa, İstanbul, İzmir, Gaziantep, Konya | 2016–2026 |
| Adana | 2019–2026 |
| Manisa | 2020–2026 |
| Antalya, Kocaeli, Tekirdağ | 2021–2026 |
| Diğer 71 il | Tamamı sentetik |

#### Schema

Bronze Parquet `bronze/hal_all/year=YYYY/month=MM/`:

| Alan | Tip | Açıklama |
|---|---|---|
| tarih | string YYYY-MM-DD | satır tarihi |
| sehir | string | il adı (Title Case TR) |
| urun | string (UPPERCASE TR) | ürün adı (örn. "DOMATES SOFRALIK SERA") |
| kategori | string | sebze / meyve (çoğu null) |
| en_dusuk | double | TL/kg minimum |
| en_yuksek | double | TL/kg maksimum |
| veri_turu | string | `gercek` veya `sentetik` |

#### Silver tarafında

`silver/hal_prices/`:
- `price_avg = (en_dusuk + en_yuksek) / 2`
- `product_name = initcap(lower(trim(urun)))`
- `source_type = veri_turu`

## Bilinen kısıtlar

- İBB ve Harman ürün isimleri farklı yazılım — `MARUL (DÜZ)` vs `MARUL DÜZ`. Sunum öncesi unification şart (Silver'da yapılır).
- `kategori` çoğu satırda null — Silver'da `Bilinmiyor` ile doldurulur.
- Sentetik veri pandemi dönemi için kullanılırken net "synthetic" disclaimer eklenmelidir (sunumda söylenecek).

## Geçmiş artifact

`hal_data.md` orijinal araştırma notları; bu README onu netleştirir.
