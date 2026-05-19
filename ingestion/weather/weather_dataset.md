# Enhanced Weather Dataset — Türkiye 81 İl (2016–2026)

## Genel Bilgi

| | Değer |
|---|---|
| **Kaynak** | NASA POWER (ERA5 + MERRA-2) + türetilmiş hesaplamalar |
| **Kapsam** | 81 il, 2016-01-01 – 2026-05-19 |
| **Çözünürlük** | Günlük |
| **Toplam kayıt** | ~307.000 (81 il × 3.791 gün) |
| **Dosya formatı** | Parquet |
| **Klasör** | `data/enhanced/{il}/{yil}.parquet` |
| **Dosya sayısı** | 891 (81 il × 11 yıl) |
| **Toplam boyut** | ~33 MB |

---

## Sütunlar

### Kimlik ve Zaman

| Sütun | Tür | Açıklama |
|---|---|---|
| `city_id` | int | İl plaka numarası (1–81) |
| `city` | str | İl adı |
| `region` | str | Coğrafi bölge |
| `time` | datetime | Tarih (günlük) |

### NASA POWER — Sıcaklık

| Sütun | Birim | Açıklama |
|---|---|---|
| `t2m_max` | °C | Günlük maksimum sıcaklık (2m) |
| `t2m_min` | °C | Günlük minimum sıcaklık (2m) |
| `t2m` | °C | Günlük ortalama sıcaklık (2m) |
| `t2mdew` | °C | Çiğ noktası sıcaklığı (2m) |

### NASA POWER — Yağış ve Su

| Sütun | Birim | Açıklama |
|---|---|---|
| `prectotcorr` | mm/gün | Düzeltilmiş toplam yağış |

### NASA POWER — Rüzgar

| Sütun | Birim | Açıklama |
|---|---|---|
| `ws10m` | m/s | Ortalama rüzgar hızı (10m) |
| `ws10m_max` | m/s | Maksimum rüzgar hızı (10m) |
| `wd10m` | derece | Rüzgar yönü (10m) |

### NASA POWER — Atmosfer ve Radyasyon

| Sütun | Birim | Açıklama |
|---|---|---|
| `rh2m` | % | Bağıl nem ortalaması (2m) |
| `allsky_sfc_sw_dwn` | kWh/m²/gün | Tüm gökyüzü koşullarında gelen kısa dalga radyasyon |
| `ps` | kPa | Yüzey basıncı |
| `cloud_amt` | % | Bulut miktarı |

### Türetilmiş Sütunlar ★

| Sütun | Birim | Yöntem |
|---|---|---|
| `et0_fao_evapotranspiration` | mm/gün | FAO-56 Penman-Monteith (pyeto kütüphanesi) |
| `soil_moisture_mm` | mm | Basit su dengesi modeli: `SM[t] = clamp(SM[t-1] + yağış - ET0, 0, 150)` |

---

## Türetilmiş Sütun Detayları

### ET0 — FAO-56 Penman-Monteith

NASA POWER değişkenleri kullanılarak hesaplanmıştır:

| Girdi | NASA POWER sütunu | Dönüşüm |
|---|---|---|
| Sıcaklık max/min/ort | `t2m_max`, `t2m_min`, `t2m` | — |
| Bağıl nem | `rh2m` | — |
| Rüzgar hızı | `ws10m` | 10m → 2m (logaritmik profil) |
| Güneş radyasyonu | `allsky_sfc_sw_dwn` | kWh → MJ/m²/gün (×3.6) |
| Atmosfer basıncı | `ps` | Psikrometrik sabit için |

Tüm iller için kullanılan varsayımlar: rakım = 0m (deniz seviyesi), zemin ısı akısı G = 0.

### Toprak Nemi (Su Dengesi Modeli)

```
SM[0]  = 75 mm  (başlangıç — alan kapasitesinin yarısı)
SM[t]  = SM[t-1] + yağış[t] - ET0[t]
SM[t]  = max(0, min(150, SM[t]))
```

- Alan kapasitesi (FC): 150 mm (tın toprak tipik değeri)
- Sıfır alt sınır: solma noktası
- Model yıllar arası süreklidir (her şehir için 2016'dan bugüne tek zincir)

---

## Okuma Örneği

```python
import pandas as pd
from pathlib import Path

# Tek şehir, tek yıl
df = pd.read_parquet("data/enhanced/Ankara/2023.parquet")

# Tüm şehirler, tüm yıllar
df = pd.read_parquet("data/enhanced/")

# Spark ile
spark.read.parquet("data/enhanced/**/*.parquet")
```

---

## ET0 Ortalama Değerleri (Coğrafi Kontrol)

| İl | ET0 ort. (mm/gün) | Bölge |
|---|---|---|
| Şanlıurfa | 4.75 | GD Anadolu — en kurak |
| Gaziantep | 4.38 | GD Anadolu |
| Adana | 4.12 | Akdeniz |
| Artvin | 1.93 | Karadeniz — en nemli |
| Bayburt | 1.88 | Doğu Karadeniz — en serin |
