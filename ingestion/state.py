"""
State management: tracks when each (location, category) was last scraped.

State file schema:
{
  "Beşiktaş_İstanbul": {
    "Meyve": {"last_scraped_at": "2026-03-27T14:30:00", "product_count": 154},
    ...
  },
  ...
}
"""
import json
import os
from datetime import datetime, timezone
from config import STALE_HOURS

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_stale(state: dict, location_key: str, category: str) -> bool:
    """Return True if the data is older than STALE_HOURS or has never been fetched."""
    entry = state.get(location_key, {}).get(category)
    if not entry:
        return True
    last = datetime.fromisoformat(entry["last_scraped_at"])
    # Make offset-naive for comparison
    if last.tzinfo is not None:
        last = last.replace(tzinfo=None)
    age_hours = (datetime.now() - last).total_seconds() / 3600
    return age_hours >= STALE_HOURS


def update_state(state: dict, location_key: str, category: str, product_count: int) -> None:
    state.setdefault(location_key, {})[category] = {
        "last_scraped_at": datetime.now().replace(microsecond=0).isoformat(),
        "product_count": product_count,
    }
