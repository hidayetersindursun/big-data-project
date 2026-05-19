"""
Güncel Hava Durumu Toplayıcı — 81 Türkiye İli
------------------------------------------------
Çalıştırıldığı gün ve saatte Open-Meteo'dan veri çeker.
Çıktı sütunları data/enhanced/ parquet şemasıyla birebir eşleşir.

Sütun eşleşmesi (Open-Meteo → enhanced şema):
  temperature_2m_max          → t2m_max          (°C)
  temperature_2m_min          → t2m_min          (°C)
  temperature_2m_mean         → t2m              (°C)
  dew_point_2m (saatlik ort.) → t2mdew           (°C)
  precipitation_sum           → prectotcorr      (mm/gün)
  wind_speed_10m (saat. ort.) → ws10m            (m/s)
  wind_direction_10m_dominant → wd10m            (derece)
  wind_speed_10m_max          → ws10m_max        (m/s)
  relative_humidity_2m (ort.) → rh2m             (%)
  shortwave_radiation_sum ÷3.6→ allsky_sfc_sw_dwn(kWh/m²/gün)
  surface_pressure (saat.ort.)→ ps               (kPa, hPa÷10)
  cloud_cover (saatlik ort.)  → cloud_amt        (%)
  et0_fao_evapotranspiration  → et0_fao_evapotranspiration (mm/gün)
  soil_moisture_0_to_7cm×70   → soil_moisture_mm (mm)

Kullanım:
  python saatlik_hava_durumu_api.py
  python saatlik_hava_durumu_api.py --out-dir /baska/klasor
"""

import argparse
import datetime
import json
import os
import time

import requests

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CITIES_FILE = os.path.join(SCRIPT_DIR, "cities_of_turkey.json")
API_URL     = "https://api.open-meteo.com/v1/forecast"

DAILY_VARS  = ",".join([
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
])

HOURLY_VARS = ",".join([
    "dew_point_2m",
    "wind_speed_10m",
    "relative_humidity_2m",
    "surface_pressure",
    "cloud_cover",
    "soil_moisture_0_to_7cm",
])


def hourly_mean(data: dict, key: str) -> float | None:
    """Günlük tüm saatlik değerlerin ortalaması (None ve eksikler atlanır)."""
    vals = [v for v in data.get(key, []) if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def fetch_city(city: dict, current_date: str, session: requests.Session) -> dict | None:
    params = {
        "latitude":  city["latitude"],
        "longitude": city["longitude"],
        "daily":     DAILY_VARS,
        "hourly":    HOURLY_VARS,
        "timezone":  "Europe/Istanbul",
        "start_date": current_date,
        "end_date":   current_date,
    }
    try:
        resp = session.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  HATA {city['name']}: {e}")
        return None

    daily  = data.get("daily", {})
    hourly = data.get("hourly", {})

    def d(key):
        vals = daily.get(key, [None])
        return vals[0] if vals else None

    # shortwave_radiation_sum: MJ/m²/gün → kWh/m²/gün
    rad = d("shortwave_radiation_sum")
    allsky = round(rad / 3.6, 4) if rad is not None else None

    # surface_pressure: hPa → kPa
    ps_hpa = hourly_mean(hourly, "surface_pressure")
    ps_kpa = round(ps_hpa / 10, 4) if ps_hpa is not None else None

    # soil_moisture m³/m³ → mm (0-7 cm katman = 70 mm derinlik)
    sm_m3 = hourly_mean(hourly, "soil_moisture_0_to_7cm")
    sm_mm = round(sm_m3 * 70, 3) if sm_m3 is not None else None

    return {
        "city_id":   city["id"],
        "city_name": city["name"],
        "region":    city.get("region", ""),
        "latitude":  city["latitude"],
        "longitude": city["longitude"],
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "weather_data": {
            "t2m_max":                    d("temperature_2m_max"),
            "t2m_min":                    d("temperature_2m_min"),
            "t2m":                        d("temperature_2m_mean"),
            "t2mdew":                     hourly_mean(hourly, "dew_point_2m"),
            "prectotcorr":                d("precipitation_sum"),
            "ws10m":                      hourly_mean(hourly, "wind_speed_10m"),
            "wd10m":                      d("wind_direction_10m_dominant"),
            "ws10m_max":                  d("wind_speed_10m_max"),
            "rh2m":                       hourly_mean(hourly, "relative_humidity_2m"),
            "allsky_sfc_sw_dwn":          allsky,
            "ps":                         ps_kpa,
            "cloud_amt":                  hourly_mean(hourly, "cloud_cover"),
            "et0_fao_evapotranspiration": d("et0_fao_evapotranspiration"),
            "soil_moisture_mm":           sm_mm,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=SCRIPT_DIR,
                        help="Çıktı klasörü (varsayılan: script dizini)")
    args = parser.parse_args()

    with open(CITIES_FILE, encoding="utf-8") as f:
        cities = json.load(f)

    now          = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    filename     = now.strftime("hava_durumu_%Y_%m_%d_%H_%M.json")
    filepath     = os.path.join(args.out_dir, filename)

    session = requests.Session()
    results = []

    print(f"Tarih    : {current_date}")
    print(f"Şehir    : {len(cities)}")
    print(f"Çıktı    : {filepath}")
    print()

    for i, city in enumerate(cities, 1):
        record = fetch_city(city, current_date, session)
        if record:
            results.append(record)
            wd = record["weather_data"]
            print(f"  [{i:2d}/81] {city['name']:20s}  "
                  f"t={wd['t2m_max']}/{wd['t2m_min']}°C  "
                  f"yağış={wd['prectotcorr']}mm  "
                  f"ET0={wd['et0_fao_evapotranspiration']}mm")
        time.sleep(0.15)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{len(results)}/81 sehir kaydedildi: {filename}")


if __name__ == "__main__":
    main()
