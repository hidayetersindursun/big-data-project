# Weather — Open-Meteo saatlik/günlük hava verisi (81 şehir)

## Ne işe yarar?

81 il merkezi için saatlik hava verisi: sıcaklık (max/min/avg), yağış, nem, rüzgar, basınç, güneş radyasyonu, toprak nemi, evapotranspirasyon. Veri kaynağı: [Open-Meteo Historical Forecast API](https://open-meteo.com/) — ücretsiz ve tarihçe (1940+) destekli.

## Projemizdeki rolü

Gold tarafındaki **`shock_propagation`** analizinin tetikleyicisi:

- **Frost (don) tespiti**: `temp_min_c < 0` → Antalya'da don olduğunda domates hasarı.
- **Heat stress**: `temp_max_c > 35` → meyve verim düşüşü.
- **Heavy rain**: `precipitation_mm > 50` → sel/hasat aksaması.

Her bu olay tespit edildiğinde, hal fiyatının kaç gün sonra (`hal_lag_days`) ve market fiyatının kaç gün sonra (`market_lag_days`) yükseldiği ölçülür.

Ayrıca uzun vadeli `prophet_forecast` modelinde harici regressor olarak da eklenebilir (yıllık mevsim profillerinin ötesinde).

## Çalıştırma

```bash
python ingestion/weather/saatlik_hava_durumu_api.py
```

Çıktı: `ingestion/weather/data/{şehir}_{yıl}.parquet` (saatlik) — sonra Spark ile günlük aggregate.

## Schema

Bronze Parquet `bronze/weather/year=YYYY/month=MM/`:

| Alan | Tip | Açıklama |
|---|---|---|
| city | string | İl adı (Title Case TR) |
| city_id | int | dahili ID |
| region | string | bölge (Akdeniz, Marmara, ...) |
| time | timestamp | saatlik veya günlük (current implementation: günlük aggregate) |
| t2m_max / t2m_min / t2m | double | °C, max/min/avg sıcaklık |
| t2mdew | double | dew point |
| prectotcorr | double | mm yağış |
| ws10m / ws10m_max | double | m/s rüzgar (avg/max) |
| wd10m | double | derece rüzgar yönü |
| rh2m | double | % nem |
| allsky_sfc_sw_dwn | double | MJ/m² güneş radyasyonu |
| ps | double | kPa basınç |
| et0_fao_evapotranspiration | double | mm referans evapotranspirasyon |
| soil_moisture_mm | double | toprak nemi |

Silver `silver/weather_daily/` aynı alanları okunabilir isimlerle yeniden adlandırır (`temp_max_c`, `precipitation_mm`, vs.).

## Bilinen kısıtlar

- `cloud_amt` %100 null gelir; Silver'da düşürülmüştür.
- API günlük rate limit'i var (10k call/gün), 81 şehir × birkaç yıl backfill için chunked istek atmak gerekir.
- Open-Meteo bazı kırsal şehirlerde nearest grid point'i alır — coğrafi olarak küçük şehirlerin (Iğdır, Şırnak) coverage'ı zayıf olabilir.

## Referans

- `weather_dataset.md` — orijinal dataset notları.
- `saatlik_hava_durumu_api.md` — API endpoint detayları.
