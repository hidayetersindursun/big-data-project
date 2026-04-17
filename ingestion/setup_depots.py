"""
One-time setup: ilçe başına tam depot listesi oluşturur.

Algoritma:
  1. Nominatim (OSM) ile her ilçenin gerçek bounding box'ını sırayla çeker
     (Nominatim rate limit: 1 req/s → sequential, 1.1s sleep)
  2. Bbox boyutuna göre adaptif grid: hedef ~150 nokta, gap kalmayacak radius
     (küçük ilçe → ince grid; büyük ilçe → kaba grid ama tam kapsam)
  3. Her grid noktasından /nearest → depot deduplicate → JSON

Kullanım:
    python ingestion/setup_depots.py                    # Tüm şehirler
    python ingestion/setup_depots.py --city İstanbul    # Sadece bir şehir
    python ingestion/setup_depots.py --district Beşiktaş
    python ingestion/setup_depots.py --concurrency 5    # Default: 5
    python ingestion/setup_depots.py --force            # Mevcut JSON'ları da yenile
"""
import argparse
import asyncio
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from client import _ASYNC_SESSION, _async_request, get_coordinates_async
from config import BASE_API_URL, CITIES

DEPOTS_DIR   = os.path.join(os.path.dirname(__file__), "depots")
BBOX_CACHE   = os.path.join(os.path.dirname(__file__), "depots", "bbox_cache.json")

NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
FETCH_LOG      = os.path.join(os.path.dirname(__file__), "depots", "fetch_log.json")
TARGET_POINTS  = 150    # hedef grid nokta sayısı / ilçe
MIN_STEP_DEG   = 0.005  # ~500m — minimum adım (küçük ilçelerde)
MIN_RADIUS_KM  = 1.0    # minimum arama yarıçapı
MAX_RADIUS_KM  = 5.0    # maksimum arama yarıçapı (API kısıtı)

# Nominatim adres alanlarında ilçe adını arayacağımız anahtarlar
_ADDR_KEYS = ("city_district", "suburb", "quarter", "town", "municipality", "county")


# ---------------------------------------------------------------------------
# Nominatim — bounding box
# ---------------------------------------------------------------------------

async def _get_bbox(district: str, city: str) -> tuple[float, float, float, float] | None:
    """
    Nominatim'den ilçe bounding box'ını döner: (south, north, west, east).
    Bulamazsa None.  Sequential çağrılmalı (rate limit: 1 req/s).
    """
    try:
        r = await _ASYNC_SESSION.request(
            "GET", NOMINATIM_URL,
            params={
                "q": f"{district}, {city}, Turkey",
                "format": "json",
                "limit": 5,
                "addressdetails": 1,
            },
            headers={"User-Agent": "bigdata-price-scraper/1.0 (academic research)"},
            timeout=10,
        )
        results = r.json()
        # İlçe adıyla eşleşen sonucu tercih et
        for item in results:
            addr = item.get("address", {})
            if any(addr.get(k, "").lower() == district.lower() for k in _ADDR_KEYS):
                bb = item["boundingbox"]
                return float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        # Eşleşme yoksa ilk sonucu kullan
        if results:
            bb = results[0]["boundingbox"]
            return float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
    except Exception as e:
        print(f"  [WARN] Nominatim error for {district}: {e}")
    return None


# ---------------------------------------------------------------------------
# Adaptif grid
# ---------------------------------------------------------------------------

def _adaptive_grid(
    south: float, north: float, west: float, east: float,
) -> tuple[list[tuple[float, float]], float]:
    """
    Bbox üzerinde adaptif grid + arama yarıçapı hesaplar.

    Gap garantisi: radius = step → daireler köşegenini (step*√2/2) aşar,
    her nokta mutlaka en az bir daire tarafından kapsanır.

    Returns:
        points    — (lat, lon) listesi
        radius_km — her nokta için /nearest arama yarıçapı
    """
    mid_lat  = (north + south) / 2
    lat_km   = (north - south) * 111.0
    lon_km   = (east  - west)  * 111.0 * math.cos(math.radians(mid_lat))
    area_km2 = lat_km * lon_km

    step_km  = max(MIN_STEP_DEG * 111.0, math.sqrt(max(area_km2, 0.01) / TARGET_POINTS))
    step_deg = max(MIN_STEP_DEG, step_km / 111.0)

    radius_km = min(MAX_RADIUS_KM, max(MIN_RADIUS_KM, step_km))

    points: list[tuple[float, float]] = []
    lat = south
    while lat <= north + 1e-9:
        lon = west
        while lon <= east + 1e-9:
            points.append((round(lat, 6), round(lon, 6)))
            lon += step_deg
        lat += step_deg

    return points, round(radius_km, 2)


# ---------------------------------------------------------------------------
# /nearest çağrısı (tek grid noktası)
# ---------------------------------------------------------------------------

async def _nearest(
    lat: float, lon: float, radius_km: float, sem: asyncio.Semaphore,
) -> tuple[list[dict], bool]:
    """Returns (depots, success). success=False means all retries failed."""
    async with sem:
        try:
            r = await _async_request(
                "POST", f"{BASE_API_URL}/nearest",
                json={"latitude": lat, "longitude": lon, "distance": radius_km},
                timeout=15,
            )
            return (r.json() if r else []), True
        except Exception as e:
            print(f"  [WARN] /nearest failed at ({lat:.4f},{lon:.4f}): {e}")
            return [], False


# ---------------------------------------------------------------------------
# İlçe başına tam depot listesi
# ---------------------------------------------------------------------------

async def build_district_depots(
    district: str,
    city: str,
    bbox: tuple[float, float, float, float] | None,
    fallback_center: tuple[float | None, float | None],
    sem: asyncio.Semaphore,
    force: bool = False,
) -> None:
    out_path = os.path.join(DEPOTS_DIR, f"{city}_{district}.json")
    tag = f"[{city}/{district}]"

    if not force and os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            print(f"  {tag} already exists ({len(existing)} depots), skipping. Use --force to refresh.")
            return
        print(f"  {tag} existing file has 0 depots — re-fetching...")

    if bbox:
        south, north, west, east = bbox
        points, radius_km = _adaptive_grid(south, north, west, east)
        area_km2 = (north - south) * 111.0 * (east - west) * 111.0 * math.cos(math.radians((north + south) / 2))
        print(f"  {tag} bbox≈{area_km2:.0f}km² → {len(points)} grid pts, r={radius_km}km")
    else:
        lat, lon = fallback_center
        if lat is None:
            print(f"  {tag} [WARN] bbox + coordinates not found, skipping")
            return
        south, north = lat - 0.03, lat + 0.03
        west,  east  = lon - 0.03, lon + 0.03
        points, radius_km = _adaptive_grid(south, north, west, east)
        print(f"  {tag} [fallback ±0.03°] → {len(points)} grid pts, r={radius_km}km")

    results = await asyncio.gather(*[_nearest(p[0], p[1], radius_km, sem) for p in points])

    depots: dict[str, dict] = {}
    failed = sum(1 for _, ok in results if not ok)
    for depot_list, _ in results:
        for d in depot_list:
            did = d.get("id")
            if did and did not in depots:
                depots[did] = {
                    "id": did,
                    "name": d.get("sellerName", ""),
                    "market": d.get("marketName", ""),
                    "lat": d["location"]["lat"],
                    "lon": d["location"]["lon"],
                }

    fail_rate = failed / len(points) if points else 0
    status = "OK" if fail_rate < 0.05 else "INCOMPLETE"
    if status == "INCOMPLETE":
        print(f"  {tag} [!] {failed}/{len(points)} grid points failed ({fail_rate:.0%}) — depot count unreliable, re-run needed")

    # fetch_log.json'a yaz
    log: dict = {}
    if os.path.exists(FETCH_LOG):
        with open(FETCH_LOG, encoding="utf-8") as f:
            log = json.load(f)
    log[f"{city}_{district}"] = {
        "total_pts": len(points),
        "failed_pts": failed,
        "fail_rate": round(fail_rate, 3),
        "depot_count": len(depots),
        "status": status,
    }
    os.makedirs(DEPOTS_DIR, exist_ok=True)
    with open(FETCH_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(list(depots.values()), f, ensure_ascii=False, indent=2)

    print(f"  {tag} {len(depots)} unique depots saved → {os.path.relpath(out_path)}  [{status}, failures={failed}/{len(points)}]")


# ---------------------------------------------------------------------------
# Orkestrasyon
# ---------------------------------------------------------------------------

async def run_async(
    city_filter: str | None = None,
    district_filter: str | None = None,
    concurrency: int = 5,
    force: bool = False,
) -> None:
    cities = {k: v for k, v in CITIES.items() if not city_filter or k == city_filter}

    district_list: list[tuple[str, str]] = []
    for city, districts in cities.items():
        if district_filter:
            districts = [d for d in districts if d == district_filter]
        for district in districts:
            district_list.append((district, city))

    # ------------------------------------------------------------------
    # Phase 1: Nominatim — cache'ten oku, eksikleri sırayla çek (1 req/s)
    # ------------------------------------------------------------------
    os.makedirs(DEPOTS_DIR, exist_ok=True)
    cache: dict[str, list] = {}
    if os.path.exists(BBOX_CACHE):
        with open(BBOX_CACHE, encoding="utf-8") as f:
            cache = json.load(f)

    bboxes: dict[tuple[str, str], tuple | None] = {}
    need_fetch = []
    for district, city in district_list:
        key = f"{city}_{district}"
        if key in cache:
            bboxes[(district, city)] = tuple(cache[key]) if cache[key] else None
        else:
            need_fetch.append((district, city))

    if need_fetch:
        print(f"Phase 1: Nominatim bbox lookup ({len(need_fetch)} new districts, sequential)...\n")
        for district, city in need_fetch:
            bbox = await _get_bbox(district, city)
            bboxes[(district, city)] = bbox
            key = f"{city}_{district}"
            cache[key] = list(bbox) if bbox else None
            if bbox:
                s, n, w, e = bbox
                area = (n - s) * 111.0 * (e - w) * 111.0 * math.cos(math.radians((n + s) / 2))
                print(f"  [{city}/{district}] bbox OK  ≈{area:.0f} km²")
            else:
                print(f"  [{city}/{district}] bbox FAILED — will use center±0.03° fallback")
            await asyncio.sleep(1.1)
        with open(BBOX_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    else:
        print(f"Phase 1: All {len(district_list)} districts loaded from bbox cache. Skipping Nominatim.\n")
        for district, city in district_list:
            if bboxes[(district, city)]:
                s, n, w, e = bboxes[(district, city)]
                area = (n - s) * 111.0 * (e - w) * 111.0 * math.cos(math.radians((n + s) / 2))
                print(f"  [{city}/{district}] cached ≈{area:.0f} km²")

    # ------------------------------------------------------------------
    # Phase 2: Fallback — bbox alamadık, coordinate API'den merkez al
    # ------------------------------------------------------------------
    sem = asyncio.Semaphore(concurrency)
    no_bbox = [(d, c) for d, c in district_list if bboxes[(d, c)] is None]
    centers: dict[tuple[str, str], tuple] = {}
    if no_bbox:
        print(f"\nPhase 2: Fetching fallback coordinates for {len(no_bbox)} districts...")
        coord_results = await asyncio.gather(*[
            get_coordinates_async(d, c, sem) for d, c in no_bbox
        ])
        centers = {(d, c): cr for (d, c), cr in zip(no_bbox, coord_results)}

    # ------------------------------------------------------------------
    # Phase 3: Paralel grid search
    # ------------------------------------------------------------------
    tasks = [
        build_district_depots(
            d, c,
            bboxes[(d, c)],
            centers.get((d, c), (None, None)),
            sem,
            force,
        )
        for d, c in district_list
    ]
    print(f"\nPhase 3: Grid search for {len(tasks)} districts (concurrency={concurrency})...\n")
    await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Phase 4: INCOMPLETE ilçeleri COMPLETE olana kadar döngüyle yenile
    # ------------------------------------------------------------------
    retry_concurrency = max(1, concurrency // 3)
    attempt = 0
    while True:
        if not os.path.exists(FETCH_LOG):
            break
        with open(FETCH_LOG, encoding="utf-8") as f:
            log = json.load(f)

        retry_list = [
            (key.split("_", 1)[1], key.split("_", 1)[0])  # (district, city)
            for key, v in log.items()
            if v["status"] == "INCOMPLETE"
            and any(key == f"{c}_{d}" for d, c in district_list)
        ]

        if not retry_list:
            break

        attempt += 1
        print(f"\nPhase 4 (attempt {attempt}): {len(retry_list)} INCOMPLETE district — retrying (concurrency={retry_concurrency})...\n")
        retry_sem = asyncio.Semaphore(retry_concurrency)
        retry_tasks = [
            build_district_depots(d, c, bboxes.get((d, c)), centers.get((d, c), (None, None)), retry_sem, force=True)
            for d, c in retry_list
        ]
        await asyncio.gather(*retry_tasks)
        await asyncio.sleep(5)  # kısa bekleme sonraki deneme öncesi

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Depot grid search — one-time setup")
    parser.add_argument("--city", metavar="NAME")
    parser.add_argument("--district", metavar="NAME")
    parser.add_argument("--concurrency", type=int, default=5, metavar="N")
    parser.add_argument("--force", action="store_true", help="Mevcut JSON'ları yenile")
    args = parser.parse_args()

    asyncio.run(run_async(args.city, args.district, args.concurrency, args.force))


if __name__ == "__main__":
    main()
