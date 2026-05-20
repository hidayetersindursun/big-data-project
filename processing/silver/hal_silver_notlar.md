# Hal Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/hal_all/`
- **Yapı**: `year={yil}/month={ay}/part-0000.parquet`
- **Kapsam**: 2016 Ocak → 2026 Aralık (11 yıl, 132 dosya)
- **Toplam satır**: ~19 milyon

## Bronze Şeması (Ham)

| Sütun | Tip | Notlar |
|---|---|---|
| `tarih` | string | `YYYY-MM-DD` formatında, tutarlı |
| `sehir` | string | Title Case, Türkçe karakter korunmuş |
| `urun` | string | Gerçek veri ALL CAPS, sentetik Title Case — karışık |
| `kategori` | string | %1.8 null; "Sebze"/"SEBZE" gibi case karışıklığı |
| `en_dusuk` | string | Float değer taşıyor, cast gerekiyor |
| `en_yuksek` | string | Float değer taşıyor, cast gerekiyor |
| `veri_turu` | string | `gercek` veya `sentetik` |
| `year` | string | Partition sütunu, `tarih`'ten türetilebilir |
| `month` | string | Partition sütunu, `tarih`'ten türetilebilir |

### Veri Dağılımı (2026-05 örneği)
- Gerçek veri: ~9.473 satır (%6.8)
- Sentetik veri: ~129.859 satır (%93.2)
- Unique ürün sayısı: 626
- Birim sütunu yok — fiyatlar zaten KG bazlı

### Kategori değerleri
- `Sebze` / `SEBZE` → normalize edildi
- `Meyve` / `MEYVE` → normalize edildi
- `İthal Ürünler` / `İTHAL` → normalize edildi
- null → `Bilinmiyor` dolduruldu

## Silver Hedef

- **Path**: `s3://s3-bbuckett/silver/hal_prices/`
- **Yapı**: `date={YYYY-MM-DD}/part-*.parquet`
- **Script**: `processing/silver/hal_silver.py`

## Silver Şeması (Dönüştürülmüş)

| Sütun | Tip | Dönüşüm |
|---|---|---|
| `date` | DATE | `tarih` string → DATE |
| `city` | string | `sehir` rename, değişiklik yok |
| `product_name` | string | `urun` → `initcap(lower())` ile Title Case |
| `category` | string | `kategori` → Title Case, null → "Bilinmiyor" |
| `price_min` | DOUBLE | `en_dusuk` cast |
| `price_max` | DOUBLE | `en_yuksek` cast |
| `price_avg` | DOUBLE | `(price_min + price_max) / 2` |
| `source_type` | string | `veri_turu` rename (`gercek`/`sentetik`) |
| `source` | string | Sabit `"hal"` etiketi |

## Mimari Kararlar

- `veri_turu` Silver'da **korundu** — filtre Gold katmanında yapılacak
- `year` ve `month` partition sütunları **kaldırıldı**, `date`'den türetilir
- Null fiyat satırları atıldı (sayısı ihmal edilebilir düzeyde)
- Birim normalizasyonu yapılmadı — kaynak zaten KG bazlı

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/hal_silver.py
```

### Bağımlılıklar
- Spark 3.5.1 (Hadoop 3.3.4 dahili)
- `hadoop-aws:3.3.4` — Spark'ın Hadoop versiyonuyla eşleşmeli (3.3.6 uyumsuz)
- `aws-java-sdk-bundle:1.12.262`

## Sonuç

| | Bronze | Silver |
|---|---|---|
| Satır sayısı | 19.003.625 | 19.003.625 |
| Null atılan | — | 0 |
| Boyut (tahmini) | ~62 MiB | ~180 MB+ |
| Partition | year/month | date |

## Silver hal_prices — Final Tablo

| Sütun | Tip | Örnek |
|---|---|---|
| `date` | DATE | `2026-05-01` |
| `city` | string | `Adana` |
| `product_name` | string | `Lahana(beyaz)` |
| `category` | string | `Sebze` |
| `price_min` | DOUBLE | `4.0` |
| `price_max` | DOUBLE | `8.0` |
| `price_avg` | DOUBLE | `6.0` |
| `source_type` | string | `gercek` / `sentetik` |
| `source` | string | `hal` |
