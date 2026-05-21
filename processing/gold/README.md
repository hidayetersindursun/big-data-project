# Gold Layer — Analiz Tabloları

İş sorularına cevap veren analiz scriptleri. Hepsi Silver tablolarını okur,
`s3://s3-bbuckett/gold/...` altına yazar. Spark ile feature engineering yapılır;
istatistiksel modeller (statsmodels, Prophet, scipy) `toPandas()` ile driver'da
çalışır — gruplar küçük olduğu için ölçeklenebilir.

## Analiz kataloğu

| Script | Girdi (Silver) | Yöntem | Çıktı (Gold) | Araştırma sorusu |
|---|---|---|---|---|
| `daily_margin.py` | market_hal_joined | 7-gün rolling ortalama (Spark Window) | `daily_margin` | Günlük hal↔market marjı ve trendi nedir? |
| `price_inequality.py` | hal_prices, market_prices | CV (varyasyon katsayısı), spread %, percentile | `price_inequality_hal`, `price_inequality_market` | Gıda fiyatlarında bölgesel eşitsizlik ne kadar? |
| `rockets_feathers.py` | market_hal_joined | Asimetrik hata düzeltme modeli (Engle-Granger ECM, statsmodels OLS) | `rockets_feathers` | Market, hal artışına hızlı düşüşe yavaş mı tepki veriyor? |
| `shock_propagation.py` | weather_daily, market_hal_joined | Şok tespiti (frost/heat/rain) + gecikme hesabı | `shock_propagation` | Hava şokları fiyata kaç günde yansıyor? |
| `pandemic_gap.py` | market_hal_joined | Yıllık ortalama karşılaştırma (2019 baseline) | `pandemic_gap` | Pandemi marjları kalıcı genişletti mi? |
| `news_price_corr.py` | gdelt_daily, market_hal_joined | Pearson lag korelasyon (0..14 gün) | `news_price_corr` | Haber tonu/yoğunluğu fiyat değişiminin öncüsü mü? |
| `prophet_forecast.py` | hal_prices | Meta Prophet (mevsimsellik + changepoint) | `price_forecast` | Önümüzdeki 30 günde fiyat ne olur? |
| `macro_price_corr.py` | market_hal_joined + akaryakit + tcmb + commodities + epias | Pearson lag korelasyon (level + change) | `macro_price_corr` | Makro etkenler (yakıt, kur, emtia, elektrik) gıda fiyatını nasıl etkiliyor? |

## Öne çıkan yöntemler

### Rockets & Feathers — asimetrik ECM
Asimetrik fiyat geçişi: market fiyatı, hal artışına (`β⁺`) ve düşüşüne (`β⁻`)
farklı hızda tepki verir.

```
Δmkt_t = α + Σ [β⁺ᵢ·max(Δhal_{t-i},0) + β⁻ᵢ·min(Δhal_{t-i},0)] + δ·EC_{t-1} + ε
asymmetry_score = (Σβ⁺) / |Σβ⁻|        > 1 → roket (tüketici aleyhine)
```

`half_life_days` = error-correction katsayısından dengeye dönüş süresi.

### macro_price_corr — makro etken korelasyonu
4 dış kaynağı tek analizde birleştirir. Her makro seri (yakıt, USD/TRY, TÜFE-gıda,
buğday, brent, elektrik PTF) × top-N gıda ürünü için `lag 0..N` Pearson korelasyon.

- **target_type**: `price` (gıda fiyatı) veya `margin` (hal↔market marjı)
- **corr_basis**: `change` (fark serisi — **birincil**, trendli serilerde spurious
  korelasyondan kaçınır) veya `level` (ham seviye)
- **best_lag**: her seri-ürün çifti için |korelasyon| en yüksek gecikme

epias kolu `try/except` ile sarılır — `silver/epias` yoksa diğer 3 kaynak yine
çalışır (graceful degradation).

### Prophet forecast
Meta Prophet additive model: `y = trend + seasonality + noise`. `is_changepoint`
trend kırılmalarını (örn. pandemi), `is_forecast` tahmin dönemini işaretler.
Tahmin, eğitim verisinin son tarihinden +30 gündür.

## Çalıştırma

`orchestration/run_gold_ec2.sh` tüm zinciri sıralı çalıştırır:

```bash
nohup bash orchestration/run_gold_ec2.sh > /tmp/run_gold.log 2>&1 &
```

Ön koşul: `silver/market_hal_joined` (silver_joined.py) yazılmış olmalı.
macro_price_corr için ek: `silver/akaryakit`, `silver/tcmb`, `silver/commodities`,
`silver/epias/price_and_cost`.

## Demo subset

Gold analizleri demo döneminde **1 yıl** (2025-05-20 → 2026-05-20) ile çalışır.
`pandemic_gap` demo subset'te 2019 baseline bulunmadığı için atlanır — tam
backfill gerektirir. Tüm scriptler `--start-date` / `--end-date` destekler.
