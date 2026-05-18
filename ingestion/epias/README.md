# ingestion/epias

EPİAŞ Şeffaflık Platformu verilerini `eptr2` üzerinden çeken saatlik ingestion modülü.

## Kurulum

```bash
pip install eptr2 pandas
```

Proje kökünde bir `.env` dosyası oluştur:

```bash
EPTR_USERNAME=epias-kullanici-eposta
EPTR_PASSWORD=epias-sifre
```

## Çalıştırma

```bash
# State'e göre sadece bayat dataset'leri güncelle
python ingestion/epias/epias_ingest.py

# Tek dataset
python ingestion/epias/epias_ingest.py --dataset price_and_cost

# Belirli tarih aralığı
python ingestion/epias/epias_ingest.py --start-date 2026-01-01 --end-date 2026-01-31

# Baştan çek
python ingestion/epias/epias_ingest.py --force

# Desteklenen dataset'leri listele
python ingestion/epias/epias_ingest.py --list-datasets
```

## Çekebildiğimiz Veriler

26 dataset desteklenmektedir. Tüm dataset'lerde ortak alanlar: `timestamp`, `_dataset`, `_source`, `_ingested_at`.

### Fiyat & Maliyet

- `price_and_cost` — PTF, SMF, WAP, sistem yönü ve dengesizlik maliyetleri
  Alanlar: `mcp`, `wap`, `smp`, `pos_imb_price`, `neg_imb_price`, `system_direction`, `kupst_cost`
- `mcp_smp_imbalance` — PTF, SMF ve dengesizlik fiyat yönü (raporlama servisi)
- `zero_balance_adjustment` — sıfır bakiye düzeltme tutarı
  Alanlar: `zeroBalanceAdjustment`, `downRegulation`, `upRegulation`, `negativeImbalance`, `kupst`

### Üretim & Tüketim

- `real_time_generation` — kaynak bazlı gerçek zamanlı üretim (saatlik)
- `realtime_consumption` — gerçek zamanlı saatlik elektrik tüketimi
  Alanlar: `consumption`
- `kgup` — kesinleşmiş günlük üretim planı, kaynak bazlı (saatlik)
  Alanlar: `toplam`, `dogalgaz`, `ruzgar`, `linyit`, `tasKomur`, `ithalKomur`, `fuelOil`, `jeotermal`, `barajli`, `nafta`, `biokutle`, `akarsu`, `gunes`, `diger`
- `consumption` — yük tahmini, gerçek zamanlı tüketim ve UECM
  Alanlar: `load_plan`, `uecm`, `rt_cons`, `consumption`
- `injection_quantity` — uzlaştırma esas veriş miktarı (UEVM)
  Alanlar: `total`, `naturalGas`, `dam`, `lignite`, `importedCoal`, `wind`, `sun`

### Yenilenebilir Enerji & YEKDEM

- `renewable_realtime_generation` — kaynak bazlı yenilenebilir gerçek zamanlı üretim (saatlik)
  Alanlar: `toplam`, `ruzgar`, `jeotermal`, `rezervuarli`, `kanalTipi`, `nehirTipi`, `copGazi`, `biyogaz`, `gunes`, `biyokutle`, `diger`
- `renewable_injection_quantity` — YEKDEM kapsamındaki lisanslı santrallerin verişi
  Alanlar: `toplam`, `ruzgar`, `jeotermal`, `rezervuarli`, `gunes`, `biyokutle`
- `wind_forecast` — RES üretim ve tahmin verisi
  Alanlar: `generation`, `forecast`, `quarter1`, `quarter2`, `quarter3`, `quarter4`
- `renewable_unit_cost` — YEKDEM birim maliyeti
  Alanlar: `supplierUnitCost`, `unitCost`, `ptf`, `version`
- `renewable_total_cost` — YEKDEM toplam gideri
  Alanlar: `toplam`, `ruzgar`, `gunes`, `jeotermal`, `biyokutle`

### Piyasa Hacmi & Dengeleme

- `dam_volume` — GÖP günlük işlem hacmi (alış/satış teklif miktarları, saatlik)
  Alanlar: `volumeOfAsk`
- `intraday_market` — GİP eşleştirme miktarı ve işlem hacmi
- `primary_frequency_capacity` — primer frekans rezerv miktarı ve fiyatı
  Alanlar: `amount`, `price`
- `secondary_frequency_capacity` — sekonder frekans rezerv miktarı ve fiyatı
  Alanlar: `amount`, `price`
- `transmission_loss_factor` — iletim sistemi kayıp katsayısı (ISKK)
  Alanlar: `firstVersionValue`, `lastVersionValue`, `difference`

### Barajlar

- `dam_daily_level` — baraj günlük kot (su yüksekliği)
- `dam_active_fullness` — baraj aktif doluluk oranı (%)
- `dam_active_volume` — baraj aktif depolama hacmi, baraj bazlı (anlık snapshot)
  Alanlar: `basinName`, `damName`, `activeVolume`

### Doğal Gaz

- `natural_gas_spot` — spot gaz fiyatları (SGP)
- `natural_gas_balancing` — doğal gaz dengeleme fiyatı
- `natural_gas_daily_transmission` — günlük doğal gaz iletim miktarı
  Alanlar: `injection`, `reproduction`

### Kesintiler

- `planned_outages` — planlı kesinti bilgisi (aylık, period=YYYY-MM)
- `unplanned_outages` — plansız kesinti bilgisi (aylık, period=YYYY-MM)

---

**Notlar:**

- Saatlik veri üreten servisler günlük JSONL partition'a yazılır.
- `injection_quantity` gibi uzlaştırma bazlı servislerde en güncel günler henüz yayımlanmamış olabilir.
- `dam_active_volume` tarihe göre sorgulanamaz; her çalıştırmada anlık veriyi getirir.
- `renewable_realtime_generation` API'si max 1 aylık aralık kabul eder (`max_range_months: 1`).

## Çıktı Formatı

```text
ingestion/epias/data/
├── consumption/
│   └── YYYY-MM-DD.jsonl
├── dam_active_fullness/
│   └── YYYY-MM-DD.jsonl
├── dam_active_volume/
│   └── YYYY-MM-DD.jsonl
├── dam_daily_level/
│   └── YYYY-MM-DD.jsonl
├── dam_volume/
│   └── YYYY-MM-DD.jsonl
├── injection_quantity/
│   └── YYYY-MM-DD.jsonl
├── intraday_market/
│   └── YYYY-MM-DD.jsonl
├── kgup/
│   └── YYYY-MM-DD.jsonl
├── mcp_smp_imbalance/
│   └── YYYY-MM-DD.jsonl
├── natural_gas_balancing/
│   └── YYYY-MM-DD.jsonl
├── natural_gas_daily_transmission/
│   └── YYYY-MM-DD.jsonl
├── natural_gas_spot/
│   └── YYYY-MM-DD.jsonl
├── planned_outages/
│   └── YYYY-MM-DD.jsonl
├── price_and_cost/
│   └── YYYY-MM-DD.jsonl
├── primary_frequency_capacity/
│   └── YYYY-MM-DD.jsonl
├── real_time_generation/
│   └── YYYY-MM-DD.jsonl
├── realtime_consumption/
│   └── YYYY-MM-DD.jsonl
├── renewable_injection_quantity/
│   └── YYYY-MM-DD.jsonl
├── renewable_realtime_generation/
│   └── YYYY-MM-DD.jsonl
├── renewable_total_cost/
│   └── YYYY-MM-DD.jsonl
├── renewable_unit_cost/
│   └── YYYY-MM-DD.jsonl
├── secondary_frequency_capacity/
│   └── YYYY-MM-DD.jsonl
├── transmission_loss_factor/
│   └── YYYY-MM-DD.jsonl
├── unplanned_outages/
│   └── YYYY-MM-DD.jsonl
├── wind_forecast/
│   └── YYYY-MM-DD.jsonl
└── zero_balance_adjustment/
    └── YYYY-MM-DD.jsonl
```

Her satır tek bir saatlik gözlemdir:

```json
{
  "timestamp": "2026-04-22T12:00:00+03:00",
  "_dataset": "price_and_cost",
  "_source": "epias",
  "_ingested_at": "2026-04-22T09:14:00+00:00",
  "contract": "PH26042212",
  "mcp": 2345.67,
  "wap": 2338.14,
  "smp": 2450.0
}
```

## State

`ingestion/epias/state.json` dataset bazında son çekim zamanını ve son gözlem zamanını tutar. Script tekrar çalıştığında son gözlemden geriye doğru kısa bir overlap penceresiyle veri çeker ve JSONL dosyalarını timestamp bazında merge eder.
