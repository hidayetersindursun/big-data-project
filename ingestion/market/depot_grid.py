"""
Grid search: ilçenin bounding box'ını tarayarak tüm unique depotları çeker.
Her grid noktasından /nearest sorgusu atar, depotId ile deduplicate eder.

districts.json'da bbox varsa onu kullanır; yoksa merkez ± DEFAULT_SPAN_DEG ile geri döner.

Kullanım:
    python ingestion/market/depot_grid.py --district Bayrampaşa --city İstanbul
    python ingestion/market/depot_grid.py --district Bayrampaşa --city İstanbul --step 0.003
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from client import get_coordinates, _request, _async_safe_request
from config import BASE_API_URL

DEFAULT_STEP_DEG = 0.008   # ~888m — radius=1km ile tam kapsama, 0.005°'den 2.5x daha az nokta
DEFAULT_RADIUS_KM = 1
DEFAULT_SPAN_DEG = 0.03    # fallback: merkez ± ~3km (bbox yoksa)

_DISTRICTS_PATH = os.path.join(os.path.dirname(__file__), "districts.json")
_DISTRICTS: dict = {}
if os.path.exists(_DISTRICTS_PATH):
    with open(_DISTRICTS_PATH, encoding="utf-8") as _f:
        _DISTRICTS = json.load(_f)


def grid_points(south: float, north: float, west: float, east: float, step: float = DEFAULT_STEP_DEG,
                center_lat: float = None, center_lon: float = None) -> list:
    """bbox içindeki grid noktalarını üret; merkez verilirse oradan uzaklığa göre sıralar."""
    points = []
    lat = south
    while lat <= north + 1e-9:
        lon = west
        while lon <= east + 1e-9:
            points.append((round(lat, 6), round(lon, 6)))
            lon += step
        lat += step
    if center_lat is not None:
        points.sort(key=lambda p: (p[0] - center_lat) ** 2 + (p[1] - center_lon) ** 2)
    return points


def _bbox_for(district: str, city: str) -> tuple:
    """districts.json'dan bbox ve merkez koordinatı döndür; yoksa merkez ± span ile fallback.
    Returns: (south, north, west, east, center_lat, center_lon, source)
    """
    key = f"{city}_{district}"
    entry = _DISTRICTS.get(key, {})
    clat, clon = entry.get("lat"), entry.get("lon")

    if "bbox" in entry:
        s, n, w, e = entry["bbox"]
        if clat is None:
            clat, clon = (s + n) / 2, (w + e) / 2
        return s, n, w, e, clat, clon, "districts.json bbox"

    if clat is None:
        clat, clon = get_coordinates(district, city)
    if clat is None:
        return None, None, None, None, None, None, "not found"

    return (clat - DEFAULT_SPAN_DEG, clat + DEFAULT_SPAN_DEG,
            clon - DEFAULT_SPAN_DEG, clon + DEFAULT_SPAN_DEG,
            clat, clon, f"center±{DEFAULT_SPAN_DEG}° fallback")


def fetch_depots_grid(district, city, step=DEFAULT_STEP_DEG, radius=DEFAULT_RADIUS_KM):
    errors: list[str] = []

    south, north, west, east, clat, clon, source = _bbox_for(district, city)
    if south is None:
        errors.append(f"[{district},{city}] koordinat/bbox bulunamadı")
        return {}, errors

    points = grid_points(south, north, west, east, step=step, center_lat=clat, center_lon=clon)
    print(f"BBox ({source}): S={south:.5f} N={north:.5f} W={west:.5f} E={east:.5f}")
    print(f"Grid: {len(points)} nokta, radius={radius}km, step={step}° (merkez önce: {clat:.5f},{clon:.5f})")

    depots = {}
    for i, (plat, plon) in enumerate(points):
        try:
            r = _request("POST", f"{BASE_API_URL}/nearest",
                         json={"latitude": plat, "longitude": plon, "distance": radius},
                         timeout=15)
        except Exception as e:
            errors.append(f"({plat},{plon}) → hata: {e}")
            r = None

        if r:
            for d in r.json():
                did = d.get("id")
                if did and did not in depots:
                    depots[did] = {
                        "id": did,
                        "name": d.get("sellerName", ""),
                        "market": d.get("marketName", ""),
                        "lat": d["location"]["lat"],
                        "lon": d["location"]["lon"],
                        "distance_from_center": d.get("distance"),
                    }
        else:
            if not any(f"({plat},{plon})" in e for e in errors):
                errors.append(f"({plat},{plon}) → API yanıt vermedi")

        print(f"  [{i+1}/{len(points)}] ({plat}, {plon}) → {len(depots)} unique depot", end="\r")
        time.sleep(0.5)

    print(f"\nToplam: {len(depots)} unique depot")
    return depots, errors


async def fetch_depots_grid_async(
    district: str,
    city: str,
    sem: asyncio.Semaphore,
    step: float = DEFAULT_STEP_DEG,
    radius: float = DEFAULT_RADIUS_KM,
) -> tuple[dict, list[str]]:
    """Async grid search — tüm noktaları paralel tarar (semaphore ile throttle)."""
    errors: list[str] = []

    south, north, west, east, clat, clon, source = _bbox_for(district, city)
    if south is None:
        errors.append(f"[{district},{city}] koordinat/bbox bulunamadı")
        return {}, errors

    points = grid_points(south, north, west, east, step=step, center_lat=clat, center_lon=clon)
    print(f"  [{city}/{district}] Grid ({source}): {len(points)} nokta, radius={radius}km, step={step}° (merkez önce)")

    depots: dict = {}
    lock = asyncio.Lock()
    completed = 0

    async def _query(plat: float, plon: float) -> None:
        nonlocal completed
        await asyncio.sleep(random.uniform(0.4, 0.8))
        r = await _async_safe_request(
            "POST", f"{BASE_API_URL}/nearest", sem,
            json={"latitude": plat, "longitude": plon, "distance": radius},
            timeout=15,
        )
        async with lock:
            completed += 1
            if r:
                for d in r.json():
                    did = d.get("id")
                    if did and did not in depots:
                        depots[did] = {
                            "id": did,
                            "name": d.get("sellerName", ""),
                            "market": d.get("marketName", ""),
                            "lat": d["location"]["lat"],
                            "lon": d["location"]["lon"],
                        }
            else:
                errors.append(f"({plat},{plon}) → API yanıt vermedi")
            if completed % 50 == 0 or completed == len(points):
                print(f"  [{city}/{district}] {completed}/{len(points)} nokta → {len(depots)} depot")

    await asyncio.gather(*[_query(lat, lon) for lat, lon in points])
    print(f"  [{city}/{district}] Grid tamamlandı: {len(depots)} unique depot")
    return depots, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--step", type=float, default=DEFAULT_STEP_DEG, help="Grid adımı (derece, varsayılan: 0.005≈500m)")
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_KM, help="Her noktadan depot arama yarıçapı (km)")
    parser.add_argument("--out", help="Çıktı JSON dosyası (varsayılan: stdout)")
    args = parser.parse_args()

    depots, errors = fetch_depots_grid(args.district, args.city, args.step, args.radius)

    if errors:
        for err in errors:
            print(f"[WARN] {err}", file=sys.stderr)

    result = list(depots.values())
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {args.out}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
