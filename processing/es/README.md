# ES Layer — Elasticsearch İndeksleme + Kibana Dashboard

Gold analiz tablolarını Elasticsearch'e indeksler ve Kibana dashboard'larını
Saved Objects API ile programatik kurar. Elasticsearch + Kibana 8.13.4, EC2'da
Docker Compose ile (bkz. `infrastructure/es/`).

## Index kataloğu

9 ES index, `gidaradar_` önekiyle. Mapping'ler `index_mappings.json`'da tanımlı.

| Index | Kaynak Gold tablosu | İçerik |
|---|---|---|
| `gidaradar_daily_margin` | daily_margin | Günlük hal↔market marjı, 7-gün rolling, `city_geo` |
| `gidaradar_price_inequality_hal` | price_inequality_hal | Hal fiyatlarında bölgesel eşitsizlik (CV, spread) |
| `gidaradar_price_inequality_market` | price_inequality_market | Market fiyatlarında bölgesel eşitsizlik |
| `gidaradar_rockets_feathers` | rockets_feathers | Asimetri skoru, β⁺/β⁻, yarı ömür |
| `gidaradar_shocks` | shock_propagation | Hava şokları, gecikme günleri, `city_geo` |
| `gidaradar_pandemic_gap` | pandemic_gap | 2019↔sonrası marj farkı |
| `gidaradar_news_corr` | news_price_corr | Haber-fiyat lag korelasyonu |
| `gidaradar_forecast` | price_forecast | Prophet 30-gün tahmini |
| `gidaradar_macro_corr` | macro_price_corr | Makro etken (yakıt/kur/emtia/elektrik) korelasyonu |

## index_to_es.py — Gold → Elasticsearch

Gold parquet'i Spark ile okur, `toLocalIterator()` ile satır satır stream ederek
`elasticsearch.helpers.bulk` ile indeksler — `toPandas()` kullanılmaz (9M satırlık
`daily_margin` driver RAM'ini patlatır).

- `city_geo` alanı, `lookups/city_coords.csv` Spark tarafında broadcast join ile eklenir.
- `INDEX_SOURCES` dict'i index → Gold path eşlemesini tutar.
- **Aylık rollup:** `daily_margin` (`INDEX_SOURCES`'ta `"rollup": "monthly"`) ham günlük
  satır yerine `(year, month, city, product, market)` aylık özetine indirilir — 10 yıllık
  ham veri (onlarca milyon satır) tek-node ES'i (8 GB RAM) zorlar; rollup ~30x küçültür.
  Alan isimleri korunur (mapping uyumlu), ek `n_days` alanı eklenir. `--no-rollup` ile
  ham satır indexlenebilir.

```bash
python processing/es/index_to_es.py --recreate          # tüm index'ler, drop+create
python processing/es/index_to_es.py --index gidaradar_macro_corr
python processing/es/index_to_es.py --no-rollup         # daily_margin'i ham günlük indexle
```

## create_data_views.sh — Kibana data view'leri

Her index için Kibana data view oluşturur (Kibana REST API). Zaman alanı olan
index'lere `timeFieldName` atanır; `rockets_feathers` ve `macro_corr` zaman-bağımsızdır.

```bash
bash processing/es/create_data_views.sh
```

## build_dashboards.py — Kibana dashboard'ları

5 dashboard'ı Saved Objects API ile programatik kurar — UI'de elle panel
yerleştirme yok. Lens visualization, Maps paneli ve by-value markdown panellerini
üretip `POST /api/saved_objects/{type}/{id}` ile yükler (migration zincirini
atlamak için `_import` yerine create endpoint).

| Dashboard | İçerik |
|---|---|
| Marj Genel Bakış | KPI'lar + zincir bazlı marj trendi + il tablosu + Türkiye haritası |
| Rockets & Feathers | Asimetri skoru bar'ları + β⁺/β⁻ detay tablosu |
| Şok Yayılım | Olay tipi dağılımı + gecikme + il haritası |
| Prophet Tahmin | Tahmin trendi + güven aralığı bandı |
| Makro Etkenler | Kaynak/seri bazlı korelasyon + lag detay tablosu |

Haritalar `ES_GEO_GRID` katmanı + EMS zemin harita kullanır; renk skalası gerçek
veri dağılımına oturtulmuş custom ramp'tır.

```bash
python processing/es/build_dashboards.py
```

## Çalıştırma sırası

```
index_to_es.py --recreate  →  create_data_views.sh  →  build_dashboards.py
```

`build_dashboards.py` data view'lerin önceden var olmasını bekler — bu yüzden
`create_data_views.sh` mutlaka önce çalışır.

## Güvenlik notu

ES portu (9200) `docker-compose.yml`'de `127.0.0.1`'e bağlıdır — internete
açılmaz (açık + auth'suz ES otomatik ransomware botlarının hedefidir). Kibana
(5601) yalnızca EC2 Security Group'ta izinli IP'lerden erişilebilir.

## EC2 RAM notu

ES heap 1.5 GB + Kibana ~0.5 GB. `index_to_es.py` Spark job'u ek ~2.5-3 GB
kullanır — indeksleme sırasında başka Spark job çalıştırma.
