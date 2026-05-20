# TCMB Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/tcmb/`
- **Yapı**: `{seri_adi}/year={yil}/month={ay}/part-0000.parquet`
- **Toplam seri sayısı**: 22
- **Boyut**: ~1.3 MiB

## Bronze'da Mevcut Veriler — Seri Detayları

Her seri **3 sütunlu** tek bir Parquet şemasına sahip:

| Sütun | Tip | Notlar |
|---|---|---|
| `date` | string | Günlük seriler: `DD-MM-YYYY` / Aylık seriler: `YYYY-MM` |
| `value` | double | Seri değeri |
| `series` | string | TCMB seri kodu (TP.DK.USD.A.YTL vb.) |

### Döviz Kurları — Günlük

| Seri | Açıklama | Tarih Aralığı | Dosya Sayısı |
|---|---|---|---|
| `usd_try_alis` | USD/TRY Alış | 2024 → 2026 | 29 |
| `usd_try_satis` | USD/TRY Satış | 2024 → 2026 | 29 |
| `eur_try_alis` | EUR/TRY Alış | 2024 → 2026 | 29 |
| `eur_try_satis` | EUR/TRY Satış | 2024 → 2026 | 29 |
| `gbp_try_alis` | GBP/TRY Alış | 2024 → 2026 | 29 |

Tarih formatı: `DD-MM-YYYY` (örn. `02-01-2024`)

### Kredi Faiz Oranları — Aylık

| Seri | Açıklama | Tarih Aralığı | Dosya Sayısı |
|---|---|---|---|
| `kredi_faiz_ticari` | Ticari kredi faizi | 2003 → 2025 | 69 |
| `kredi_faiz_tuketici` | Tüketici kredi faizi | 2003 → 2025 | 69 |

Tarih formatı: `YYYY-MM` (örn. `2003-10`)

### TÜFE Alt Endeksleri — Aylık

| Seri | Açıklama | Tarih Aralığı | Dosya Sayısı |
|---|---|---|---|
| `tufe_genel_yoy` | TÜFE Genel (YoY) | 2024 → 2025 | 6 |
| `tufe_cekirdek_yoy` | TÜFE Çekirdek (YoY) | 2024 → 2025 | 6 |
| `tufe_gida_yoy` | TÜFE Gıda (YoY) | 2024 → 2025 | 6 |
| `tufe_gida_alkolsuz_yoy` | TÜFE Gıda & Alkolsüz (YoY) | 2004 → 2025 | 66 |
| `tufe_islem_disi_yoy` | TÜFE İşlem Dışı (YoY) | 2024 → 2025 | 6 |
| `tufe_konut_enerji_yoy` | TÜFE Konut & Enerji (YoY) | 2004 → 2025 | 66 |
| `tufe_taze_meyve_sebze_yoy` | TÜFE Taze Meyve & Sebze (YoY) | 2004 → 2025 | 66 |
| `tufe_ulastirma_yoy` | TÜFE Ulaştırma (YoY) | 2004 → 2025 | 66 |

Tarih formatı: `YYYY-MM` (örn. `2024-10`)

### Yİ-ÜFE Alt Endeksleri — Aylık

| Seri | Açıklama | Tarih Aralığı | Dosya Sayısı |
|---|---|---|---|
| `yiufe_genel_yoy` | Yİ-ÜFE Genel (YoY) | 2024 → 2025 | 6 |
| `yiufe_gida_imalat_yoy` | Yİ-ÜFE Gıda İmalat (YoY) | 2024 → 2025 | 6 |
| `yiufe_elektrik_gaz_yoy` | Yİ-ÜFE Elektrik & Gaz (YoY) | 2024 → 2025 | 6 |
| `yiufe_hayvancilik_yoy` | Yİ-ÜFE Hayvancılık (YoY) | 2024 → 2025 | 6 |
| `yiufe_icecek_imalat_yoy` | Yİ-ÜFE İçecek İmalat (YoY) | 2024 → 2025 | 6 |
| `yiufe_tarim_yoy` | Yİ-ÜFE Tarım (YoY) | 2024 → 2025 | 6 |
| `yiufe_ulastirma_yoy` | Yİ-ÜFE Ulaştırma (YoY) | 2024 → 2025 | 6 |

Tarih formatı: `YYYY-MM` (örn. `2024-10`)

---

## Önemli Tespitler

- **İki farklı tarih formatı var**: günlük seriler `DD-MM-YYYY`, aylık seriler `YYYY-MM`
- **İki farklı granülarite var**: döviz kurları günlük (iş günleri), enflasyon/faiz aylık
- Aylık serilerde tarih ayın ilk günü olarak yorumlanacak (`2024-10` → `2024-10-01`)
- Döviz verisi yalnızca 2024'ten başlıyor — hal verimiz 2016'dan geliyor, Gold join'ında bu eksiklik göze çarpacak

## Silver'a Nasıl Geçireceğiz?

### Sorun: Partition yapısı uyumsuz
Bronze'da klasör isimleri `series=usd_try_alis/` formatında değil, düz `usd_try_alis/` — Spark tek seferde tüm `bronze/tcmb/` yolunu okuyamıyor.

### Çözüm: Her seriyi ayrı oku, union yap
```python
for series in SERIES_FOLDERS:
    df = spark.read.parquet(f"bronze/tcmb/{series}").withColumn("series_name", lit(series))
dfs → union → transform → silver/tcmb/
```

### Partition Stratejisi
- `date` ile partition yapmak **yanlış** — 3.443 satır için çok fazla küçük dosya (~600 gün × 22 seri)
- **Doğrusu**: `series_name` ile partition → 22 klasör, her biri tüm tarihleri içerir

```
silver/tcmb/
    series_name=usd_try_alis/part-0000.parquet
    series_name=eur_try_alis/part-0000.parquet
    ...
```

## Silver tcmb — Final Tablo

| Sütun | Tip | Örnek |
|---|---|---|
| `date` | DATE | `2024-01-02` |
| `series_name` | string | `usd_try_alis` |
| `value` | double | `29.4382` |
| `source` | string | `tcmb` |

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/tcmb_silver.py
```
