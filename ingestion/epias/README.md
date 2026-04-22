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

Şu an script ile veri alabildiğimiz dataset'ler:

- `price_and_cost` — PTF, SMF, WAP, sistem yönü ve dengesizlik maliyetleri
  Örnek alanlar: `mcp`, `wap`, `smp`, `pos_imb_price`, `neg_imb_price`, `system_direction`, `kupst_cost`
- `consumption` — yük tahmini, gerçek zamanlı tüketim ve UECM
  Örnek alanlar: `load_plan`, `uecm`, `rt_cons`, `consumption`
- `real_time_generation` — kaynak bazlı gerçek zamanlı üretim
- `injection_quantity` — uzlaştırma esas veriş miktarı
  Örnek alanlar: `total`, `naturalGas`, `dam`, `lignite`, `importedCoal`, `wind`, `sun`
- `renewable_injection_quantity` — YEKDEM kapsamındaki lisanslı santrallerin kaynak bazlı verişi
  Örnek alanlar: `toplam`, `ruzgar`, `jeotermal`, `rezervuarli`, `gunes`, `biyokutle`
- `wind_forecast` — RES üretim ve tahmin verisi
  Örnek alanlar: `generation`, `forecast`, `quarter1`, `quarter2`, `quarter3`, `quarter4`
- `renewable_unit_cost` — YEKDEM birim maliyeti
  Örnek alanlar: `supplierUnitCost`, `unitCost`, `ptf`, `version`
- `renewable_total_cost` — YEKDEM toplam gideri
  Örnek alanlar: `toplam`, `ruzgar`, `gunes`, `jeotermal`, `biyokutle`
- `zero_balance_adjustment` — sıfır bakiye düzeltme tutarı
  Örnek alanlar: `zeroBalanceAdjustment`, `downRegulation`, `upRegulation`, `negativeImbalance`, `kupst`
- `transmission_loss_factor` — iletim sistemi kayıp katsayısı
  Örnek alanlar: `firstVersionValue`, `lastVersionValue`, `difference`
- `primary_frequency_capacity` — primer frekans rezerv miktarı ve fiyatı
  Örnek alanlar: `amount`, `price`
- `secondary_frequency_capacity` — sekonder frekans rezerv miktarı ve fiyatı
  Örnek alanlar: `amount`, `price`

Not:

- Bazı servisler saatliktir ve günlük partition üretir.
- Bazıları aylık / versiyonlu yayınlanır; bu yüzden kısa ve çok yeni aralıklarda boş dönebilir.
- Özellikle `injection_quantity` gibi uzlaştırma bazlı servislerde en güncel günler henüz yayımlanmamış olabilir.

Tüm dataset'lerde ortak alanlar:

- `timestamp`
- `_dataset`
- `_source`
- `_ingested_at`
- `contract`

## Çıktı Formatı

```text
ingestion/epias/data/
├── consumption/
│   └── YYYY-MM-DD.jsonl
├── injection_quantity/
│   └── YYYY-MM-DD.jsonl
├── primary_frequency_capacity/
│   └── YYYY-MM-DD.jsonl
├── price_and_cost/
│   └── YYYY-MM-DD.jsonl
├── real_time_generation/
│   └── YYYY-MM-DD.jsonl
├── renewable_injection_quantity/
│   └── YYYY-MM-DD.jsonl
├── renewable_total_cost/
│   └── YYYY-MM-DD.jsonl
├── renewable_unit_cost/
│   └── YYYY-MM-DD.jsonl
├── secondary_frequency_capacity/
│   └── YYYY-MM-DD.jsonl
├── transmission_loss_factor/
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
