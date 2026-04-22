"""
TCMB EVDS ingestion module.
Döviz kurları ve enflasyon serilerini 2003'ten bugüne çeker.
Çıktı: tcmb/data/{seri_adı}.jsonl  (her satır bir gözlem)
State: tcmb/data/state.json        (seri başına son çekilen tarih)

Kullanım:
    python tcmb/tcmb_evds.py              # sadece stale serileri güncelle
    python tcmb/tcmb_evds.py --force      # hepsini baştan çek
    python tcmb/tcmb_evds.py --full       # 2003'ten tam geçmişi çek
    python tcmb/tcmb_evds.py --discover   # EVDS kategori ağacını yazdır
"""

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("EVDS_API_KEY", "3Oo5rGdWkp")
BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_FILE = DATA_DIR / "state.json"

HISTORICAL_START = "01-01-2003"
DEFAULT_START    = "01-01-2024"

# EVDS frekans kodları (Kılavuz s.3):
#   1=Günlük, 2=İşgünü, 3=Haftalık, 4=Ayda 2 Kez, 5=Aylık, 6=3 Aylık, 7=6 Aylık, 8=Yıllık
# Formül kodları: 0=Ham, 1=Yüzde Değişim, 2=Fark, 3=Yıllık Yüzde Değişim (YoY),
#                 4=Yıllık Fark, 5=Yıl Sonuna Göre %Değ, 6=Yıl Sonuna Göre Fark,
#                 7=Hareketli Ortalama, 8=Hareketli Toplam
# aggregationTypes: avg, min, max, first, last, sum  (STRING! sayısal değer 400 verir)

BATCHES = [
    {
        "name": "fx_daily",
        "freq": 1,                         # Günlük
        "series": [
            {"code": "TP.DK.USD.A.YTL", "name": "usd_try_alis",  "formula": 0, "agg": "last", "start": DEFAULT_START},
            {"code": "TP.DK.USD.S.YTL", "name": "usd_try_satis", "formula": 0, "agg": "last", "start": DEFAULT_START},
            {"code": "TP.DK.EUR.A.YTL", "name": "eur_try_alis",  "formula": 0, "agg": "last", "start": DEFAULT_START},
            {"code": "TP.DK.EUR.S.YTL", "name": "eur_try_satis", "formula": 0, "agg": "last", "start": DEFAULT_START},
            {"code": "TP.DK.GBP.A.YTL", "name": "gbp_try_alis",  "formula": 0, "agg": "last", "start": DEFAULT_START},
        ],
    },
    {
        "name": "inflation_monthly",
        "freq": 5,                         # Aylık (4 DEĞİL — 4 "ayda 2 kez")
        "series": [
            # YoY yüzde değişim → formula=3
            {"code": "TP.FE.OKTG01", "name": "tufe_genel_yoy",      "formula": 3, "agg": "avg", "start": DEFAULT_START},
            {"code": "TP.FE.OKTG02", "name": "tufe_cekirdek_yoy",   "formula": 3, "agg": "avg", "start": DEFAULT_START},
            {"code": "TP.FE.OKTG05", "name": "tufe_islem_disi_yoy", "formula": 3, "agg": "avg", "start": DEFAULT_START},
            {"code": "TP.FG.J0",     "name": "tufe_gida_yoy",       "formula": 3, "agg": "avg", "start": DEFAULT_START},
            {"code": "TP.FG.J01",    "name": "yiufe_tarim_yoy",     "formula": 3, "agg": "avg", "start": DEFAULT_START},
            {"code": "TP.FG.J011",   "name": "yiufe_genel_yoy",     "formula": 3, "agg": "avg", "start": DEFAULT_START},
        ],
    },
]

SERIES = [s for b in BATCHES for s in b["series"]]

STALE_DAYS = 1

# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({"key": API_KEY})

# Kısa, makul backoff. 4xx (client error) için zaten retry etmiyoruz.
BACKOFF = [2, 5, 15]
TIMEOUT = 30

# EVDS istek başına ~1000 gözlem limiti vardır; daha büyük aralıklarda
# cevap kesilir ve sadece son 1000 kayıt döner. Bunu frekansa göre pencerelere
# bölmek zorundayız.
# Her frekans için güvenli tek-istek pencere uzunluğu (gün).
WINDOW_DAYS: dict[int, int] = {
    1: 600,        # Günlük      (~1.6 yıl × ~365 gün = 600 gözlem < 1000)
    2: 800,        # İşgünü      (~3.2 yıl × ~250 = 800)
    3: 6000,       # Haftalık    (6000/7 ≈ 860 hafta)
    4: 30000,      # Ayda 2 Kez  (çok büyük pencere güvenli)
    5: 27000,      # Aylık       (900 ay ≈ 75 yıl)
    6: 80000,      # 3 Aylık
    7: 160000,     # 6 Aylık
    8: 320000,     # Yıllık
}


def _get(path_params: str) -> dict:
    """HTTP GET. 4xx -> retry yok (parametre hatası). 5xx / network -> retry."""
    url = f"{BASE_URL}/{path_params}&type=json"
    last_exc: Exception | None = None
    for attempt in range(len(BACKOFF) + 1):
        try:
            r = SESSION.get(url, timeout=TIMEOUT)
            # 4xx → kalıcı hata, retry etme
            if 400 <= r.status_code < 500:
                try:
                    body = r.json()
                except ValueError:
                    body = {"message": r.text[:200]}
                raise requests.HTTPError(
                    f"HTTP {r.status_code} — {body.get('message', body)} — URL: {url}"
                )
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            raise
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt == len(BACKOFF):
                raise
            wait = BACKOFF[attempt]
            print(f"  ⚠  {exc} — {wait}s bekleyip tekrar deneniyor")
            time.sleep(wait)
    if last_exc:
        raise last_exc
    return {}


# ---------------------------------------------------------------------------
# EVDS API helpers
# ---------------------------------------------------------------------------

def _col_for(series: dict) -> str:
    """EVDS yanıtında seriye karşılık gelen kolon adını üretir.
    Formula=0 ise saf kod (. -> _). Formula>0 ise 'KOD-FORMULA' eklenir."""
    col = series["code"].replace(".", "_")
    if series.get("formula", 0) and series["formula"] != 0:
        col = f"{col}-{series['formula']}"
    return col


def _fetch_batch_single(series_list: list[dict], start: str, end: str, freq: int) -> dict[str, list[dict]]:
    """Tek HTTP isteği. Büyük aralıklar için `fetch_batch` kullanın."""
    codes    = "-".join(s["code"] for s in series_list)
    formulas = "-".join(str(s.get("formula", 0)) for s in series_list)
    aggs     = "-".join(s.get("agg", "avg") for s in series_list)

    data = _get(
        f"series={codes}&startDate={start}&endDate={end}"
        f"&frequency={freq}&aggregationTypes={aggs}&formulas={formulas}"
    )
    items = data.get("items", [])

    result: dict[str, list[dict]] = {s["name"]: [] for s in series_list}

    for item in items:
        tarih = item.get("Tarih", "")
        if not tarih:
            continue
        for s in series_list:
            col = _col_for(s)
            raw = item.get(col)
            if raw is None:
                raw = item.get(col.upper())
            if raw is None or raw == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            result[s["name"]].append({"date": tarih, "value": value, "series": s["code"]})

    return result


def _iter_windows(start: str, end: str, freq: int):
    """Tarih aralığını frekans-güvenli pencerelere böler. (start_str, end_str) üretir.
    Giriş/çıkış formatı: DD-MM-YYYY."""
    start_d = datetime.strptime(start, "%d-%m-%Y").date()
    end_d   = datetime.strptime(end,   "%d-%m-%Y").date()
    if start_d > end_d:
        return
    step_days = WINDOW_DAYS.get(freq, 600)
    cur = start_d
    while cur <= end_d:
        win_end = min(cur + timedelta(days=step_days - 1), end_d)
        yield cur.strftime("%d-%m-%Y"), win_end.strftime("%d-%m-%Y")
        cur = win_end + timedelta(days=1)


def fetch_batch(series_list: list[dict], start: str, end: str, freq: int) -> dict[str, list[dict]]:
    """
    Birden fazla seriyi çeker. API başına ~1000 gözlem limiti olduğundan
    aralığı frekansa göre pencerelere böler ve sonuçları birleştirir.

    Önemli: `formulas` ve `aggregationTypes` her seri için ayrı ayrı, `-` ile
    ayrılmış şekilde gönderilir. Aksi halde API 400 döner.
    `aggregationTypes` sayısal değil, string olmalı (avg/last/...).
    """
    result: dict[str, list[dict]] = {s["name"]: [] for s in series_list}
    for w_start, w_end in _iter_windows(start, end, freq):
        chunk = _fetch_batch_single(series_list, w_start, w_end, freq)
        for name, recs in chunk.items():
            result[name].extend(recs)

    # Her seri için deterministik, benzersiz ve sıralı sonuç
    for name, recs in result.items():
        seen: set[str] = set()
        uniq: list[dict] = []
        for r in sorted(recs, key=lambda x: _parse_evds_date(x["date"]) or date.min):
            if r["date"] in seen:
                continue
            seen.add(r["date"])
            uniq.append(r)
        result[name] = uniq

    return result


def discover_categories() -> None:
    data = _get("datagroups?mode=0")
    for cat in data.get("datagroup", []):
        print(f"{cat.get('DATAGROUP_CODE')}  —  {cat.get('DATAGROUP_NAME')}")


def list_series_in_group(group_code: str) -> None:
    data = _get(f"serieList?code={group_code}")
    for s in data.get("serieList", []):
        print(f"{s.get('SERIE_CODE'):40s} {s.get('SERIE_NAME')}")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_stale(state: dict, name: str) -> bool:
    last = state.get(name)
    if not last:
        return True
    last_dt = datetime.strptime(last, "%Y-%m-%d").date()
    return (date.today() - last_dt).days >= STALE_DAYS


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def series_path(name: str) -> Path:
    return DATA_DIR / f"{name}.jsonl"


def read_existing_dates(name: str) -> set[str]:
    path = series_path(name)
    if not path.exists():
        return set()
    dates: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                dates.add(json.loads(line)["date"])
            except (json.JSONDecodeError, KeyError):
                pass
    return dates


def append_records(name: str, records: list[dict]) -> int:
    if not records:
        return 0
    existing = read_existing_dates(name)
    new_records = [r for r in records if r["date"] not in existing]
    if not new_records:
        return 0
    path = series_path(name)
    with path.open("a", encoding="utf-8") as f:
        for r in sorted(new_records, key=lambda x: x["date"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(new_records)


def overwrite_records(name: str, records: list[dict]) -> int:
    path = series_path(name)
    with path.open("w", encoding="utf-8") as f:
        for r in sorted(records, key=lambda x: x["date"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

def today_str() -> str:
    return date.today().strftime("%d-%m-%Y")


def _parse_evds_date(s: str) -> date | None:
    """EVDS tarih formatları: 'DD-MM-YYYY' (günlük) veya 'YYYY-M' (aylık)."""
    for fmt in ("%d-%m-%Y", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _batch_start(batch: dict, state: dict, force: bool, full: bool) -> str:
    """Batch için en erken start tarihini hesapla (tüm serilerden en erkeni)."""
    if force:
        return HISTORICAL_START if full else batch["series"][0]["start"]
    if full:
        return HISTORICAL_START

    starts = []
    for s in batch["series"]:
        last = state.get(s["name"])
        if last:
            last_dt = datetime.strptime(last, "%Y-%m-%d").date()
            starts.append((last_dt + timedelta(days=1)).strftime("%d-%m-%Y"))
        else:
            starts.append(s["start"])

    return min(starts, key=lambda d: datetime.strptime(d, "%d-%m-%Y"))


def run(force: bool = False, full: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    end = today_str()
    t0 = time.time()

    for batch in BATCHES:
        stale_series = [s for s in batch["series"] if force or is_stale(state, s["name"])]
        if not stale_series:
            for s in batch["series"]:
                print(f"  ✓  {s['name']} güncel, atlanıyor")
            continue

        start = _batch_start(batch, state, force, full)
        codes_str = ", ".join(s["name"] for s in stale_series)
        print(f"\n  ↓  Batch '{batch['name']}' ({len(stale_series)} seri)  {start} → {end}")
        print(f"     Seriler: {codes_str}")

        try:
            t_batch = time.time()
            all_records = fetch_batch(stale_series, start, end, batch["freq"])
            print(f"     [HTTP {time.time() - t_batch:.1f}s]")

            for s in stale_series:
                name = s["name"]
                records = all_records.get(name, [])
                if force:
                    n = overwrite_records(name, records)
                else:
                    n = append_records(name, records)
                print(f"     {name}: {n} yeni kayıt (toplam {len(records)} gözlem)")
                if records:
                    # En son tarihi state'e yaz (format: DD-MM-YYYY veya YYYY-M)
                    last_str = max(records, key=lambda r: _parse_evds_date(r["date"]) or date.min)["date"]
                    parsed = _parse_evds_date(last_str)
                    state[name] = parsed.isoformat() if parsed else date.today().isoformat()

            save_state(state)

        except Exception as exc:
            print(f"  HATA ({batch['name']}): {exc}")

    print(f"\nTamamlandı. Toplam süre: {time.time() - t0:.1f}s")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCMB EVDS veri çekici")
    parser.add_argument("--force",    action="store_true", help="Tüm serileri baştan çek")
    parser.add_argument("--full",     action="store_true", help="2003'ten tam geçmişi çek")
    parser.add_argument("--discover", action="store_true", help="EVDS kategori ağacını listele")
    parser.add_argument("--group",    type=str,            help="Grup içindeki serileri listele")
    args = parser.parse_args()

    if args.discover:
        discover_categories()
    elif args.group:
        list_series_in_group(args.group)
    else:
        run(force=args.force, full=args.full)
