"""
Low-level API client for marketfiyati.org.tr.
All HTTP calls live here; no business logic.

Sync functions are kept for depot_grid.py.
Async functions (suffix _async) are used by scraper.py.
"""
import asyncio
import random
import time

from curl_cffi import requests as curl_requests
from curl_cffi.requests import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    BASE_API_URL,
    COMMON_HEADERS,
    DEPOT_RADIUS_KM,
    HARITA_API_URL,
    PAGE_DELAY,
    PAGE_SIZE,
    USER_AGENTS,
)

# AutoSuggestion response array field indices
_IDX_FULL_ADDRESS = 0
_IDX_DISTRICT = 5
_IDX_CITY = 6
_IDX_LON = 7
_IDX_LAT = 8

# Sync session — used by depot_grid.py
_SESSION = curl_requests.Session(impersonate="chrome124")

# Async session — used by scraper.py
# pool_connections=3: sunucu tarafında tek IP'den çok bağlantı açılmasını önler
_ASYNC_SESSION = AsyncSession(impersonate="chrome124", max_clients=3)


def _headers() -> dict:
    """Return common headers with a randomly chosen User-Agent."""
    return {**COMMON_HEADERS, "User-Agent": random.choice(USER_AGENTS)}


# ---------------------------------------------------------------------------
# Sync HTTP (kept for depot_grid.py)
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=3, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=False,
)
def _request(method: str, url: str, **kwargs):
    """HTTP request with tenacity exponential backoff on any error."""
    r = _SESSION.request(method, url, headers=_headers(), **kwargs)
    if r.status_code >= 500:
        raise Exception(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r


def _safe_request(method: str, url: str, **kwargs):
    """Wrapper that returns None instead of raising after all retries are exhausted."""
    try:
        return _request(method, url, **kwargs)
    except Exception as e:
        print(f"  [ERROR] Giving up: {e}")
        return None


def get_coordinates(district: str, city: str) -> tuple[float, float] | tuple[None, None]:
    """Return (lat, lon) for a district+city pair, or (None, None) on failure."""
    url = f"{HARITA_API_URL}/AutoSuggestion/Search"
    r = _safe_request("GET", url, params={"words": f"{district} {city}"}, timeout=15)
    if r is None:
        return None, None

    results = r.json()
    for row in results:
        if (row[_IDX_DISTRICT].lower() == district.lower()
                and row[_IDX_CITY].lower() == city.lower()):
            return row[_IDX_LAT], row[_IDX_LON]
    if results:
        return results[0][_IDX_LAT], results[0][_IDX_LON]
    return None, None


def get_nearest_depots(lat: float, lon: float) -> list[dict]:
    """Return list of depot dicts near (lat, lon)."""
    url = f"{BASE_API_URL}/nearest"
    r = _safe_request("POST", url,
                      json={"latitude": lat, "longitude": lon, "distance": DEPOT_RADIUS_KM},
                      timeout=15)
    return r.json() if r else []


def scrape_page(keywords: str, lat: float, lon: float, depot_ids: list[str], page: int) -> tuple[list[dict], int]:
    """Fetch a single page of products. Returns (products, total_available)."""
    url = f"{BASE_API_URL}/searchByCategories"
    r = _safe_request("POST", url,
                      json={
                          "menuCategory": True,
                          "keywords": keywords,
                          "pages": page,
                          "size": PAGE_SIZE,
                          "latitude": lat,
                          "longitude": lon,
                          "distance": DEPOT_RADIUS_KM,
                          "depots": depot_ids,
                      },
                      timeout=20)
    if r is None:
        return [], 0
    data = r.json()
    return data.get("content", []), data.get("numberOfFound", 0)


def scrape_all_pages(keywords: str, lat: float, lon: float, depot_ids: list[str]) -> list[dict]:
    """Fetch every page of a category until all products are retrieved."""
    all_products: list[dict] = []
    page = 0
    while True:
        products, total = scrape_page(keywords, lat, lon, depot_ids, page)
        all_products.extend(products)
        fetched = len(all_products)
        print(f"    page {page:>3}: {len(products):>3} products  (fetched {fetched}/{total})")
        if len(products) == 0 or fetched >= total:
            break
        page += 1
        time.sleep(random.uniform(*PAGE_DELAY))
    return all_products


# ---------------------------------------------------------------------------
# Async HTTP — used by scraper.py for parallel district scraping
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=3, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=False,
)
async def _async_request(method: str, url: str, **kwargs):
    """Async HTTP request with tenacity exponential backoff."""
    r = await _ASYNC_SESSION.request(method, url, headers=_headers(), **kwargs)
    if r.status_code == 429:
        raise Exception("HTTP 429 rate limited")
    if r.status_code >= 500:
        raise Exception(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r


async def _async_safe_request(method: str, url: str, sem: asyncio.Semaphore, **kwargs):
    """Throttled async request — acquires semaphore, returns None on total failure."""
    try:
        async with sem:
            # Semaphore içinde küçük jitter: aynı anda birden fazla istek olsa bile
            # sunucuya tam aynı milisaniyede ulaşmaz → burst azalır
            await asyncio.sleep(random.uniform(0.1, 0.4))
            return await _async_request(method, url, **kwargs)
    except Exception as e:
        print(f"  [ERROR] Giving up: {e}")
        return None


async def get_coordinates_async(
    district: str, city: str, sem: asyncio.Semaphore
) -> tuple[float, float] | tuple[None, None]:
    url = f"{HARITA_API_URL}/AutoSuggestion/Search"
    r = await _async_safe_request("GET", url, sem, params={"words": f"{district} {city}"}, timeout=15)
    if r is None:
        return None, None
    results = r.json()
    for row in results:
        if (row[_IDX_DISTRICT].lower() == district.lower()
                and row[_IDX_CITY].lower() == city.lower()):
            return row[_IDX_LAT], row[_IDX_LON]
    if results:
        return results[0][_IDX_LAT], results[0][_IDX_LON]
    return None, None


async def get_nearest_depots_async(lat: float, lon: float, sem: asyncio.Semaphore) -> list[dict]:
    url = f"{BASE_API_URL}/nearest"
    r = await _async_safe_request(
        "POST", url, sem,
        json={"latitude": lat, "longitude": lon, "distance": DEPOT_RADIUS_KM},
        timeout=15,
    )
    return r.json() if r else []


async def _scrape_page_async(
    keywords: str, lat: float, lon: float, depot_ids: list[str],
    page: int, sem: asyncio.Semaphore,
) -> tuple[list[dict], int]:
    url = f"{BASE_API_URL}/searchByCategories"
    r = await _async_safe_request(
        "POST", url, sem,
        json={
            "menuCategory": True,
            "keywords": keywords,
            "pages": page,
            "size": PAGE_SIZE,
            "latitude": lat,
            "longitude": lon,
            "distance": DEPOT_RADIUS_KM,
            "depots": depot_ids,
        },
        timeout=20,
    )
    if r is None:
        return [], 0
    data = r.json()
    return data.get("content", []), data.get("numberOfFound", 0)


async def scrape_all_pages_async(
    keywords: str, lat: float, lon: float,
    depot_ids: list[str], sem: asyncio.Semaphore,
    label: str = "",
) -> tuple[list[dict], int]:
    """Async version: fetch every page until all products retrieved.
    Returns (products, total_expected)."""
    all_products: list[dict] = []
    total_expected = 0
    page = 0
    while True:
        products, total = await _scrape_page_async(keywords, lat, lon, depot_ids, page, sem)
        if total:
            total_expected = total
        all_products.extend(products)
        fetched = len(all_products)
        print(f"    {label} page {page:>3}: {len(products):>3} products  (fetched {fetched}/{total})")
        if len(products) == 0 or fetched >= total:
            break
        page += 1
        await asyncio.sleep(random.uniform(*PAGE_DELAY))
    return all_products, total_expected
