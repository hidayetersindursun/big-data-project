"""
TCMB JSONL dosyalarindan interaktif HTML grafik dashboard'u uretir.

Kullanim:
    python tcmb/plot_tcmb.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
PLOT_DIR = Path(__file__).resolve().parent / "plots"
OUT_FILE = PLOT_DIR / "tcmb_dashboard.html"


def read_series(name: str, date_fmt: str):
    path = DATA_DIR / f"{name}.jsonl"
    pairs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            dt = datetime.strptime(row["date"], date_fmt)
            pairs.append((dt, float(row["value"])))
    pairs.sort(key=lambda x: x[0])
    return [p[0].strftime("%Y-%m-%d") for p in pairs], [p[1] for p in pairs]


def _json(x):
    return json.dumps(x, ensure_ascii=False)


def build_html() -> str:
    usd_x, usd_y = read_series("usd_try_alis", "%d-%m-%Y")
    eur_x, eur_y = read_series("eur_try_alis", "%d-%m-%Y")
    gbp_x, gbp_y = read_series("gbp_try_alis", "%d-%m-%Y")
    cpi_x, cpi_y = read_series("tufe_genel_yoy", "%Y-%m")
    core_x, core_y = read_series("tufe_cekirdek_yoy", "%Y-%m")
    food_x, food_y = read_series("tufe_gida_yoy", "%Y-%m")
    ppi_x, ppi_y = read_series("yiufe_genel_yoy", "%Y-%m")

    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TCMB Grafik Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 24px; background:#f7f8fa; color:#111; }}
    h1 {{ margin:0 0 6px; }}
    p {{ margin:0 0 16px; color:#555; }}
    .card {{ background:#fff; border:1px solid #e6e8ef; border-radius:14px; padding:14px; margin-bottom:16px; box-shadow:0 1px 2px rgba(0,0,0,.05); }}
    .plot {{ width:100%; height:440px; }}
  </style>
</head>
<body>
  <h1>TCMB Veri Grafikleri</h1>
  <p>Kaynak: <code>tcmb/data/*.jsonl</code></p>

  <div class="card"><div id="fx_all" class="plot"></div></div>
  <div class="card"><div id="fx_recent" class="plot"></div></div>
  <div class="card"><div id="inflation" class="plot"></div></div>

  <script>
    const usdX = {_json(usd_x)}, usdY = {_json(usd_y)};
    const eurX = {_json(eur_x)}, eurY = {_json(eur_y)};
    const gbpX = {_json(gbp_x)}, gbpY = {_json(gbp_y)};
    const cpiX = {_json(cpi_x)}, cpiY = {_json(cpi_y)};
    const coreX = {_json(core_x)}, coreY = {_json(core_y)};
    const foodX = {_json(food_x)}, foodY = {_json(food_y)};
    const ppiX = {_json(ppi_x)}, ppiY = {_json(ppi_y)};

    Plotly.newPlot('fx_all', [
      {{ x: usdX, y: usdY, mode: 'lines', name: 'USD/TRY alış' }},
      {{ x: eurX, y: eurY, mode: 'lines', name: 'EUR/TRY alış' }},
      {{ x: gbpX, y: gbpY, mode: 'lines', name: 'GBP/TRY alış' }},
    ], {{
      title: 'Kur Serileri (Tüm Dönem)',
      xaxis: {{ title: 'Tarih', rangeslider: {{ visible: true }} }},
      yaxis: {{ title: 'Kur' }},
      margin: {{ t: 50, r: 20, b: 40, l: 50 }},
    }}, {{responsive: true}});

    const lastN = 260;
    Plotly.newPlot('fx_recent', [
      {{ x: usdX.slice(-lastN), y: usdY.slice(-lastN), mode: 'lines', name: 'USD/TRY son 1 yıl' }},
      {{ x: eurX.slice(-lastN), y: eurY.slice(-lastN), mode: 'lines', name: 'EUR/TRY son 1 yıl' }},
      {{ x: gbpX.slice(-lastN), y: gbpY.slice(-lastN), mode: 'lines', name: 'GBP/TRY son 1 yıl' }},
    ], {{
      title: 'Kur Serileri (Son 1 Yıl)',
      xaxis: {{ title: 'Tarih' }},
      yaxis: {{ title: 'Kur' }},
      margin: {{ t: 50, r: 20, b: 40, l: 50 }},
    }}, {{responsive: true}});

    Plotly.newPlot('inflation', [
      {{ x: cpiX, y: cpiY, mode: 'lines', name: 'TÜFE Genel YoY' }},
      {{ x: coreX, y: coreY, mode: 'lines', name: 'TÜFE Çekirdek YoY' }},
      {{ x: foodX, y: foodY, mode: 'lines', name: 'TÜFE Gıda YoY' }},
      {{ x: ppiX, y: ppiY, mode: 'lines', name: 'Yİ-ÜFE Genel YoY' }},
    ], {{
      title: 'Enflasyon Göstergeleri (Yıllık % Değişim)',
      xaxis: {{ title: 'Tarih', rangeslider: {{ visible: true }} }},
      yaxis: {{ title: '%' }},
      margin: {{ t: 50, r: 20, b: 40, l: 50 }},
    }}, {{responsive: true}});
  </script>
</body>
</html>
"""


def main():
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(build_html(), encoding="utf-8")
    print(f"Dashboard olusturuldu: {OUT_FILE}")


if __name__ == "__main__":
    main()
