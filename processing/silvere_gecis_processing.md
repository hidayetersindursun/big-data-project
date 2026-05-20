# Silver Katmanına Geçiş — İşlem Notu

## Genel Amaç

Bronze katmanındaki ham Parquet verilerini Apache Spark ile okuyup temizleyerek,
standardize edilmiş Silver tablolarını `s3://s3-bbuckett/silver/` altına yazmak.

## Mimari Kararlar

- Her kaynak kendi Silver tablosunu alır (tek büyük tablo değil)
- Gold katmanında join yapılır, Silver'da değil
- Tüm tablolarda ortak schema standartları uygulanır

### Ortak Schema Standartları

| Alan | Format |
|---|---|
| Tarih | `date: DATE (YYYY-MM-DD)` |
| Şehir | `city: STRING (Title Case, Türkçe karakter korunur)` |
| Fiyat | `price_per_kg: DOUBLE` |
| Kaynak | `source: STRING` |

## Silver Tablolar

| Tablo | Kaynak (Bronze) | Durum |
|---|---|---|
| `silver/hal_prices` | `bronze/hal_all` | Bekliyor |
| `silver/market_prices` | `bronze/market`, `bronze/market_synthetic` | Bekliyor |
| `silver/macro_indicators` | `bronze/tcmb`, `bronze/epias`, `bronze/akaryakit` | Bekliyor |
| `silver/weather_daily` | `bronze/weather` | Bekliyor |
| `silver/commodities` | `bronze/commodities` | Bekliyor |

## İlerleme

### Yapılacaklar
- [ ] `processing/silver/` klasör yapısını oluştur
- [ ] Ortak SparkSession fabrikasını yaz (`utils/spark_session.py`)
- [ ] Birim dönüşüm kataloğunu tanımla (`utils/unit_normalizer.py`)
- [ ] Şehir/bölge isim standardizasyon mapping'i oluştur
- [ ] `hal_silver.py` — entity resolution + birim standardizasyonu
- [ ] `market_silver.py` — fiyat normalizasyonu
- [ ] `macro_indicators_silver.py` — TCMB + EPİAŞ + akaryakıt birleştirme
- [ ] `weather_silver.py` — şehir + tarih bazlı özet
- [ ] `commodities_silver.py`

### Tamamlananlar
- [x] Branch oluşturuldu: `silver_gecis_gelistirmeleri`
- [x] S3 bucket incelendi: `s3://s3-bbuckett/` — yalnızca Bronze mevcut
- [x] Mimari kararlar belirlendi

## Notlar
