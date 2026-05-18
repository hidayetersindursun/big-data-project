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
from datetime import date, datetime

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "state.json")


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_stale(state: dict, location_key: str, category: str) -> bool:
    """Return True if this (location, category) was not scraped today."""
    entry = state.get(location_key, {}).get(category)
    if not entry:
        return True
    last_date = datetime.fromisoformat(entry["last_scraped_at"]).date()
    return last_date < date.today()


def update_state(state: dict, location_key: str, category: str, product_count: int) -> None:
    state.setdefault(location_key, {})[category] = {
        "last_scraped_at": datetime.now().replace(microsecond=0).isoformat(),
        "product_count": product_count,
    }
