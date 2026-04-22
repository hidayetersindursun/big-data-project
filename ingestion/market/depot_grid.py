"""
Grid search: ilçenin bounding box'ını tarayarak tüm unique depotları çeker.
Her grid noktasından /nearest sorgusu atar, depotId ile deduplicate eder.

Kullanım:
    python ingestion/depot_grid.py --district Bayrampaşa --city İstanbul --radius 1 --step 0.005
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from client import get_coordinates, _request
from config import BASE_API_URL

# ~500m adım için 0.005 derece (enlem/boylam yaklaşımı)
DEFAULT_STEP_DEG = 0.005
DEFAULT_RADIUS_KM = 1
DEFAULT_SPAN_DEG = 0.03  # ~3km x 3km bounding box (ilçe merkezinden her yöne)


def grid_points(center_lat, center_lon, span=DEFAULT_SPAN_DEG, step=DEFAULT_STEP_DEG):
    """Bounding box içindeki grid noktalarını üret."""
    points = []
    lat = center_lat - span
    while lat <= center_lat + span:
        lon = center_lon - span
        while lon <= center_lon + span:
            points.append((round(lat, 6), round(lon, 6)))
            lon += step
        lat += step
    return points


def fetch_depots_grid(district, city, span=DEFAULT_SPAN_DEG, step=DEFAULT_STEP_DEG, radius=DEFAULT_RADIUS_KM):
    errors: list[str] = []

    lat, lon = get_coordinates(district, city)
    if lat is None:
        errors.append(f"[{district},{city}] koordinat bulunamadı")
        return {}, errors

    print(f"Merkez: lat={lat:.5f}, lon={lon:.5f}")
    points = grid_points(lat, lon, span=span, step=step)
    print(f"Grid: {len(points)} nokta, radius={radius}km, step={step}°")

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
            if r is None and not any(f"({plat},{plon})" in e for e in errors):
                errors.append(f"({plat},{plon}) → API yanıt vermedi")
        print(f"  [{i+1}/{len(points)}] ({plat}, {plon}) → {len(depots)} unique depot", end="\r")
        time.sleep(0.5)

    print(f"\nToplam: {len(depots)} unique depot")
    return depots, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--span", type=float, default=DEFAULT_SPAN_DEG, help="Merkezdten yarıçap (derece)")
    parser.add_argument("--step", type=float, default=DEFAULT_STEP_DEG, help="Grid adımı (derece)")
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_KM, help="Her noktadan depot arama yarıçapı (km)")
    parser.add_argument("--out", help="Çıktı JSON dosyası (varsayılan: stdout)")
    args = parser.parse_args()

    depots, errors = fetch_depots_grid(args.district, args.city, args.span, args.step, args.radius)

    if errors:
        import sys
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
