# Güncel Hava Durumu Toplayıcı — Kullanım Kılavuzu

**Script:** `saatlik_hava_durumu_api.py`  
**Kaynak:** Open-Meteo Forecast API (ücretsiz, API key yok)  
**Kapsam:** 81 Türkiye ili, çalıştırıldığı günün verisi

---

## Çalıştırma

```bash
# Standart çalıştırma (çıktı script dizinine kaydedilir)
python saatlik_hava_durumu_api.py

# Farklı klasöre kaydet
python saatlik_hava_durumu_api.py --out-dir C:\veri\hava
```

Çıktı dosyası otomatik olarak adlandırılır:
```
hava_durumu_YYYY_MM_DD_HH_MM.json
```

---

## Zamanlayıcı ile Otomatik Çalıştırma

### Windows Görev Zamanlayıcı (Task Scheduler)

1. `Görev Zamanlayıcı`yı aç → `Temel Görev Oluştur`
2. Tetikleyici: **Günlük**, istenen saat
3. Eylem: **Program Başlat**
   ```
   Program : C:\Users\PC_N_633\miniconda3\python.exe
   Bağımsız değişken: C:\Users\PC_N_633\Desktop\akca\Big_Data\weather\saatlik_hava_durumu_api.py
   ```

### Manuel Test (PowerShell)
```powershell
python weather\saatlik_hava_durumu_api.py
```

---

## Çıktı Formatı

Her çalıştırmada 81 şehri içeren tek bir JSON dosyası üretilir.

### Dosya Yapısı

```json
[
  {
    "city_id": 6,
    "city_name": "Ankara",
    "region": "İç Anadolu",
    "latitude": "39.9208",
    "longitude": "32.8541",
    "timestamp": "2026-05-19 12:27:24",
    "weather_data": {
      "t2m_max": 20.6,
      "t2m_min": 8.3,
      "t2m": 14.5,
      "t2mdew": 7.22,
      "prectotcorr": 0.0,
      "ws10m": 3.40,
      "wd10m": 229,
      "ws10m_max": 5.7,
      "rh2m": 64.13,
      "allsky_sfc_sw_dwn": 6.04,
      "ps": 91.52,
      "cloud_amt": 61.96,
      "et0_fao_evapotranspiration": 3.65,
      "soil_moisture_mm": 11.76
    }
  }
]
```

---

## Sütun Açıklamaları

| Sütun | Birim | Açıklama | Kaynak |
|---|---|---|---|
| `t2m_max` | °C | Günlük maksimum sıcaklık (2m) | Open-Meteo daily |
| `t2m_min` | °C | Günlük minimum sıcaklık (2m) | Open-Meteo daily |
| `t2m` | °C | Günlük ortalama sıcaklık (2m) | Open-Meteo daily |
| `t2mdew` | °C | Çiğ noktası sıcaklığı (saatlik ort.) | Open-Meteo hourly |
| `prectotcorr` | mm/gün | Günlük toplam yağış | Open-Meteo daily |
| `ws10m` | m/s | Ortalama rüzgar hızı 10m (saatlik ort.) | Open-Meteo hourly |
| `wd10m` | derece | Baskın rüzgar yönü | Open-Meteo daily |
| `ws10m_max` | m/s | Maksimum rüzgar hızı 10m | Open-Meteo daily |
| `rh2m` | % | Bağıl nem (saatlik ort.) | Open-Meteo hourly |
| `allsky_sfc_sw_dwn` | kWh/m²/gün | Güneş kısa dalga radyasyon | Open-Meteo daily ÷ 3.6 |
| `ps` | kPa | Yüzey basıncı (saatlik ort.) | Open-Meteo hourly ÷ 10 |
| `cloud_amt` | % | Bulut miktarı (saatlik ort.) | Open-Meteo hourly |
| `et0_fao_evapotranspiration` | mm/gün | FAO-56 referans ET | Open-Meteo daily |
| `soil_moisture_mm` | mm | Toprak nemi 0-7cm katman | Open-Meteo hourly × 70 |

> **Not:** `soil_moisture_mm` = `soil_moisture_0_to_7cm` (m³/m³) × 70 mm (katman derinliği).  
> Bu değer `data/enhanced/` şemasındaki su dengesi modeliyle aynı birime sahip ancak farklı hesap yöntemidir.

---

## Enhanced Dataset ile Uyumluluk

Bu script'in ürettiği sütunlar `data/enhanced/{il}/{yil}.parquet` şemasıyla **birebir eşleşir**:

```python
import pandas as pd, json

# Enhanced parquet
df = pd.read_parquet("data/enhanced/Ankara/2024.parquet")

# Güncel JSON
with open("hava_durumu_2026_05_19_12_27.json") as f:
    today = next(r for r in json.load(f) if r["city_name"] == "Ankara")

# Aynı sütun isimleri
print(set(df.columns) - {"city_id","city","region","time"})
print(set(today["weather_data"].keys()))
# Çıktı birebir aynı
```

---

## Örnek Çıktı (2026-05-19 — Seçili İller)

| İl | t2m_max | t2m_min | yağış | ET0 | toprak nemi |
|---|---|---|---|---|---|
| Adana | 27.6°C | 17.3°C | 0.0 mm | 5.08 mm | — |
| Ankara | 20.6°C | 8.3°C | 0.0 mm | 3.65 mm | 11.76 mm |
| Antalya | 27.3°C | 19.7°C | 0.0 mm | 6.03 mm | — |
| Erzurum | 9.9°C | 3.5°C | 0.2 mm | 2.43 mm | — |
| Şanlıurfa | 25.2°C | 15.8°C | 0.0 mm | 6.82 mm | — |
| Rize | 17.2°C | 12.9°C | 7.4 mm | 1.50 mm | — |
