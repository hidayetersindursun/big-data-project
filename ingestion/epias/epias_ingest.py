"""
EPİAŞ ingestion module.

Saatlik EPİAŞ verilerini `eptr2` üzerinden çeker ve tarih bazlı JSONL
partition'larına yazar.

Çıktı:
    ingestion/epias/data/{dataset}/YYYY-MM-DD.jsonl

State:
    ingestion/epias/state.json

Kimlik doğrulama:
    Kök dizindeki `.env` dosyasında `EPTR_USERNAME` ve `EPTR_PASSWORD`
    tanımlı olmalıdır.
"""

from __future__ import annotations

import argparse
import calendar
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd
from eptr2 import EPTR2
from eptr2.composite import (
    get_hourly_consumption_and_forecast_data,
    get_hourly_price_and_cost_data,
)

try:
    from config import (
        DATASETS,
        DATA_DIR,
        DEFAULT_OVERLAP_HOURS,
        DEFAULT_TIMEOUT_SECONDS,
        STALE_MINUTES,
        STATE_FILE,
    )
except ImportError:  # pragma: no cover - python -m support
    from .config import (
        DATASETS,
        DATA_DIR,
        DEFAULT_OVERLAP_HOURS,
        DEFAULT_TIMEOUT_SECONDS,
        STALE_MINUTES,
        STATE_FILE,
    )


logger = logging.getLogger("epias_ingest")
LOCAL_TZ = ZoneInfo("Europe/Istanbul")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_stale(state: dict, dataset: str) -> bool:
    entry = state.get(dataset, {})
    last_scraped_at = parse_dt(entry.get("last_scraped_at"))
    if last_scraped_at is None:
        return True
    age_minutes = (utcnow() - last_scraped_at).total_seconds() / 60
    return age_minutes >= STALE_MINUTES


def get_start_date(
    dataset: str,
    config: dict,
    state: dict,
    force: bool,
    explicit_start: str | None,
) -> str:
    if explicit_start:
        return explicit_start
    if force:
        return config["default_start"]

    last_observation_at = parse_dt(state.get(dataset, {}).get("last_observation_at"))
    if last_observation_at is None:
        return config["default_start"]

    overlap_hours = config.get("overlap_hours", DEFAULT_OVERLAP_HOURS)
    overlap_start = (last_observation_at - timedelta(hours=overlap_hours)).date()
    floor_start = date.fromisoformat(config["default_start"])
    return max(overlap_start, floor_start).isoformat()


def build_client(dotenv_path: str) -> EPTR2:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return EPTR2(
        use_dotenv=True,
        recycle_tgt=True,
        dotenv_path=dotenv_path,
        tgt_path=str(DATA_DIR),
    )


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def iter_windows(start_date: str, end_date: str, max_range_months: int):
    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    while current <= end:
        next_boundary = add_months(current, max_range_months)
        window_end = min(next_boundary - timedelta(days=1), end)
        yield current.isoformat(), window_end.isoformat()
        current = window_end + timedelta(days=1)


def fetch_price_and_cost(eptr: EPTR2, start_date: str, end_date: str, timeout: int) -> pd.DataFrame:
    return get_hourly_price_and_cost_data(
        start_date=start_date,
        end_date=end_date,
        eptr=eptr,
        include_wap=True,
        add_kupst_cost=True,
        include_contract_symbol=True,
        timeout=timeout,
        max_lives=3,
        retry_backoff=1.0,
        retry_backoff_max=4.0,
    )


def fetch_consumption(eptr: EPTR2, start_date: str, end_date: str, timeout: int) -> pd.DataFrame:
    _ = timeout
    return get_hourly_consumption_and_forecast_data(
        start_date=start_date,
        end_date=end_date,
        eptr=eptr,
        include_contract_symbol=True,
    )


def fetch_real_time_generation(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "rt-gen", start_date, end_date, timeout)


def fetch_eptr_call(
    eptr: EPTR2,
    call_key: str,
    start_date: str,
    end_date: str,
    timeout: int,
    **extra_kwargs,
) -> pd.DataFrame:
    return eptr.call(
        call_key,
        start_date=start_date,
        end_date=end_date,
        request_kwargs={"timeout": timeout},
        retry_attempts=3,
        retry_backoff=1.0,
        retry_backoff_max=4.0,
        retry_jitter=0.1,
        **extra_kwargs,
    )


def merge_frames_on_time(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    if left.empty and right.empty:
        return pd.DataFrame()
    if left.empty:
        return right.copy()
    if right.empty:
        return left.copy()

    join_cols = [column for column in ("date", "time", "hour") if column in left.columns and column in right.columns]
    if not join_cols:
        raise ValueError("Veri setleri zaman kolonlari uzerinden merge edilemedi.")
    return left.merge(right, on=join_cols, how="outer")


def fetch_injection_quantity(eptr: EPTR2, start_date: str, end_date: str, timeout: int) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "uevm", start_date, end_date, timeout)


def fetch_renewable_injection_quantity(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "ren-uevm", start_date, end_date, timeout)


def fetch_wind_forecast(eptr: EPTR2, start_date: str, end_date: str, timeout: int) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "wind-forecast", start_date, end_date, timeout)


def fetch_renewable_unit_cost(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "ren-unit-cost", start_date, end_date, timeout)


def fetch_renewable_total_cost(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "ren-total-cost", start_date, end_date, timeout)


def fetch_zero_balance_adjustment(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "zero-balance", start_date, end_date, timeout)


def fetch_transmission_loss_factor(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    return fetch_eptr_call(eptr, "iskk", start_date, end_date, timeout)


def fetch_primary_frequency_capacity(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    qty_df = fetch_eptr_call(eptr, "anc-pf-qty", start_date, end_date, timeout)
    price_df = fetch_eptr_call(eptr, "anc-pfk", start_date, end_date, timeout)
    return merge_frames_on_time(qty_df, price_df)


def fetch_secondary_frequency_capacity(
    eptr: EPTR2,
    start_date: str,
    end_date: str,
    timeout: int,
) -> pd.DataFrame:
    qty_df = fetch_eptr_call(eptr, "anc-sf-qty", start_date, end_date, timeout)
    price_df = fetch_eptr_call(eptr, "anc-sfk", start_date, end_date, timeout)
    return merge_frames_on_time(qty_df, price_df)


FETCHERS: dict[str, Callable[[EPTR2, str, str, int], pd.DataFrame]] = {
    "price_and_cost": fetch_price_and_cost,
    "consumption": fetch_consumption,
    "real_time_generation": fetch_real_time_generation,
    "injection_quantity": fetch_injection_quantity,
    "renewable_injection_quantity": fetch_renewable_injection_quantity,
    "wind_forecast": fetch_wind_forecast,
    "renewable_unit_cost": fetch_renewable_unit_cost,
    "renewable_total_cost": fetch_renewable_total_cost,
    "zero_balance_adjustment": fetch_zero_balance_adjustment,
    "transmission_loss_factor": fetch_transmission_loss_factor,
    "primary_frequency_capacity": fetch_primary_frequency_capacity,
    "secondary_frequency_capacity": fetch_secondary_frequency_capacity,
}


def get_timestamp_column(df: pd.DataFrame) -> str:
    for candidate in ("timestamp", "dt", "date", "period"):
        if candidate in df.columns:
            return candidate
    raise ValueError(
        "Timestamp kolonu bulunamadi. Beklenen kolonlardan biri yok: "
        "timestamp, dt, date, period"
    )


def normalize_frame(df: pd.DataFrame, dataset: str) -> list[dict]:
    if df.empty:
        return []

    working = df.copy()
    ts_col = get_timestamp_column(working)
    parsed_ts = pd.to_datetime(working[ts_col], errors="coerce", utc=True)
    working = working.loc[parsed_ts.notna()].copy()
    parsed_ts = parsed_ts.loc[parsed_ts.notna()].dt.tz_convert(LOCAL_TZ)
    if working.empty:
        return []

    working["timestamp"] = parsed_ts.map(lambda value: value.isoformat())
    working["_dataset"] = dataset
    working["_source"] = "epias"
    working["_ingested_at"] = utcnow().isoformat()

    if ts_col != "timestamp":
        working = working.drop(columns=[ts_col])

    if "hour" in working.columns and "timestamp" in working.columns:
        working = working.drop(columns=["hour"])

    preferred_order = ["timestamp", "_dataset", "_source", "_ingested_at"]
    ordered_columns = preferred_order + [
        column for column in working.columns if column not in preferred_order
    ]
    working = working[ordered_columns]
    working = working.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    working = working.where(pd.notna(working), None)
    return working.to_dict(orient="records")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Bozuk JSON satiri atlandi: %s", path)
    return rows


def write_partition(dataset: str, partition_date: str, rows: list[dict]) -> int:
    target_dir = DATA_DIR / dataset
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{partition_date}.jsonl"

    merged: dict[str, dict] = {}
    for row in read_jsonl(target_file):
        timestamp = row.get("timestamp")
        if timestamp:
            merged[timestamp] = row

    for row in rows:
        timestamp = row["timestamp"]
        merged[timestamp] = row

    ordered_rows = [merged[key] for key in sorted(merged)]
    with target_file.open("w", encoding="utf-8") as handle:
        for row in ordered_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return len(rows)


def persist_records(dataset: str, rows: list[dict]) -> int:
    partitions: dict[str, list[dict]] = {}
    for row in rows:
        partition_date = row["timestamp"][:10]
        partitions.setdefault(partition_date, []).append(row)

    written = 0
    for partition_date, partition_rows in sorted(partitions.items()):
        written += write_partition(dataset, partition_date, partition_rows)
    return written


def update_state(state: dict, dataset: str, rows: list[dict], start_date: str, end_date: str) -> None:
    last_observation_at = max((row["timestamp"] for row in rows), default=None)
    state[dataset] = {
        "last_scraped_at": utcnow().isoformat(),
        "last_observation_at": last_observation_at,
        "record_count": len(rows),
        "last_requested_start_date": start_date,
        "last_requested_end_date": end_date,
    }


def fetch_dataset_rows(
    eptr: EPTR2,
    dataset: str,
    start_date: str,
    end_date: str,
    timeout: int,
) -> list[dict]:
    dataset_config = DATASETS[dataset]
    max_range_months = dataset_config.get("max_range_months", 12)
    all_rows: list[dict] = []

    windows = list(iter_windows(start_date, end_date, max_range_months))
    for index, (window_start, window_end) in enumerate(windows, start=1):
        logger.info(
            "    chunk %s/%s  %s -> %s",
            index,
            len(windows),
            window_start,
            window_end,
        )
        frame = FETCHERS[dataset](eptr, window_start, window_end, timeout)
        all_rows.extend(normalize_frame(frame, dataset))

    deduped: dict[str, dict] = {}
    for row in all_rows:
        deduped[row["timestamp"]] = row
    return [deduped[key] for key in sorted(deduped)]


def run(args: argparse.Namespace) -> None:
    end_date = args.end_date or date.today().isoformat()
    selected_datasets = args.dataset or list(DATASETS.keys())
    state = load_state()

    datasets_to_fetch: list[tuple[str, str]] = []
    for dataset in selected_datasets:
        if dataset not in DATASETS:
            raise ValueError(f"Bilinmeyen dataset: {dataset}")

        if args.force or args.start_date or is_stale(state, dataset):
            start_date = get_start_date(
                dataset=dataset,
                config=DATASETS[dataset],
                state=state,
                force=args.force,
                explicit_start=args.start_date,
            )
            datasets_to_fetch.append((dataset, start_date))
        else:
            logger.info("  ✓ %s guncel, atlaniyor", dataset)

    if not datasets_to_fetch:
        logger.info("Tum dataset'ler guncel.")
        return

    try:
        eptr = build_client(dotenv_path=args.dotenv_path)
    except Exception as exc:
        raise RuntimeError(
            "EPİAŞ oturumu acilamadi. Kök dizinde `.env` dosyasi olusturup "
            "`EPTR_USERNAME` ve `EPTR_PASSWORD` alanlarini doldurun."
        ) from exc

    for dataset, start_date in datasets_to_fetch:
        logger.info("\n  ↓ %s  %s -> %s", dataset, start_date, end_date)
        try:
            rows = fetch_dataset_rows(eptr, dataset, start_date, end_date, args.timeout)
            written = persist_records(dataset, rows)
            update_state(state, dataset, rows, start_date, end_date)
            save_state(state)
            logger.info("    %s satir yazildi", written)
        except Exception as exc:
            logger.error("  HATA (%s): %s", dataset, exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPİAŞ saatlik veri ingestion scripti")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=sorted(DATASETS.keys()),
        help="Tek bir dataset sec. Birden fazla kez verilebilir.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Secilen dataset'i default tarihinden itibaren bastan cek.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Baslangic tarihi (YYYY-MM-DD). Verilirse state override edilir.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Bitis tarihi (YYYY-MM-DD). Varsayilan bugun.",
    )
    parser.add_argument(
        "--dotenv-path",
        default=".env",
        help="EPTR_USERNAME / EPTR_PASSWORD iceren .env yolu.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout saniyesi.",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="Cekilebilir dataset listesini yazdir ve cik.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser()
    args = parser.parse_args()

    if args.list_datasets:
        for key, meta in DATASETS.items():
            print(f"{key:20s} - {meta['description']}")
        return

    run(args)


if __name__ == "__main__":
    main()
