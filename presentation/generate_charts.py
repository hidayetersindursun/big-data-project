"""GıdaRadar final sunum — Gold katmanı verisinden grafik üretimi.

S3 (s3-bbuckett) Gold tablolarını okur, presentation/assets/ altına PNG üretir.
Kullanım:  python presentation/generate_charts.py
"""
import sys, io, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv

load_dotenv(".env")
import boto3
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS, exist_ok=True)
BUCKET = "s3-bbuckett"
s3 = boto3.client("s3", region_name="eu-central-1")

# Görsel kimlik
NAVY = "#1b2a4a"
TEAL = "#2a9d8f"
ORANGE = "#e76f51"
GOLD = "#e9c46a"
GREY = "#8d99ae"
plt.rcParams.update({
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "axes.labelsize": 13,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})


def load_gold(prefix, max_files=4000):
    """gold/<prefix>/ altındaki parquet dosyalarını tek DataFrame'e indir."""
    keys = []
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".parquet"):
                keys.append(o["Key"])
    dfs = []
    for k in keys[:max_files]:
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=k)
            dfs.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))
        except Exception as e:
            print(f"  skip {k}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def save(fig, name):
    path = os.path.join(ASSETS, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  -> {name}")


# ---------------------------------------------------------------- 1. compression
def chart_compression():
    # s3_bronze_upload_raporu.md doğrulanmış değerleri
    src = ["hal_all", "akaryakit", "epias", "commodities", "weather"]
    raw = [1028.0, 97.6, 254.3, 3.5, 33.0]      # MB ham (CSV/JSONL)
    parq = [61.7, 7.8, 41.4, 1.0, 17.2]          # MB parquet
    ratio = [r / p for r, p in zip(raw, parq)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    y = np.arange(len(src))
    a1.barh(y - 0.2, raw, 0.4, label="Raw (CSV/JSONL)", color=GREY)
    a1.barh(y + 0.2, parq, 0.4, label="Parquet (Snappy)", color=TEAL)
    a1.set_yticks(y); a1.set_yticklabels(src)
    a1.set_xlabel("Size (MB, log scale)"); a1.set_xscale("log")
    a1.set_title("Bronze: Raw vs Parquet Footprint")
    a1.legend(); a1.invert_yaxis()
    bars = a2.barh(y, ratio, color=ORANGE)
    a2.set_yticks(y); a2.set_yticklabels(src)
    a2.set_xlabel("Compression ratio  (raw / parquet)")
    a2.set_title("Storage Shrink Factor")
    a2.invert_yaxis()
    for b, r in zip(bars, ratio):
        a2.text(b.get_width() + 0.3, b.get_y() + b.get_height() / 2,
                f"{r:.1f}x", va="center", fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.suptitle("Parquet Conversion — up to ~17x smaller, columnar & partition-pruned",
                 fontsize=15, fontweight="bold", y=0.99)
    save(fig, "compression.png")


# ---------------------------------------------------------------- 2. source coverage
def chart_source_coverage():
    # Bronze parquet boyutu (MB) — s3_bronze_upload_raporu.md
    rows = [
        ("market_synthetic", 3200, "Daily"),
        ("market (live)", 14.8, "Daily"),
        ("hal_all (81 cities)", 61.7, "Daily"),
        ("gdelt (news)", 33.6, "15-min batch"),
        ("epias (26 sets)", 41.4, "Hourly"),
        ("weather (Open-Meteo)", 17.2, "Hourly"),
        ("akaryakit (fuel)", 7.8, "Daily"),
        ("commodities", 1.0, "Daily"),
        ("tcmb (FX/CPI)", 1.3, "Daily/Monthly"),
    ]
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    sizes = [r[1] for r in rows]
    freqs = [r[2] for r in rows]
    cmap = {"Daily": TEAL, "Hourly": NAVY, "15-min batch": ORANGE,
            "Daily/Monthly": GOLD}
    colors = [cmap[f] for f in freqs]
    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(names))
    bars = ax.barh(y, sizes, color=colors)
    ax.set_yticks(y); ax.set_yticklabels(names)
    ax.set_xscale("log")
    ax.set_xlabel("Bronze Parquet size (MB, log scale)")
    ax.set_title("9 Independent Data Sources — Bronze Layer Footprint")
    for b, s, f in zip(bars, sizes, freqs):
        ax.text(b.get_width() * 1.1, b.get_y() + b.get_height() / 2,
                f"{s:g} MB", va="center", fontsize=11)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in cmap.values()]
    ax.legend(handles, cmap.keys(), title="Update cadence", loc="lower right")
    save(fig, "source_coverage.png")


# ---------------------------------------------------------------- 3. daily margin
def chart_margin():
    df = load_gold("gold/daily_margin/")
    df = df[df["margin_pct"].notna()]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    clipped = df["margin_pct"].clip(-20, 320)
    a1.hist(clipped, bins=50, color=TEAL, edgecolor="white")
    med = df["margin_pct"].median()
    a1.axvline(med, color=ORANGE, lw=2.5, label=f"Median {med:.0f}%")
    a1.set_xlabel("Hal -> Market margin (%)")
    a1.set_ylabel("Daily price records")
    a1.set_title(f"Margin Distribution ({len(df) / 1e6:.2f}M records)")
    a1.legend()
    city = (df.groupby("city")["margin_pct"].median()
            .sort_values(ascending=False).head(12))
    a2.barh(city.index[::-1], city.values[::-1], color=NAVY)
    a2.set_xlabel("Median margin (%)")
    a2.set_title("Highest-Margin Provinces")
    for i, v in enumerate(city.values[::-1]):
        a2.text(v + 2, i, f"{v:.0f}%", va="center", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.suptitle("Daily Hal-to-Market Margin — shelf price typically near "
                 "double the wholesale price",
                 fontsize=15, fontweight="bold", y=0.99)
    save(fig, "margin_dist.png")


# ---------------------------------------------------------------- 4. rockets & feathers
def chart_rockets():
    df = load_gold("gold/rockets_feathers/")
    df = df[(df["n_obs"] >= 150) & df["asymmetry_score"].notna()]
    df = df[(df["asymmetry_score"] > 0) & (df["asymmetry_score"] < 5)]
    df = df.sort_values("asymmetry_score")
    top_feather = df.head(8)
    top_rocket = df.tail(8)
    sub = pd.concat([top_feather, top_rocket]).drop_duplicates("product_canonical")
    sub = sub.sort_values("asymmetry_score")
    colors = [ORANGE if v > 1 else TEAL for v in sub["asymmetry_score"]]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    y = np.arange(len(sub))
    ax.barh(y, sub["asymmetry_score"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([p.replace("_", " ").title() for p in sub["product_canonical"]])
    ax.axvline(1.0, color=NAVY, lw=2, ls="--")
    ax.text(1.02, len(sub) - 0.5, "symmetric (1.0)", color=NAVY, fontsize=11)
    ax.set_xlabel("Asymmetry score   =  Sum(beta+) / |Sum(beta-)|")
    ax.set_title("Rockets & Feathers — Asymmetric Price Transmission per Product")
    handles = [plt.Rectangle((0, 0), 1, 1, color=ORANGE),
               plt.Rectangle((0, 0), 1, 1, color=TEAL)]
    ax.legend(handles, ["> 1  Rocket (rises fast)", "< 1  Feather (falls slow)"],
              loc="lower right")
    save(fig, "rockets_feathers.png")


# ---------------------------------------------------------------- 5. shock propagation
def chart_shock():
    df = load_gold("gold/shock_propagation/")
    need = {"market_lag_days", "hal_lag_days", "peak_change_pct",
            "product_canonical"}
    if df.empty or not need.issubset(df.columns):
        print("  shock: beklenen kolonlar yok (tablo yeniden yazılıyor "
              "olabilir) — mevcut PNG korunuyor")
        return
    mkt = df["market_lag_days"].dropna()
    hal = df["hal_lag_days"].dropna()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    bins = np.arange(0, 33, 3)
    a1.hist([hal, mkt], bins=bins, color=[GOLD, ORANGE],
            label=["Hal (wholesale) lag", "Market (retail) lag"])
    a1.set_xlabel("Days from weather shock to +10% price")
    a1.set_ylabel("Shock x product cases")
    a1.set_title("Shock Propagation Lag")
    a1.legend()
    pk = df[df["peak_change_pct"].notna()]
    prod = (pk.groupby("product_canonical")["peak_change_pct"].median()
            .sort_values(ascending=False).head(10))
    a2.barh([p.replace("_", " ").title() for p in prod.index][::-1],
            prod.values[::-1], color=NAVY)
    a2.set_xlabel("Median peak price jump (%)")
    a2.set_title("Most Weather-Sensitive Products")
    for i, v in enumerate(prod.values[::-1]):
        a2.text(v + 0.3, i, f"{v:.0f}%", va="center", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.suptitle("Weather Shock -> Shelf Price — measured transmission delay",
                 fontsize=15, fontweight="bold", y=0.99)
    save(fig, "shock_lag.png")


# ---------------------------------------------------------------- 6. price inequality
def chart_inequality():
    df = load_gold("gold/price_inequality_market/")
    df = df[df["spread_pct"].notna()]
    prod = (df.groupby("product")["spread_pct"].median()
            .sort_values(ascending=False).head(14))
    fig, ax = plt.subplots(figsize=(12, 6.5))
    y = np.arange(len(prod))
    bars = ax.barh(y, prod.values[::-1], color=TEAL)
    ax.set_yticks(y)
    ax.set_yticklabels([p.replace("_", " ").title() for p in prod.index[::-1]])
    ax.set_xlabel("Median cross-province price spread  (max-min)/avg  (%)")
    ax.set_title("Inter-City Price Inequality — Same Product, 81 Provinces")
    for b, v in zip(bars, prod.values[::-1]):
        ax.text(b.get_width() + 0.4, b.get_y() + b.get_height() / 2,
                f"{v:.0f}%", va="center", fontsize=10)
    mean_cv = df["cv"].median()
    ax.text(0.98, 0.04, f"Median coefficient of variation: {mean_cv:.3f}",
            transform=ax.transAxes, ha="right", fontsize=11,
            bbox=dict(boxstyle="round", fc=GOLD, ec="none", alpha=0.6))
    save(fig, "price_inequality.png")


# ---------------------------------------------------------------- 7. macro corr
def chart_macro():
    df = load_gold("gold/macro_price_corr/")
    df = df[df["best_lag"] == True]
    df = df[df["correlation"].notna()]
    df["abs_corr"] = df["correlation"].abs()
    grp = (df.groupby("macro_series")["abs_corr"].mean()
           .sort_values(ascending=False).head(10))

    def short(s):
        s = str(s)
        return s[:34] + "..." if len(s) > 34 else s

    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(grp))
    bars = ax.barh(y, grp.values[::-1], color=NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels([short(s) for s in grp.index[::-1]])
    ax.set_xlabel("Mean |Pearson correlation| at best lag (0-30 days)")
    ax.set_title("External Drivers — Macro Factors vs Food Prices")
    for b, v in zip(bars, grp.values[::-1]):
        ax.text(b.get_width() + 0.005, b.get_y() + b.get_height() / 2,
                f"{v:.2f}", va="center", fontsize=10)
    save(fig, "macro_corr.png")


# ---------------------------------------------------------------- 8. forecast
def chart_forecast(product="Domates"):
    df = load_gold(f"gold/price_forecast/product_canonical={product}/")
    if df.empty:
        print("  forecast: veri yok, atlandi")
        return
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    hist = df[~df["is_forecast"]]
    fc = df[df["is_forecast"]]
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.fill_between(df["date"], df["yhat_lower"], df["yhat_upper"],
                    color=TEAL, alpha=0.2, label="Uncertainty band")
    ax.plot(hist["date"], hist["yhat"], color=NAVY, lw=2, label="Fitted (history)")
    if not fc.empty:
        ax.plot(fc["date"], fc["yhat"], color=ORANGE, lw=2.5,
                label="30-day forecast")
    cp = df[df["is_changepoint"] == True]
    for _, r in cp.iterrows():
        ax.axvline(r["date"], color=GREY, ls=":", lw=1)
    if not cp.empty:
        ax.plot([], [], color=GREY, ls=":", label="Trend changepoint")
    ax.set_xlabel("Date"); ax.set_ylabel("Price index (Prophet yhat)")
    ax.set_title(f"Prophet Forecast — {product} Price Trend, Seasonality & Changepoints")
    ax.legend(loc="upper left")
    save(fig, "forecast_domates.png")


if __name__ == "__main__":
    print("Grafikler uretiliyor (S3 Gold)...")
    # Her grafik bagimsiz; biri hata verirse digerleri ve onceki PNG korunur.
    for fn in (chart_compression, chart_source_coverage, chart_margin,
               chart_rockets, chart_shock, chart_inequality, chart_macro,
               chart_forecast):
        try:
            fn()
        except Exception as e:
            print(f"  ATLANDI {fn.__name__}: {e} — mevcut PNG korunuyor")
    print(f"Tamamlandi -> {ASSETS}")
