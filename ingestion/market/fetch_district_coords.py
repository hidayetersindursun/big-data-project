"""
Nominatim (OpenStreetMap) kullanarak config.py'deki tüm ilçelerin
koordinatlarını çeker ve districts.json olarak kaydeder.

Kullanım:
    python ingestion/market/fetch_district_coords.py
"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from config import CITIES

OUT = os.path.join(os.path.dirname(__file__), "districts.json")
ARCGIS_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"


def fetch_coord(district: str, city: str) -> tuple[float, float] | tuple[None, None]:
    try:
        r = requests.get(ARCGIS_URL, params={
            "singleLine": f"{district} {city} Turkey",
            "f": "json",
            "maxLocations": 1,
        }, verify=False, timeout=10)
        r.raise_for_status()
        candidates = r.json().get("candidates", [])
        if candidates:
            loc = candidates[0]["location"]
            return float(loc["y"]), float(loc["x"])
    except Exception as e:
        print(f"  [ERROR] {district}/{city}: {e}", flush=True)
    return None, None


def main():
    existing = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            existing = json.load(f)

    total = sum(len(v) for v in CITIES.values())
    done = 0
    failed = []

    for city, districts in CITIES.items():
        for district in districts:
            key = f"{city}_{district}"
            if key in existing:
                done += 1
                print(f"  [SKIP] {key} — already cached")
                continue

            lat, lon = fetch_coord(district, city)
            done += 1

            if lat is not None:
                existing[key] = {"lat": lat, "lon": lon}
                print(f"  [{done}/{total}] {key} → {lat:.5f}, {lon:.5f}", flush=True)
            else:
                failed.append(key)
                print(f"  [{done}/{total}] {key} → FAILED", flush=True)

            # Nominatim kullanım koşulları: max 1 istek/saniye
            time.sleep(1.1)

            # Her 10 ilçede bir kaydet (crash recovery)
            if done % 10 == 0:
                with open(OUT, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n=== Bitti: {len(existing)} ilçe kaydedildi, {len(failed)} başarısız ===")
    if failed:
        print("Başarısız:", ", ".join(failed))


if __name__ == "__main__":
    main()
