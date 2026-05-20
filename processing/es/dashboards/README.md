# GıdaRadar — Kibana Dashboard Spec

ES indexlerinden beslenen 4 dashboard. Hocanın "dashboardda neler olacak, butona basıldı ne olacak" sorusuna karşılık.

## Workflow: Dashboard'ı kurma → export → reproduce

1. **Veri hazırlığı**: Gold tabloları ES'e yüklensin (`python processing/es/index_to_es.py --recreate`).
2. **Kibana UI'de dashboard'ları interaktif kur** (aşağıda 4 adet spec var).
3. **Saved Object export**: Stack Management → Saved Objects → "Export type: dashboard" — bağlantılı visualization/lens'ler de dahil olur.
4. **Commit**: export ndjson'ı bu klasöre koy (`dashboards/dashboard1_marj_haritasi.ndjson`, vs.).
5. **Reproduce**: `bootstrap_es.sh` saved-objects API ile reimport yapar.

---

## Dashboard 1 — Marj Haritası (Türkiye)

**ES indexleri**: `gidaradar_daily_margin`, `gidaradar_price_inequality_hal`

**Controls (top bar)**:
- Date range picker (default: son 30 gün)
- `product_canonical` dropdown (default: `domates_sofralik`)
- `market_name` multi-select (6 zincir: a101, bim, carrefour, migros, sok, tarim_kredi)

**Panels**:

| # | Panel | Visualization | Data |
|---|---|---|---|
| 1 | Türkiye Marj Haritası | Region map (`tr-il` boundaries) | `gidaradar_daily_margin`: avg(margin_pct) per city |
| 2 | Top Şehirler Tablosu | Data table | city, hal_avg, market_avg, margin_pct desc |
| 3 | Hal vs Market Time Series | Line chart | hal_price (blue) + 6 chain line (renkli) |
| 4 | Şehir CV Bar | Horizontal bar | `gidaradar_price_inequality_hal`: top-15 product, cv desc |

**Etkileşim (kullanıcı haritada bir şehre tıklarsa)**:
- Kibana cross-filter pushes `city: <clicked>` to all 4 panels
- Tablo o şehre filtrelenir (artık tek satır görünür ama detaylı)
- Time series o şehrin günlük verisini gösterir
- CV bar filter dışı kalır (ürün bazlı, şehir filtresine bağlı değil)

**Etkileşim (product değiştirilirse)**:
- Tüm 4 panel yeni product için tekrar render.

---

## Dashboard 2 — Rockets & Feathers Karşılaştırıcı

**ES indexleri**: `gidaradar_rockets_feathers`, `gidaradar_daily_margin`

**Controls**:
- `product_canonical` dropdown

**Panels**:

| # | Panel | Visualization | Data |
|---|---|---|---|
| 1 | Asimetri Skoru | Bar chart | x=market_name (6), y=asymmetry_score; reference line at 1.0; renk: <1=yeşil, >1=kırmızı |
| 2 | β⁺ vs β⁻ | Grouped bar | beta_up vs beta_down per market |
| 3 | Hal vs Market Time Series | Line chart with annotations | hal (gri), market (renkli); annotation: önemli changepoint günleri |
| 4 | Hızlı Stat | Markdown / metric | "domates_sofralik için BIM rocket, A101 feather" gibi otomatik bulgular |

**Etkileşim (bar tıkla — Panel 1)**:
- `market_name + product_canonical` cross-filter Panel 3'e
- Panel 3 sadece o zinciri gösterir, hal ile karşılaştırması net.

---

## Dashboard 3 — Şok Yayılım Zaman Çizelgesi

**ES indexleri**: `gidaradar_shocks`, `gidaradar_daily_margin`, opsiyonel `gidaradar_news_corr`

**Controls**:
- City dropdown (default: Antalya)
- Product dropdown (default: domates_sofralik)
- Lag window radio: 3 / 7 / 14 / 30 gün

**Panels**:

| # | Panel | Visualization | Data |
|---|---|---|---|
| 1 | Olay Zaman Çizelgesi | Line + annotation | shocks olarak markers (▼), tone bars üstte |
| 2 | Hal + Market Fiyat | Line chart | hal_price (kalın) + market_price (her chain) overlay |
| 3 | Şok Etkisi Tablosu | Data table | event_date, type, hal_lag, mkt_lag, peak_change_pct |
| 4 | Lag Histogram | Histogram | event_type → hal_lag_days dağılımı |

**Etkileşim (olay marker'ına tıkla)**:
- `event_date` filter tüm panellere
- Tablo o olayı (ve aynı tarihteki diğer olayları) gösterir
- Time series event_date ± 30 gün penceresine zoom

**Etkileşim (Lag window radio)**:
- Tablo filtrelenir: `hal_lag_days <= window`

---

## Dashboard 4 — Pandemi Marj Genişlemesi + Prophet Tahmin

**ES indexleri**: `gidaradar_pandemic_gap`, `gidaradar_forecast`

**Controls**:
- `product_canonical` dropdown

**Panels**:

| # | Panel | Visualization | Data |
|---|---|---|---|
| 1 | Baseline vs Post Marj | Metric (büyük rakam) | baseline_margin, post_margin (2021), gap_widening_pct (ok ikonu) |
| 2 | Yıl Yıl Karşılaştırma | Clustered bar | 2019 vs 2021/22/23/24 marj per market_name |
| 3 | Prophet Forecast | Line + shaded band | yhat (solid history + dashed forecast), yhat_lower/upper band, changepoint dikey çizgi |
| 4 | Changepoint Noktaları | Data table | is_changepoint=true tarihler |

**Etkileşim**:
- Product değişimi → 4 panel de yeniden filter.
- Panel 3'te grafik üstünde hover → tarih + yhat + interval gözükür.

---

## Saved Objects export komutu (Kibana Dev Console)

```
POST kbn:/api/saved_objects/_export
{
  "type": ["dashboard", "lens", "visualization", "index-pattern", "search"],
  "includeReferencesDeep": true
}
```

Çıktı ndjson; bu klasöre kaydet.

## Re-import (yeni Kibana'ya)

```
POST kbn:/api/saved_objects/_import?overwrite=true
@dashboards/dashboard1_marj_haritasi.ndjson
```

## Index pattern oluşturma (manuel)

İlk açılışta Kibana index pattern istiyor. 8 index için tek tek veya glob ile:

- `gidaradar_*` → tüm dashboard'ları kapsar
- Time field:
  - `gidaradar_daily_margin` → `date`
  - `gidaradar_shocks` → `event_date`
  - `gidaradar_forecast` → `date`
  - diğerleri time-independent

## Performans notu

t3.large (8 GB) EC2'da ES heap 1.5GB, 8 index toplam ~2-5M doc — Kibana refresh süresi 1-3 sn arası beklenir. Dashboard'da auto-refresh KAPALI olsun (sunum sırasında interactive).
