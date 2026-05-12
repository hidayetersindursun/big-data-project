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
    "mcp_smp_imbalance": {
        "description": "PTF, SMF ve dengesizlik fiyat yonu (raporlama servisi)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "natural_gas_spot": {
        "description": "Spot gaz fiyatlari (SGP)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "natural_gas_balancing": {
        "description": "Dogal gaz dengeleme fiyati",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "intraday_market": {
        "description": "GIP eslestirme miktari ve islem hacmi",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "dam_daily_level": {
        "description": "Baraj gunluk kot (su yuksekligi)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": 0,
        "max_range_months": 999,
    },
    "dam_active_fullness": {
        "description": "Baraj aktif doluluk orani (%)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": 0,
        "max_range_months": 999,
    },
    "planned_outages": {
        "description": "Planli kesinti bilgisi (aylik, period=YYYY-MM)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": 0,
        "max_range_months": 1,
        "inter_chunk_delay": 1.0,
    },
    "unplanned_outages": {
        "description": "Plansiz kesinti bilgisi (aylik, period=YYYY-MM)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": 0,
        "max_range_months": 1,
        "inter_chunk_delay": 1.0,
    },
    "dam_volume": {
        "description": "GOP gunluk islem hacmi (alis/satis teklif miktarlari)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
    "realtime_consumption": {
        "description": "Gercek zamanli saatlik elektrik tuketimi",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "renewable_realtime_generation": {
        "description": "Kaynak bazli yenilenebilir gercek zamanli uretim (ruzgar, gunes, jeotermal...)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 1,
    },
    "kgup": {
        "description": "Kesinlesmis gunluk uretim plani - kaynak bazli saatlik",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 3,
    },
    "dam_active_volume": {
        "description": "Baraj aktif depolama hacmi (baraj bazli)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": 0,
        "max_range_months": 999,
    },
    "natural_gas_daily_transmission": {
        "description": "Dogal gaz gunluk iletim miktari (enjeksiyon ve geri uretim)",
        "default_start": DEFAULT_HISTORY_START,
        "overlap_hours": DEFAULT_OVERLAP_HOURS,
        "max_range_months": 12,
    },
}
