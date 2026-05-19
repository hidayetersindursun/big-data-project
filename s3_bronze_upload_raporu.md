# S3 Bronze Layer — Upload Raporu

**Bucket:** `s3://s3-bbuckett/bronze/`  
**Son güncelleme:** 2026-05-19  
**Proje:** Turkey Food Supply Chain Transparency and Spatial Margin Analysis Engine

---

## Yüklenen Veri Kaynakları

| Kaynak | S3 Yolu | Format | Partition | Dosya | Ham Boyut | Parquet | Sıkıştırma |
|--------|---------|--------|-----------|-------|-----------|---------|------------|
| **hal_all** | `bronze/hal_all/` | CSV → Parquet | year/month | 132 | 1.028 MB | 61.7 MB | **16.7x** |
| **epias** | `bronze/epias/` | JSONL → Parquet | dataset/year/month | 1.731 | 254.3 MB | 41.4 MB | **6.1x** |
| **akaryakit** | `bronze/akaryakit/` | JSONL → Parquet | year/month/day | 1.285 | 97.6 MB | 7.8 MB | **12.5x** |
| **weather** | `bronze/weather/` | JSONL → Parquet | year/month | 125 | 33.0 MB | 17.2 MB | **1.9x** |
| **tcmb** | `bronze/tcmb/` | JSONL → Parquet | series/year/month | 613 | 0.3 MB | 1.3 MB | — |
| **commodities** | `bronze/commodities/` | JSONL → Parquet | year/month | 77 | 3.5 MB | 1.0 MB | **3.5x** |
| **market_synthetic** | `bronze/market_synthetic/` | JSONL → Parquet | year/month | 57+ | — | 3.200 MB | — |
| **gdelt** | `bronze/gdelt/` | JSONL → Parquet | year/month/day | 2 | 253.0 MB\* | 33.6 MB | — |
| **market** | `bronze/market/` | JSONL → Parquet | year/month/day | 7 | 591.2 MB | 14.8 MB | — |

> \* GDELT lokal boyutu yalnızca 2016-01-01 tek günü kapsar; 10 yıllık backfill devam ediyor.  
> market_synthetic ham boyutu ölçülmedi (sentetik üretim + upload tek adımda yapıldı).  
> Sıkıştırma oranı `—` olanlar henüz tam backfill tamamlanmamış veya lokal kaynak ölçülmemiş kaynaklardır.

---

## Neden Parquet?

Parquet **sütun bazlı** bir format olduğu için:

- Gereksiz sütunlar diskte okunmaz → I/O maliyeti düşer
- Tip bazlı sıkıştırma (RLE, dictionary encoding) JSON/CSV'ye göre 5–17x daha küçük dosya üretir
- Spark `WHERE year=2024 AND month=3` yazdığında sadece ilgili partition klasörünü okur, tüm Bronze taranmaz
- **EMR maliyeti doğrudan dosya boyutu ve okuma süresine bağlı**

---

## Partition Stratejisi

| Granülarite | Kaynaklar | Neden |
|-------------|-----------|-------|
| `year/month/day` | market, hal_istanbul, hal_harman, akaryakit, gdelt | Günlük margin hesabı yapılacak; gün bazlı sorgu kritik |
| `year/month` | hal_all, epias, tcmb, commodities, weather, market_synthetic | Günlük granülarite gerekmez; aylık birleştirme dosya sayısını makul tutar |
| `dataset/year/month` | epias | 26 farklı dataset; her dataset ayrı prefix altında |
| `series/year/month` | tcmb | Her TCMB serisi (kur, enflasyon vb.) ayrı prefix altında |

---

## hal_all Detayı

**Kaynak:** `ingestion/hal/tum_hal_data/{şehir}/{yıl}.csv`  
**Kapsam:** 81 il × 2016–2026 = 891 CSV dosyası, ~19 milyon satır  
**Schema:** `tarih, sehir, urun, kategori, en_dusuk, en_yuksek, veri_turu`  
**veri_turu değerleri:** `gercek` (10 şehir için gerçek hal verisi) / `sentetik` (71 şehir)

| Şehir | Gerçek Veri Yılları |
|-------|---------------------|
| Bursa, İstanbul, İzmir, Gaziantep, Konya | 2016–2026 |
| Adana | 2019–2026 |
| Manisa | 2020–2026 |
| Antalya, Kocaeli, Tekirdağ | 2021–2026 |
| Diğer 71 il | Tamamı sentetik |

Parquet'e dönüşümde **16.7x sıkıştırma** elde edilmiştir:  
`1.028 MB CSV → 61.7 MB Parquet`

---

## Devam Eden / Planlanan Yüklemeler

| Kaynak | Durum | Notlar |
|--------|-------|--------|
| market_synthetic | 🔄 Devam ediyor | 2019–2026 aylık Parquet, ~5GB tahmini |
| gdelt | ⏳ Planlandı | 2016-01-02 → 2026-05-09, 7 paralel BigQuery worker |
| hal_istanbul | ⏳ Planlandı | Günlük scraper canlıya alınacak |
| hal_harman | ⏳ Planlandı | Günlük scraper canlıya alınacak |
| market | ⏳ Planlandı | Günlük scraper backfill + canlı |

---

## Otomatik Log

Her upload sonrası `upload_log.jsonl` dosyasına satır eklenir:

```json
{"ts": "2026-05-19T...", "source": "hal_all", "bucket": "s3-bbuckett", "orig_mb": 1028, "parquet_mb": 61.7, "compression_x": 16.7}
```

Okumak için:
```powershell
Get-Content upload_log.jsonl | ConvertFrom-Json | Format-Table source, orig_mb, parquet_mb, compression_x, ts
```
