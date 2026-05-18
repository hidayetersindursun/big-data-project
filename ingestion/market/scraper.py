"""
Main orchestrator — async parallel scraper.

Usage:
    python scraper.py                    # Stale data only (< 24h threshold)
    python scraper.py --force            # Re-scrape everything
    python scraper.py --city İstanbul    # Only one city
    python scraper.py --district Kadıköy # Only one district (all cities)
    python scraper.py --category Meyve   # Only one category
    python scraper.py --concurrency 10    # Max concurrent HTTP requests (default: 5)
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime

# Allow running as `python ingestion/scraper.py` from project root
sys.path.insert(0, os.path.dirname(__file__))

from client import (
    get_coordinates_async,
    get_nearest_depots_async,
    scrape_all_pages_async,
)
from config import CATEGORIES, CATEGORY_API_KEYWORD, CATEGORY_DELAY, CITIES
from depot_grid import fetch_depots_grid, fetch_depots_grid_async
from state import is_stale, load_state, save_state, update_state

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEPOTS_DIR = os.path.join(DATA_DIR, "depots")
FETCH_LOG = os.path.join(DEPOTS_DIR, "fetch_log.json")


class _RateLimiter:
    """
    Adaptive rate limiter — hata oranı artınca otomatik yavaşlar.

    Her başarısız istek error_count'u artırır.
    Her başarılı istek azaltır.
    wait() çağrıldığında error_count'a göre delay ekler.
    Böylece concurrency değiştirilmeden throughput düşürülür.
    """

    def __init__(self, threshold: int = 3, max_delay: float = 60.0):
        self._count = 0
        self._threshold = threshold
        self._max_delay = max_delay
        self._lock = asyncio.Lock()

    async def error(self):
        async with self._lock:
            self._count = min(self._count + 1, 20)

    async def success(self):
        async with self._lock:
            self._count = max(self._count - 1, 0)

    async def wait(self):
        """Hata oranı yüksekse istek öncesi bekle."""
        if self._count >= self._threshold:
            delay = min(self._count * 3.0, self._max_delay)
            print(f"  [RATE LIMIT] Hata sayısı={self._count}, {delay:.0f}s bekleniyor...")
            await asyncio.sleep(delay + random.uniform(0, delay * 0.2))

    @property
    def error_count(self) -> int:
        return self._count


# ---------------------------------------------------------------------------

def location_key(district: str, city: str) -> str:
    return f"{district}_{city}"


def output_path(district: str, city: str, category: str, date: str) -> str:
    safe_cat = category.replace(" ", "_").replace("/", "-")
    folder = os.path.join(DATA_DIR, f"{city}_{district}", date)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{safe_cat}.jsonl")


def enrich(products: list[dict], district: str, city: str, scraped_at: str) -> list[dict]:
    for p in products:
        p["_district"] = district
        p["_city"] = city
        p["_scraped_at"] = scraped_at
    return products


def write_jsonl(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _append_fetch_log(city: str, district: str, errors: list[str]) -> None:
    try:
        with open(FETCH_LOG, encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        log = []
    log.append({
        "ts": datetime.now().replace(microsecond=0).isoformat(),
        "city": city,
        "district": district,
        "errors": errors,
    })
    with open(FETCH_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------

async def _scrape_category(
    district: str, city: str, category: str,
    lat: float, lon: float, depot_ids: list[str],
    sem: asyncio.Semaphore,
    state: dict, state_lock: asyncio.Lock, counters: dict,
    incomplete: list, incomplete_lock: asyncio.Lock,
    rate_limiter: _RateLimiter,
    known_total: int = 0,
) -> None:
    """
    Tek kategori için tüm sayfaları çeker.

    known_total: önceki denemeden bilinen toplam ürün sayısı.
    Retry'da API tamamen kapalıysa (total_expected=0 döner) bu değer
    kullanılarak yanlış OK kararı önlenir.
    """
    loc_key = location_key(district, city)
    label = f"[{city}/{district}][{category}]"
    print(f"  {label} scraping...")

    # Hata oranı yüksekse istek öncesi bekle (adaptive rate limit)
    await rate_limiter.wait()

    api_keyword = CATEGORY_API_KEYWORD.get(category, category)
    products, total_expected = await scrape_all_pages_async(
        api_keyword, lat, lon, depot_ids, sem, label=label
    )
    fetched = len(products)

    # -1: tüm retry'lar tükendi, API tamamen ulaşılamaz — INCOMPLETE'e at, state'e yazma
    if total_expected == -1:
        await rate_limiter.error()
        print(f"  {label} → request failed entirely — INCOMPLETE, will retry")
        async with incomplete_lock:
            incomplete.append((district, city, category, lat, lon, depot_ids, known_total))
        return

    # Retry sırasında API tamamen kapalıysa total_expected=0 döner.
    # known_total ile gerçek beklenen sayıyı koru.
    effective_total = total_expected if total_expected > 0 else known_total
    ok = effective_total == 0 or fetched >= effective_total * 0.95

    if fetched > 0:
        await rate_limiter.success()
    else:
        await rate_limiter.error()

    scraped_at = datetime.now().replace(microsecond=0).isoformat()
    date = scraped_at[:10]
    path = output_path(district, city, category, date)

    if ok and fetched > 0:
        write_jsonl(path, enrich(products, district, city, scraped_at))
        async with state_lock:
            update_state(state, loc_key, category, fetched)
            save_state(state)
        counters["scraped"] += fetched
        print(f"  {label} → {fetched} products saved  [OK]")

    elif ok and fetched == 0 and effective_total == 0:
        # API gerçekten 0 ürün döndürdü (boş kategori) — state'e yaz
        write_jsonl(path, [])
        async with state_lock:
            update_state(state, loc_key, category, 0)
            save_state(state)
        print(f"  {label} → 0 products (empty category)  [OK]")

    else:
        # Kısmen çekildi ya da retry'da API kapalıydı
        if fetched > 0:
            # Kısmi veriyi kaydet (bir sonraki retry birleştirmez, üstüne yazar)
            write_jsonl(path, enrich(products, district, city, scraped_at))
        pct = fetched / effective_total if effective_total else 0
        print(f"  {label} → {fetched}/{effective_total} ({pct:.0%}) — INCOMPLETE, will retry")
        async with incomplete_lock:
            incomplete.append((district, city, category, lat, lon, depot_ids, effective_total))


async def _scrape_district(
    district: str,
    city: str,
    stale_cats: list[str],
    sem: asyncio.Semaphore,
    grid_sem: asyncio.Semaphore,
    state: dict,
    state_lock: asyncio.Lock,
    counters: dict,
    incomplete: list,
    incomplete_lock: asyncio.Lock,
    rate_limiter: _RateLimiter,
    progress: dict,
    progress_lock: asyncio.Lock,
    no_grid: bool = True,
) -> None:
    tag = f"[{city}/{district}]"
    t0 = time.time()
    scraped_before = counters["scraped"]

    depot_json = os.path.join(DEPOTS_DIR, f"{city}_{district}.json")
    if os.path.exists(depot_json):
        with open(depot_json, encoding="utf-8") as f:
            depots = json.load(f)
        lat, lon = await get_coordinates_async(district, city, sem)
        if lat is None and depots:
            lat, lon = depots[0]["lat"], depots[0]["lon"]
    else:
        lat, lon = await get_coordinates_async(district, city, sem)
        if lat is None:
            print(f"  {tag} [WARN] coordinates not found, skipping")
            async with progress_lock:
                progress["done"] += 1
            return

        if no_grid:
            depots = await get_nearest_depots_async(lat, lon, sem)
            if not depots:
                # Kırsal ilçelerde 10km yetmeyebilir — 25km ve 50km ile dene
                for fallback_radius in (25, 50):
                    depots = await get_nearest_depots_async(lat, lon, sem, radius_km=fallback_radius)
                    if depots:
                        print(f"  {tag} nearest: {fallback_radius}km radius ile {len(depots)} depot bulundu")
                        break
            if not depots:
                print(f"  {tag} [WARN] no depots found (10/25/50km), skipping")
                async with progress_lock:
                    progress["done"] += 1
                return
        else:
            print(f"  {tag} depot JSON not found — running grid search...")
            async with grid_sem:  # tek seferde bir ilçe grid search yapar
                depots_dict, grid_errors = await fetch_depots_grid_async(district, city, asyncio.Semaphore(1))

            if depots_dict:
                depot_json_path = os.path.join(DEPOTS_DIR, f"{city}_{district}.json")
                with open(depot_json_path, "w", encoding="utf-8") as f:
                    json.dump(list(depots_dict.values()), f, ensure_ascii=False, indent=2)
                depots = list(depots_dict.values())
            else:
                depots = await get_nearest_depots_async(lat, lon, sem)
                if not depots:
                    print(f"  {tag} [WARN] no depots found, skipping")
                    if grid_errors:
                        _append_fetch_log(city, district, grid_errors)
                    async with progress_lock:
                        progress["done"] += 1
                    return

            if grid_errors:
                _append_fetch_log(city, district, grid_errors)

    depot_ids = [d["id"] for d in depots]
    await asyncio.gather(*[
        _scrape_category(
            district, city, cat, lat, lon, depot_ids,
            sem, state, state_lock, counters, incomplete, incomplete_lock,
            rate_limiter,
        )
        for cat in stale_cats
    ])

    elapsed = time.time() - t0
    district_products = counters["scraped"] - scraped_before
    async with progress_lock:
        progress["done"] += 1
        done = progress["done"]
        total = progress["total"]
    pct = done / total * 100
    mins, secs = divmod(int(elapsed), 60)
    dur = f"{mins}dk {secs}sn" if mins else f"{secs}sn"
    print(f"[{done}/{total} | %{pct:.0f}] ✓ {city}/{district} — {district_products} ürün, {len(stale_cats)} kat, {dur}")


async def run_async(
    force: bool = False,
    city_filter: str | None = None,
    district_filter: str | None = None,
    category_filter: str | None = None,
    concurrency: int = 10,
    exclude_cities: list[str] | None = None,
    no_grid: bool = True,
) -> None:
    state = load_state()
    exclude_cities = exclude_cities or []
    categories = [c for c in CATEGORIES if not category_filter or c == category_filter]
    cities = {
        k: v for k, v in CITIES.items()
        if (not city_filter or k == city_filter) and k not in exclude_cities
    }

    sem = asyncio.Semaphore(concurrency)
    grid_sem = asyncio.Semaphore(1)  # aynı anda sadece 1 ilçe grid search yapar
    state_lock = asyncio.Lock()
    counters = {"scraped": 0, "skipped": 0}
    incomplete: list = []
    incomplete_lock = asyncio.Lock()
    rate_limiter = _RateLimiter(threshold=3, max_delay=60.0)
    progress_lock = asyncio.Lock()

    task_args = []
    for city, districts in cities.items():
        if district_filter:
            districts = [d for d in districts if d == district_filter]

        for district in districts:
            loc_key = location_key(district, city)
            stale_cats = [c for c in categories if force or is_stale(state, loc_key, c)]
            if not stale_cats:
                counters["skipped"] += len(categories)
                continue
            task_args.append((district, city, stale_cats))

    progress = {"done": 0, "total": len(task_args)}
    total_cats = sum(len(cats) for _, _, cats in task_args)

    print(f"\n{'='*60}")
    print(f"  {len(task_args)} ilçe | {total_cats} kategori görevi | concurrency={concurrency}")
    city_summary = {}
    for _, city, cats in task_args:
        city_summary[city] = city_summary.get(city, 0) + 1
    for city, cnt in city_summary.items():
        print(f"    {city}: {cnt} ilçe")
    print(f"{'='*60}\n")

    tasks = [
        _scrape_district(
            district, city, stale_cats, sem, grid_sem, state, state_lock,
            counters, incomplete, incomplete_lock, rate_limiter,
            progress, progress_lock, no_grid=no_grid,
        )
        for district, city, stale_cats in task_args
    ]
    await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Retry: INCOMPLETE kategorileri exponential backoff + düşük concurrency
    # ------------------------------------------------------------------
    retry_concurrency = max(1, concurrency // 3)
    attempt = 0
    retry_wait = 30  # ilk retry öncesi bekleme (saniye)
    max_attempts = 3

    while incomplete and attempt < max_attempts:
        attempt += 1
        batch = incomplete[:]
        incomplete.clear()

        print(f"\nRetry attempt {attempt}/{max_attempts}: {len(batch)} incomplete categories "
              f"(concurrency={retry_concurrency}) — waiting {retry_wait}s first...\n")
        await asyncio.sleep(retry_wait)
        retry_wait = min(retry_wait * 2, 300)  # 30 → 60 → 120 → 300s (max 5 dk)

        retry_sem = asyncio.Semaphore(retry_concurrency)
        retry_rate_limiter = _RateLimiter(threshold=2, max_delay=60.0)

        await asyncio.gather(*[
            _scrape_category(
                district, city, category, lat, lon, depot_ids,
                retry_sem, state, state_lock, counters, incomplete, incomplete_lock,
                retry_rate_limiter,
                known_total=known_total,
            )
            for district, city, category, lat, lon, depot_ids, known_total in batch
        ])

    if incomplete:
        print(f"\n[WARN] {len(incomplete)} categories still incomplete after {max_attempts} attempts:")
        for district, city, category, *_, known_total in incomplete:
            print(f"  [{city}/{district}][{category}] expected ~{known_total} products")
        print("  → State not updated — will be retried on next run (tomorrow)")

    print(
        f"\n=== Done: {counters['scraped']} products scraped, "
        f"{counters['skipped']} categories skipped (fresh) ==="
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="marketfiyati.org.tr async scraper")
    parser.add_argument("--force", action="store_true", help="Re-scrape even fresh data")
    parser.add_argument("--city", metavar="NAME", help="Only scrape this city")
    parser.add_argument("--exclude", nargs="+", default=[], metavar="CITY",
                        help="Skip these cities (space-separated)")
    parser.add_argument("--district", metavar="NAME", help="Only scrape this district")
    parser.add_argument("--category", metavar="NAME", help="Only scrape this category")
    parser.add_argument(
        "--concurrency", metavar="N", type=int, default=5,
        help="Max concurrent HTTP requests (default: 5, lower if rate-limited)",
    )
    parser.add_argument(
        "--grid", action="store_true",
        help="Run grid search for cities without a pre-built depot file (yavaş, daha fazla depot)",
    )
    args = parser.parse_args()

    asyncio.run(run_async(
        force=args.force,
        city_filter=args.city,
        district_filter=args.district,
        category_filter=args.category,
        concurrency=args.concurrency,
        exclude_cities=args.exclude,
        no_grid=not args.grid,
    ))


if __name__ == "__main__":
    main()
