# Weather Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/weather/`
- **Yapı**: `year={yil}/month={ay}/part-0000.parquet`
- **Kapsam**: 2016 → 2026 (11 yıl, 125 dosya)
- **Boyut**: ~17.2 MiB

## Bronze Şeması (Ham)

| Sütun | Tip | Notlar |
|---|---|---|
| `city_id` | long | Numerik şehir ID |
| `city` | string | Title Case, Türkçe karakter korunmuş |
| `region` | string | Coğrafi bölge (Akdeniz, Ege vb.) |
| `time` | timestamp_ntz | Günlük, saat 00:00:00 |
| `t2m_max` | double | Maks. sıcaklık 2m (°C) |
| `t2m_min` | double | Min. sıcaklık 2m (°C) |
| `t2m` | double | Ort. sıcaklık 2m (°C) |
| `t2mdew` | double | Çiğ noktası sıcaklığı (°C) |
| `prectotcorr` | double | Yağış miktarı (mm) |
| `ws10m` | double | Rüzgar hızı 10m (m/s) |
| `wd10m` | double | Rüzgar yönü 10m (derece) |
| `ws10m_max` | double | Maks. rüzgar hızı 10m (m/s) |
| `rh2m` | double | Bağıl nem 2m (%) |
| `allsky_sfc_sw_dwn` | double | Güneş radyasyonu (MJ/m²/gün) — %30 null |
| `ps` | double | Yüzey basıncı (kPa) |
| `cloud_amt` | double | Bulut miktarı (%) — **%100 null** |
| `et0_fao_evapotranspiration` | double | Evapotranspirasyon (mm/gün) |
| `soil_moisture_mm` | double | Toprak nemi (mm) |

### Null Durumu
- `cloud_amt` → %100 null → **kaldırıldı**
- `allsky_sfc_sw_dwn` → ~%30 null → tutuldu (eksik ölçüm, veri yokluğu değil)
- Diğer sütunlar: 243/1458 null (belirli şehir/tarih kombinasyonları)

## Silver Hedef

- **Path**: `s3://s3-bbuckett/silver/weather_daily/`
- **Yapı**: `date={YYYY-MM-DD}/part-*.parquet`
- **Script**: `processing/silver/weather_silver.py`

## Mimari Kararlar

- `time` (timestamp) → `date` (DATE) — veri zaten günlük granülaritede
- `cloud_amt` kaldırıldı — %100 null, bilgi değeri sıfır
- Teknik sütun isimleri okunabilir hale getirildi (Gold join'larında daha anlaşılır)
- `city` ve `region` korundu — Gold'da hal/market ile spatial join için gerekli

## Silver hal_prices — Final Tablo

| Sütun | Tip | Açıklama | Örnek |
|---|---|---|---|
| `date` | DATE | Tarih | `2026-05-01` |
| `city_id` | long | Numerik şehir ID | `1` |
| `city` | string | Şehir adı | `Adana` |
| `region` | string | Coğrafi bölge | `Akdeniz` |
| `temp_max_c` | double | Maks. sıcaklık (°C) | `26.43` |
| `temp_min_c` | double | Min. sıcaklık (°C) | `15.38` |
| `temp_avg_c` | double | Ort. sıcaklık (°C) | `19.96` |
| `dew_point_c` | double | Çiğ noktası (°C) | `14.16` |
| `precipitation_mm` | double | Yağış (mm) | `0.19` |
| `humidity_pct` | double | Bağıl nem (%) | `71.83` |
| `wind_speed_ms` | double | Rüzgar hızı (m/s) | `2.05` |
| `wind_speed_max_ms` | double | Maks. rüzgar hızı (m/s) | `4.48` |
| `wind_dir_deg` | double | Rüzgar yönü (derece) | `204.2` |
| `solar_rad_mj` | double | Güneş radyasyonu (MJ/m²) | `2.207` |
| `pressure_kpa` | double | Yüzey basıncı (kPa) | `99.84` |
| `evapotranspiration_mm` | double | Evapotranspirasyon (mm) | `2.236` |
| `soil_moisture_mm` | double | Toprak nemi (mm) | `127.09` |
| `source` | string | Kaynak etiketi | `weather` |

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/weather_silver.py
```

## Sonuç

| | Bronze | Silver |
|---|---|---|
| Boyut | ~17.2 MiB | — |
| Partition | year/month | date |
| Sütun sayısı | 18 | 18 (cloud_amt çıktı, source eklendi) |
| Kaldırılan | — | `cloud_amt` (%100 null) |
