"""
Kibana 8.13 Saved Objects üreteci — 4 dashboard + Lens visualization'lar.

Akış:
  1. Kibana'dan data view listesini çek (title → id).
  2. Her dashboard için Lens viz saved object'leri üret.
  3. NDJSON dosyasına yaz (her satır bir saved object).
  4. Sonra: curl ile POST /api/saved_objects/_import?overwrite=true

Kullanım:
  python3 processing/es/build_dashboards.py            # /tmp/gr_dashboards.ndjson
  python3 processing/es/build_dashboards.py --out X.ndjson
"""

import argparse
import json
import os
import urllib.error
import urllib.request

KIBANA = os.environ.get("KIBANA_HOST", "http://localhost:5601")

# Demo veri aralığı — dashboard timeFrom/timeTo
TIME_FROM = "2025-05-01T00:00:00.000Z"
TIME_TO = "2026-05-21T23:59:59.000Z"

# Her dashboard'ın üstündeki açıklama metni (Markdown)
MD_MARJ = """### Marj Genel Bakış — Hal (toptan) ile Market (perakende) Fiyat Farkı

Bu dashboard, ürünlerin **toptan hal fiyatı** ile **market raf fiyatı** arasındaki kâr marjını analiz eder.

- **KPI kartları** — ortalama marj %, ortalama hal ve market fiyatı (₺/kg)
- **Marj Trendi** — 6 market zincirinin zaman içindeki marj değişimi
- **İl Tablosu + Harita** — marjın 81 ildeki coğrafi dağılımı (harita: koyu kırmızı = yüksek marj)
- **Ürün Grafiği** — hangi üründe marj en yüksek

*Demo dönemi: Mayıs 2025 – Mayıs 2026.*"""

MD_ROCKETS = """### Rockets & Feathers — Asimetrik Fiyat Geçişi

Market fiyatları, hal fiyatı **artınca hızlı** yükselip **düşünce yavaş** mı iniyor? ("Roket gibi çıkar, tüy gibi iner.")

- **Asimetri Skoru > 1** → roket etkisi (tüketici aleyhine asimetri)
- **β⁺** hal artışına geçiş hızı · **β⁻** hal düşüşüne geçiş hızı
- **Yarı ömür (gün)** — fiyatın dengeye dönüş süresi

Engle-Granger asimetrik hata düzeltme modeli (ECM) ile hesaplanmıştır."""

MD_SOK = """### Şok Yayılım — Olaydan Rafa Geçiş Hızı

Hava olayları ve fiyat şoklarının hal ve market fiyatlarına **kaç günde** yansıdığını ölçer.

- **Olay Tipi Dağılımı** — şok olaylarının türlere göre sayısı
- **Ortalama Gecikme** — şokun hal ve markete ulaşma süresi (gün); düşük = hızlı geçiş
- **Tablo + Harita** — il bazlı zirve fiyat değişimi % ve coğrafi yoğunluk"""

MD_PROPHET = """### Prophet Tahmin — 30 Günlük Fiyat Öngörüsü

Meta **Prophet** zaman serisi modeli ile ürün fiyatlarının gelecek 30 günlük tahmini.

- **Tahmin Trendi** — ürün bazlı öngörülen fiyat (₺/kg)
- **Güven Aralığı** — tahminin belirsizlik bandı (alt/üst sınır)
- **Tablo** — ürün bazlı tahmin özeti

Model, mevsimsellik ve trend bileşenleriyle 10 yıllık geçmiş seriden öğrenir."""


# ----------------------------------------------------------------------
# Kibana'dan data view id'leri
# ----------------------------------------------------------------------
def fetch_data_views():
    """title → id eşlemesi döndür."""
    req = urllib.request.Request(
        f"{KIBANA}/api/data_views",
        headers={"kbn-xsrf": "true"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return {dv["title"]: dv["id"] for dv in data["data_view"]}


# ----------------------------------------------------------------------
# Lens column üreticileri (formBased datasource)
# ----------------------------------------------------------------------
def col_date(field="date", interval="auto"):
    return {
        "label": field,
        "dataType": "date",
        "operationType": "date_histogram",
        "sourceField": field,
        "isBucketed": True,
        "scale": "interval",
        "params": {"interval": interval, "includeEmptyRows": True, "dropPartials": False},
    }


def col_terms(field, size=10, order_col=None, order_dir="desc"):
    if order_col:
        order_by = {"type": "column", "columnId": order_col}
    else:
        order_by = {"type": "alphabetical", "fallback": True}
    return {
        "label": f"{field} (top {size})",
        "dataType": "string",
        "operationType": "terms",
        "sourceField": field,
        "isBucketed": True,
        "scale": "ordinal",
        "params": {
            "size": size,
            "orderBy": order_by,
            "orderDirection": order_dir,
            "otherBucket": False,
            "missingBucket": False,
            "parentFormat": {"id": "terms"},
        },
    }


def col_metric(op, field, label=None, decimals=2):
    """op: average | sum | median | max | min"""
    return {
        "label": label or f"{op}({field})",
        "dataType": "number",
        "operationType": op,
        "sourceField": field,
        "isBucketed": False,
        "scale": "ratio",
        "params": {"emptyAsNull": True, "format": {"id": "number", "params": {"decimals": decimals}}},
    }


def col_count(label="Kayıt sayısı"):
    return {
        "label": label,
        "dataType": "number",
        "operationType": "count",
        "sourceField": "___records___",
        "isBucketed": False,
        "scale": "ratio",
        "params": {"emptyAsNull": True},
    }


def _layer(columns):
    return {"columns": columns, "columnOrder": list(columns.keys()), "incompleteColumns": {}}


def _wrap(viz_id, title, viz_type, visualization, columns, dv_id):
    """Lens saved object dict."""
    return {
        "id": viz_id,
        "type": "lens",
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": viz_type,
            "state": {
                "visualization": visualization,
                "query": {"query": "", "language": "kuery"},
                "filters": [],
                "datasourceStates": {"formBased": {"layers": {"L1": _layer(columns)}}},
                "internalReferences": [],
                "adHocDataViews": {},
            },
        },
        "references": [
            {"type": "index-pattern", "id": dv_id, "name": "indexpattern-datasource-layer-L1"},
        ],
    }


# ----------------------------------------------------------------------
# Lens viz tipleri
# ----------------------------------------------------------------------
def lens_metric(viz_id, title, dv_id, metric_col):
    cols = {"m1": metric_col}
    viz = {"layerId": "L1", "layerType": "data", "metricAccessor": "m1"}
    return _wrap(viz_id, title, "lnsMetric", viz, cols, dv_id)


def lens_xy(viz_id, title, dv_id, x_col, metric_cols, series_type="line",
            split_col=None):
    """metric_cols: dict {id: column}. x_col: column. split_col: column|None."""
    cols = {"x1": x_col}
    accessors = []
    for i, (mid, mcol) in enumerate(metric_cols.items()):
        cols[mid] = mcol
        accessors.append(mid)
    layer = {
        "layerId": "L1",
        "layerType": "data",
        "seriesType": series_type,
        "xAccessor": "x1",
        "accessors": accessors,
    }
    if split_col:
        cols["s1"] = split_col
        layer["splitAccessor"] = "s1"
    # columnOrder: bucket'lar önce
    order = ["x1"] + (["s1"] if split_col else []) + accessors
    cols_ordered = {k: cols[k] for k in order}
    viz = {
        "legend": {"isVisible": True, "position": "right"},
        "valueLabels": "hide",
        "fittingFunction": "None",
        "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
        "gridlinesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "preferredSeriesType": series_type,
        "layers": [layer],
    }
    return _wrap(viz_id, title, "lnsXY", viz, cols_ordered, dv_id)


def lens_table(viz_id, title, dv_id, columns, col_order):
    """columns: dict {id: column}. col_order: id listesi (görünüm sırası)."""
    cols_ordered = {k: columns[k] for k in col_order}
    viz = {
        "layerId": "L1",
        "layerType": "data",
        "columns": [{"columnId": cid, "isTransposed": False} for cid in col_order],
        "paging": {"size": 20, "enabled": True},
    }
    return _wrap(viz_id, title, "lnsDatatable", viz, cols_ordered, dv_id)


# ----------------------------------------------------------------------
# Maps (type: map) — ES_GEO_GRID nokta katmanı
# ----------------------------------------------------------------------
def kibana_map(map_id, title, dv_id, geo_field, metric_field, metric_label, color_stops):
    """Türkiye haritası: her ızgara noktası bir konum, renk = avg(metric_field).
    color_stops: [(değer, '#hex'), ...] — gerçek veri dağılımına oturtulmuş eşikler."""
    color_name = f"avg_of_{metric_field}"
    source = {
        "type": "ES_GEO_GRID",
        "id": f"{map_id}-src",
        "applyGlobalQuery": True,
        "applyGlobalTime": True,
        "applyForceRefresh": True,
        "geoField": geo_field,
        "metrics": [
            {"type": "count"},
            {"type": "avg", "field": metric_field, "label": metric_label},
        ],
        "requestType": "point",
        "resolution": "MOST_FINE",
        "indexPatternRefName": "layer_0_source_index_pattern",
    }
    style_props = {
        "icon": {"type": "STATIC", "options": {"value": "marker"}},
        "fillColor": {
            "type": "DYNAMIC",
            "options": {
                "useCustomColorRamp": True,
                "customColorRamp": [{"stop": s, "color": c} for s, c in color_stops],
                "field": {"name": color_name, "origin": "source"},
                "type": "ORDINAL",
            },
        },
        "lineColor": {"type": "STATIC", "options": {"color": "#3d3d3d"}},
        "lineWidth": {"type": "STATIC", "options": {"size": 1}},
        "iconSize": {"type": "STATIC", "options": {"size": 8}},
        "iconOrientation": {"type": "STATIC", "options": {"orientation": 0}},
        "labelText": {"type": "STATIC", "options": {"value": ""}},
        "labelZoomRange": {"options": {"useLayerZoomRange": True, "minZoom": 0, "maxZoom": 24}},
        "labelColor": {"type": "STATIC", "options": {"color": "#000000"}},
        "labelSize": {"type": "STATIC", "options": {"size": 14}},
        "labelBorderColor": {"type": "STATIC", "options": {"color": "#FFFFFF"}},
        "symbolizeAs": {"options": {"value": "circle"}},
        "labelBorderSize": {"options": {"size": "SMALL"}},
        "labelPosition": {"options": {"position": "CENTER"}},
    }
    layer = {
        "id": f"{map_id}-layer",
        "label": title,
        "sourceDescriptor": source,
        "visible": True,
        "style": {"type": "VECTOR", "properties": style_props, "isTimeAware": True},
        "type": "GEOJSON_VECTOR",
        "joins": [],
        "minZoom": 0, "maxZoom": 24, "alpha": 0.9,
        "includeInFitToBounds": True,
    }
    # Base map (zemin harita) — EMS road map. Olmadan harita beyaz görünür.
    base_layer = {
        "id": f"{map_id}-base",
        "label": None,
        "sourceDescriptor": {"type": "EMS_TMS", "isAutoSelect": True},
        "type": "EMS_VECTOR_TILE",
        "minZoom": 0, "maxZoom": 24,
        "alpha": 1,
        "visible": True,
        "style": {"type": "EMS_VECTOR_TILE", "color": ""},
        "includeInFitToBounds": True,
    }
    map_state = {
        "zoom": 5.4,
        "center": {"lon": 35.4, "lat": 39.1},
        "timeFilters": {"from": TIME_FROM, "to": TIME_TO},
        "refreshConfig": {"isPaused": True, "interval": 0},
        "query": {"query": "", "language": "kuery"},
        "filters": [],
        "settings": {"autoFitToDataBounds": False},
    }
    return {
        "id": map_id,
        "type": "map",
        "attributes": {
            "title": title,
            "description": "",
            "mapStateJSON": json.dumps(map_state),
            "layerListJSON": json.dumps([base_layer, layer]),
            "uiStateJSON": json.dumps({"isLayerTOCOpen": True, "openTOCDetails": []}),
        },
        "references": [
            {"type": "index-pattern", "id": dv_id, "name": "layer_0_source_index_pattern"},
        ],
    }


def _markdown_panel_json(pid, markdown_text, h):
    """Dashboard'a gömülü (by-value) markdown paneli — ayrı saved object değil.
    Kibana 8.x'te 'Text' paneli böyle saklanır; by-reference markdown render olmaz."""
    return {
        "type": "visualization",
        "gridData": {"x": 0, "y": 0, "w": 48, "h": h, "i": pid},
        "panelIndex": pid,
        "embeddableConfig": {
            "savedVis": {
                "id": "",
                "type": "markdown",
                "title": "",
                "description": "",
                "params": {
                    "fontSize": 12,
                    "openLinksInNewTab": True,
                    "markdown": markdown_text,
                },
                "uiState": {},
                "data": {
                    "aggs": [],
                    "searchSource": {"query": {"query": "", "language": "kuery"}, "filter": []},
                },
            },
            "enhancements": {},
        },
    }


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------
def dashboard(dash_id, title, panels, intro_md=None):
    """panels: [(viz_id, x, y, w, h), ...]  → lens varsayılır
              veya [(ptype, viz_id, x, y, w, h), ...] → tip açık (lens|map)
    intro_md verilirse en üste tam-genişlik (by-value) markdown açıklama paneli eklenir."""
    # normalize → hepsi 6-tuple
    norm = []
    for p in panels:
        if len(p) == 5:
            norm.append(("lens",) + tuple(p))
        else:
            norm.append(tuple(p))
    panels_json = []
    references = []
    intro_h = 9
    if intro_md:
        panels_json.append(_markdown_panel_json("intro", intro_md, intro_h))
        norm = [(t, i, x, y + intro_h, w, h) for (t, i, x, y, w, h) in norm]
    for i, (ptype, viz_id, x, y, w, h) in enumerate(norm):
        pid = f"p{i+1}"
        ref_name = f"panel_{pid}"
        panels_json.append({
            "type": ptype,
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": pid},
            "panelIndex": pid,
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": ref_name,
        })
        references.append({"type": ptype, "id": viz_id, "name": ref_name})
    return {
        "id": dash_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": "",
            "panelsJSON": json.dumps(panels_json, ensure_ascii=False),
            "optionsJSON": json.dumps({
                "useMargins": True, "syncColors": False, "syncCursor": True,
                "syncTooltips": False, "hidePanelTitles": False,
            }),
            "timeRestore": True,
            "timeFrom": TIME_FROM,
            "timeTo": TIME_TO,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"}, "filter": [],
                }),
            },
        },
        "references": references,
    }


# ----------------------------------------------------------------------
# 4 dashboard tanımı
# ----------------------------------------------------------------------
def build_all(dv):
    objs = []

    # === Dashboard 1: Marj Genel Bakış ===
    dm = dv["gidaradar_daily_margin"]
    objs += [
        lens_metric("gr-l-dm-kpi-margin", "Ortalama Marj %", dm,
                    col_metric("average", "margin_pct", "Ortalama Marj %", 1)),
        lens_metric("gr-l-dm-kpi-hal", "Ort. Hal Fiyatı ₺/kg", dm,
                    col_metric("average", "hal_price_per_kg", "Ort. Hal ₺/kg", 2)),
        lens_metric("gr-l-dm-kpi-market", "Ort. Market Fiyatı ₺/kg", dm,
                    col_metric("average", "market_price_per_kg", "Ort. Market ₺/kg", 2)),
        lens_xy("gr-l-dm-trend", "Marj Trendi — Zincir Bazlı", dm,
                col_date("date", "1w"),
                {"m1": col_metric("average", "margin_pct", "Ort. Marj %", 1)},
                series_type="line",
                split_col=col_terms("market_name", 6, order_col="m1")),
        lens_table("gr-l-dm-city", "İl Bazlı Ortalama Marj", dm,
                   {"c1": col_terms("city", 20, order_col="c2"),
                    "c2": col_metric("average", "margin_pct", "Ort. Marj %", 1),
                    "c3": col_metric("average", "hal_price_per_kg", "Ort. Hal ₺/kg", 2),
                    "c4": col_metric("average", "market_price_per_kg", "Ort. Market ₺/kg", 2)},
                   ["c1", "c2", "c3", "c4"]),
        lens_xy("gr-l-dm-product", "Ürün Bazlı Ortalama Marj", dm,
                col_terms("product_canonical", 15, order_col="m1"),
                {"m1": col_metric("average", "margin_pct", "Ort. Marj %", 1)},
                series_type="bar_horizontal"),
        kibana_map("gr-map-marj", "Marj Haritası — İl Bazlı (renk = ort. marj %)",
                   dm, "city_geo", "margin_pct", "Ort. Marj %",
                   [(95, "#ffffb2"), (125, "#fecc5c"), (155, "#fd8d3c"),
                    (195, "#f03b20"), (235, "#bd0026")]),
    ]
    objs.append(dashboard("gr-dashboard-marj", "GıdaRadar — Marj Genel Bakış", [
        ("gr-l-dm-kpi-margin", 0, 0, 16, 7),
        ("gr-l-dm-kpi-hal", 16, 0, 16, 7),
        ("gr-l-dm-kpi-market", 32, 0, 16, 7),
        ("gr-l-dm-trend", 0, 7, 48, 15),
        ("gr-l-dm-city", 0, 22, 24, 18),
        ("gr-l-dm-product", 24, 22, 24, 18),
        ("map", "gr-map-marj", 0, 40, 48, 20),
    ], intro_md=MD_MARJ))

    # === Dashboard 2: Rockets & Feathers ===
    rf = dv["gidaradar_rockets_feathers"]
    objs += [
        lens_metric("gr-l-rf-kpi", "Ortalama Asimetri Skoru", rf,
                    col_metric("average", "asymmetry_score", "Ort. Asimetri", 2)),
        lens_xy("gr-l-rf-market", "Zincir Bazlı Asimetri Skoru", rf,
                col_terms("market_name", 6, order_col="m1"),
                {"m1": col_metric("average", "asymmetry_score", "Ort. Asimetri", 2)},
                series_type="bar"),
        lens_xy("gr-l-rf-product", "Ürün Bazlı Asimetri Skoru", rf,
                col_terms("product_canonical", 15, order_col="m1"),
                {"m1": col_metric("average", "asymmetry_score", "Ort. Asimetri", 2)},
                series_type="bar_horizontal"),
        lens_table("gr-l-rf-table", "Asimetri Detay Tablosu", rf,
                   {"c1": col_terms("product_canonical", 30, order_col="c4"),
                    "c2": col_metric("average", "beta_up", "β⁺ (yukarı)", 3),
                    "c3": col_metric("average", "beta_down", "β⁻ (aşağı)", 3),
                    "c4": col_metric("average", "asymmetry_score", "Asimetri", 2),
                    "c5": col_metric("average", "half_life_days", "Yarı ömür (gün)", 1)},
                   ["c1", "c2", "c3", "c4", "c5"]),
    ]
    objs.append(dashboard("gr-dashboard-rockets", "GıdaRadar — Rockets & Feathers", [
        ("gr-l-rf-kpi", 0, 0, 48, 6),
        ("gr-l-rf-market", 0, 6, 24, 15),
        ("gr-l-rf-product", 24, 6, 24, 15),
        ("gr-l-rf-table", 0, 21, 48, 18),
    ], intro_md=MD_ROCKETS))

    # === Dashboard 3: Şok Yayılım ===
    sh = dv["gidaradar_shocks"]
    objs += [
        lens_metric("gr-l-sh-kpi", "Toplam Şok Olayı", sh, col_count("Şok olayı")),
        lens_xy("gr-l-sh-type", "Olay Tipi Dağılımı", sh,
                col_terms("event_type", 10, order_col="m1"),
                {"m1": col_count("Olay sayısı")},
                series_type="bar"),
        lens_xy("gr-l-sh-lag", "Ortalama Gecikme — Hal vs Market (gün)", sh,
                col_terms("event_type", 10, order_col="m1"),
                {"m1": col_metric("average", "hal_lag_days", "Hal gecikme", 1),
                 "m2": col_metric("average", "market_lag_days", "Market gecikme", 1)},
                series_type="bar"),
        lens_table("gr-l-sh-table", "Şok Etkisi Detayı", sh,
                   {"c1": col_terms("city", 30, order_col="c3"),
                    "c2": col_terms("event_type", 10),
                    "c3": col_metric("average", "peak_change_pct", "Zirve değişim %", 1),
                    "c4": col_metric("average", "hal_lag_days", "Hal gecikme (gün)", 1),
                    "c5": col_metric("average", "market_lag_days", "Market gecikme (gün)", 1)},
                   ["c1", "c2", "c3", "c4", "c5"]),
        kibana_map("gr-map-sok", "Şok Haritası — İl Bazlı (renk = ort. zirve değişim %)",
                   sh, "city_geo", "peak_change_pct", "Zirve değişim %",
                   [(14, "#ffffb2"), (16.5, "#fecc5c"), (18, "#fd8d3c"),
                    (22, "#f03b20"), (30, "#bd0026")]),
    ]
    objs.append(dashboard("gr-dashboard-sok", "GıdaRadar — Şok Yayılım", [
        ("gr-l-sh-kpi", 0, 0, 48, 6),
        ("gr-l-sh-type", 0, 6, 24, 15),
        ("gr-l-sh-lag", 24, 6, 24, 15),
        ("gr-l-sh-table", 0, 21, 48, 18),
        ("map", "gr-map-sok", 0, 39, 48, 20),
    ], intro_md=MD_SOK))

    # === Dashboard 4: Prophet Tahmin ===
    fc = dv["gidaradar_forecast"]
    objs += [
        lens_metric("gr-l-fc-kpi", "Tahmin Kaydı Sayısı", fc, col_count("Tahmin satırı")),
        lens_xy("gr-l-fc-trend", "Fiyat Tahmini — Ürün Bazlı", fc,
                col_date("date", "1w"),
                {"m1": col_metric("average", "yhat", "Tahmin ₺/kg", 2)},
                series_type="line",
                split_col=col_terms("product_canonical", 8, order_col="m1")),
        lens_xy("gr-l-fc-band", "Tahmin + Güven Aralığı (tüm ürünler ort.)", fc,
                col_date("date", "1w"),
                {"m1": col_metric("average", "yhat_lower", "Alt sınır", 2),
                 "m2": col_metric("average", "yhat", "Tahmin", 2),
                 "m3": col_metric("average", "yhat_upper", "Üst sınır", 2)},
                series_type="line"),
        lens_table("gr-l-fc-table", "Ürün Bazlı Tahmin Özeti", fc,
                   {"c1": col_terms("product_canonical", 30, order_col="c2"),
                    "c2": col_metric("average", "yhat", "Ort. Tahmin ₺/kg", 2),
                    "c3": col_metric("average", "yhat_lower", "Ort. Alt sınır", 2),
                    "c4": col_metric("average", "yhat_upper", "Ort. Üst sınır", 2)},
                   ["c1", "c2", "c3", "c4"]),
    ]
    objs.append(dashboard("gr-dashboard-prophet", "GıdaRadar — Prophet Tahmin", [
        ("gr-l-fc-kpi", 0, 0, 48, 6),
        ("gr-l-fc-trend", 0, 6, 48, 15),
        ("gr-l-fc-band", 0, 21, 24, 15),
        ("gr-l-fc-table", 24, 21, 24, 15),
    ], intro_md=MD_PROPHET))

    return objs


def push_object(obj):
    """Tek saved object'i create endpoint ile yükle — _import'tan farklı:
    migration zinciri uygulanmaz, obje 'current version' kabul edilir."""
    url = f"{KIBANA}/api/saved_objects/{obj['type']}/{obj['id']}?overwrite=true"
    body = json.dumps({
        "attributes": obj["attributes"],
        "references": obj.get("references", []),
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, f"{e.code}: {e.read().decode('utf-8', 'ignore')[:400]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/gr_dashboards.ndjson")
    parser.add_argument("--no-push", action="store_true", help="Sadece NDJSON yaz, Kibana'ya gönderme")
    args = parser.parse_args()

    dv = fetch_data_views()
    print(f"Data view'ler: {len(dv)} adet")
    for need in ("gidaradar_daily_margin", "gidaradar_rockets_feathers",
                 "gidaradar_shocks", "gidaradar_forecast"):
        if need not in dv:
            raise SystemExit(f"HATA: '{need}' data view'i yok. Önce create_data_views.sh çalıştır.")

    objs = build_all(dv)
    with open(args.out, "w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    n_lens = sum(1 for o in objs if o["type"] == "lens")
    n_dash = sum(1 for o in objs if o["type"] == "dashboard")
    print(f"Yazıldı → {args.out}  ({n_lens} Lens viz + {n_dash} dashboard)")

    if args.no_push:
        return

    # Push: build_all sırası zaten lens'leri kendi dashboard'undan önce üretir.
    ok, fail = 0, 0
    for o in objs:
        success, info = push_object(o)
        if success:
            ok += 1
        else:
            fail += 1
            print(f"  HATA {o['type']}/{o['id']}: {info}")
    print(f"Push: {ok} OK, {fail} hata")


if __name__ == "__main__":
    main()
