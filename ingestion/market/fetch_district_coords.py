"""
ArcGIS ile merkez koordinatı, Nominatim (OSM) ile bbox çeker.
districts.json'a { lat, lon, bbox: [south, north, west, east] } olarak kaydeder.

Kullanım:
    python ingestion/market/fetch_district_coords.py
"""
import json
import os
import sys
import time

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(__file__))
from config import CITIES

OUT = os.path.join(os.path.dirname(__file__), "districts.json")

ARCGIS_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "BigDataTurkeyFoodPrices/1.0 (h.e.dursun@gmail.com)"}


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
        print(f"  [ERROR] coord {district}/{city}: {e}", flush=True)
    return None, None


_MIN_BBOX_DEG = 0.02  # ~2km — bundan küçük bbox ilçe sınırı değil, kasaba noktasıdır


def _bbox_ok(bb: list) -> bool:
    """bbox gerçek bir ilçe sınırını temsil edecek kadar büyük mü?"""
    if not bb:
        return False
    s, n, w, e = bb
    return (n - s) >= _MIN_BBOX_DEG and (e - w) >= _MIN_BBOX_DEG


def fetch_bbox(district: str, city: str) -> list | None:
    """Nominatim'den ilçe bbox'ını çek: [south_lat, north_lat, west_lon, east_lon].

    Önce idari sınır (class=boundary, type=administrative) sonuçlarına bakar;
    nokta/kasaba sonuçlarını (_bbox_ok ile) eliyor.
    """
    try:
        r = requests.get(NOMINATIM_URL, params={
            "q": f"{district} {city} Turkey",
            "format": "json",
            "limit": 10,
            "addressdetails": 1,
        }, headers=NOMINATIM_HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json()

        d_lower = district.lower()

        # 1. Geçiş: class=boundary + type=administrative + display_name eşleşmesi
        for res in results:
            if res.get("class") != "boundary" or res.get("type") != "administrative":
                continue
            display = res.get("display_name", "").lower()
            if display.startswith(d_lower):
                bb = res.get("boundingbox")
                if bb:
                    candidate = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
                    if _bbox_ok(candidate):
                        return candidate

        # 2. Geçiş: class=boundary + type=administrative (display_name'e bakmadan)
        for res in results:
            if res.get("class") != "boundary" or res.get("type") != "administrative":
                continue
            bb = res.get("boundingbox")
            if bb:
                candidate = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
                if _bbox_ok(candidate):
                    return candidate

        # 3. Geçiş: herhangi bir sonuç, yeterince büyük bbox varsa
        for res in results:
            bb = res.get("boundingbox")
            if bb:
                candidate = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
                if _bbox_ok(candidate):
                    return candidate

    except Exception as e:
        print(f"  [ERROR] bbox {district}/{city}: {e}", flush=True)
    return None


def main():
    existing = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            existing = json.load(f)

    total = sum(len(v) for v in CITIES.values())
    done = 0
    failed_coord = []
    failed_bbox = []

    for city, districts in CITIES.items():
        for district in districts:
            key = f"{city}_{district}"
            entry = existing.get(key, {})
            done += 1

            # --- Koordinat ---
            if "lat" not in entry:
                lat, lon = fetch_coord(district, city)
                if lat is not None:
                    entry["lat"] = lat
                    entry["lon"] = lon
                    print(f"  [{done}/{total}] {key} COORD → {lat:.5f}, {lon:.5f}", flush=True)
                else:
                    failed_coord.append(key)
                    print(f"  [{done}/{total}] {key} COORD → FAILED", flush=True)
                time.sleep(0.5)
            else:
                print(f"  [{done}/{total}] {key} COORD → skip (cached)", flush=True)

            # --- BBox ---
            if "bbox" not in entry:
                bbox = fetch_bbox(district, city)
                if bbox:
                    entry["bbox"] = bbox
                    print(f"           {key} BBOX  → {bbox}", flush=True)
                else:
                    failed_bbox.append(key)
                    print(f"           {key} BBOX  → FAILED", flush=True)
                # Nominatim kullanım koşulları: max 1 istek/sn
                time.sleep(1.1)
            else:
                print(f"           {key} BBOX  → skip (cached)", flush=True)

            existing[key] = entry

            # Her 10 ilçede crash recovery için kaydet
            if done % 10 == 0:
                with open(OUT, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n=== Bitti: {len(existing)} ilçe kaydedildi ===")
    if failed_coord:
        print(f"Koordinat başarısız ({len(failed_coord)}): {', '.join(failed_coord)}")
    if failed_bbox:
        print(f"BBox başarısız ({len(failed_bbox)}): {', '.join(failed_bbox)}")


if __name__ == "__main__":
    main()
