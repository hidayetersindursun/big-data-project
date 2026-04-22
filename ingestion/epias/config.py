from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = BASE_DIR / "state.json"

DEFAULT_HISTORY_START = "2016-01-01"
DEFAULT_TIMEOUT_SECONDS = 20
STALE_MINUTES = 45
DEFAULT_OVERLAP_HOURS = 48

DATASETS = {
    "price_and_cost": {
        "description": "PTF, SMF, dengesizlik ve WAP",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "consumption": {
        "description": "Yuk tahmini, gercek zamanli tuketim ve UECM",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "real_time_generation": {
        "description": "Kaynak bazli gercek zamanli uretim",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "injection_quantity": {
        "description": "Uzlastirma esas veris miktari (UEVM)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "renewable_injection_quantity": {
        "description": "YEKDEM kapsamindaki lisansli santrallerin UEVM verisi",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "wind_forecast": {
        "description": "RES uretim ve tahmin verisi",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 1,
    },
    "renewable_unit_cost": {
        "description": "YEKDEM birim maliyeti",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "renewable_total_cost": {
        "description": "YEKDEM toplam gideri",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "zero_balance_adjustment": {
        "description": "Sifir bakiye duzeltme tutari",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "transmission_loss_factor": {
        "description": "Iletim sistemi kayip katsayisi (ISKK)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "primary_frequency_capacity": {
        "description": "Primer frekans rezerv miktari ve fiyat",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "secondary_frequency_capacity": {
        "description": "Sekonder frekans rezerv miktari ve fiyat",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
}
