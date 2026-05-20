# Akaryakıt Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/akaryakit/`
- **Yapı**: `year={yil}/month={ay}/day={gun}/part-0000.parquet`
- **Kapsam**: 2016 → 2026 (11 yıl, 1.285 dosya)
- **Boyut**: ~7.8 MiB

## Bronze Şeması (Ham)

| Sütun | Tip | Notlar |
|---|---|---|
| `Tarih` | string | `DD.MM.YYYY` formatı — Türkçe format |
| `İl` | string | ALL CAPS Türkçe şehir adı |
| `Marka` | string | Akaryakıt markası (BP, Shell, vb.) |
| `Yakıt Tipi` | string | Uzun Türkçe yakıt tipi açıklaması |
| `Fiyat` | double | TL cinsinden litre fiyatı |

## Silver Hedef

- **Path**: `s3://s3-bbuckett/silver/akaryakit/`
- **Yapı**: `date={YYYY-MM-DD}/part-*.parquet`
- **Script**: `processing/silver/akaryakit_silver.py`
- **Mod**: `append` — günlük yeni veri eklenir, mevcut silinmez

## Mimari Kararlar

- `Tarih` (DD.MM.YYYY) → `date` (DATE) standart formata çevrildi
- `İl` ALL CAPS → `city` Title Case standardizasyonu
- Sütun adları Türkçe büyük harften İngilizce snake_case'e geçirildi
- Gold'da nakliye maliyeti hesabı için `fuel_type` ve `city` korundu

## Silver akaryakit — Final Tablo

| Sütun | Tip | Örnek |
|---|---|---|
| `date` | DATE | `2026-01-01` |
| `city` | string | `Adana` |
| `brand` | string | `BP` |
| `fuel_type` | string | `Kurşunsuz Benzin 95 Oktan` |
| `price_tl` | double | `54.98` |
| `source` | string | `akaryakit` |

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/akaryakit_silver.py
```
