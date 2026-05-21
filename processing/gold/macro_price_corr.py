"""
Gold: macro_price_corr

Makro göstergelerin gıda fiyatı / marjı ile lag korelasyonu:
  - akaryakit  : yakıt fiyatı (ulaşım/lojistik maliyeti)
  - tcmb       : USD/TRY kuru, TÜFE-gıda, ticari kredi faizi (makro etken)
  - commodities: global emtia (buğday, brent — referans/öncü fiyat)
  - epias      : elektrik piyasa fiyatı (üretim/soğuk-zincir maliyeti)

Her makro seri × top-N gıda ürünü için lag 0..MAX_LAG Pearson korelasyon.
İki hedef: gıda fiyatı (price) ve hal↔market marjı (margin).
İki baz: ham seviye (level) ve fark serisi (change). Trendli seriler spurious
korelasyon ürettiği için 'change' birincil yorumlanmalı.

Çıktı: gold/macro_price_corr/macro_source=.../
  macro_source, macro_series, product_canonical, target_type, corr_basis,
  lag_days, correlation, p_value, n_obs, best_lag

news_price_corr.py ile aynı iskelet (Spark agg → toPandas → scipy.pearsonr).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

import pandas as pd
from pyspark.sql import functions as F
from utils.spark_session import get_spark_session
from utils.partitions import filter_by_date_partitioned  # noqa: E402

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
SILVER_AKARYAKIT = f"{_S3_PREFIX}://s3-bbuckett/silver/akaryakit"
SILVER_TCMB = f"{_S3_PREFIX}://s3-bbuckett/silver/tcmb"
SILVER_COMMODITIES = f"{_S3_PREFIX}://s3-bbuckett/silver/commodities"
SILVER_EPIAS_PC = f"{_S3_PREFIX}://s3-bbuckett/silver/epias/price_and_cost"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/macro_price_corr"

TOP_PRODUCTS = 15
DEFAULT_MAX_LAG = 30
COMMODITIES_MAX_LAG = 60          # global emtia geçişi yavaş → geniş lead-lag
MIN_OBS = 30                       # korelasyon için minimum ortak gözlem

# tcmb tall tablosundan çekilecek seriler (silver/tcmb.series_name)
TCMB_SERIES = ["usd_try_satis", "tufe_gida_yoy", "kredi_faiz_ticari"]


# ----------------------------------------------------------------------
# Makro seri hazırlama — her biri pandas DF: [date, macro_series, value]
# ----------------------------------------------------------------------
def akaryakit_series(spark):
    df = spark.read.parquet(SILVER_AKARYAKIT)
    daily = df.groupBy("date", "fuel_type").agg(F.avg("price_tl").alias("value"))
    pdf = daily.toPandas().rename(columns={"fuel_type": "macro_series"})
    return pdf[["date", "macro_series", "value"]]


def tcmb_series(spark):
    df = spark.read.parquet(SILVER_TCMB).filter(F.col("series_name").isin(*TCMB_SERIES))
    pdf = df.select("date", "series_name", "value").toPandas()
    return pdf.rename(columns={"series_name": "macro_series"})


def commodities_series(spark):
    df = spark.read.parquet(SILVER_COMMODITIES)
    daily = df.groupBy("date", "commodity_name").agg(F.avg("close").alias("value"))
    pdf = daily.toPandas().rename(columns={"commodity_name": "macro_series"})
    return pdf[["date", "macro_series", "value"]]


def epias_series(spark):
    """price_and_cost — şema dataset'e özgü; numeric fiyat kolonunu auto-detect et."""
    df = spark.read.parquet(SILVER_EPIAS_PC)
    numeric = [
        f.name for f in df.schema.fields
        if f.dataType.typeName() in ("double", "float", "integer", "long")
        and f.name not in ("year", "month")
    ]
    if not numeric:
        return None
    pref = [c for c in numeric if any(k in c.lower() for k in ("price", "mcp", "ptf", "cost"))]
    col = pref[0] if pref else numeric[0]
    daily = (
        df.withColumn("date", F.to_date("timestamp"))
        .groupBy("date")
        .agg(F.avg(col).alias("value"))
    )
    pdf = daily.toPandas()
    pdf["macro_series"] = f"epias_{col}"
    return pdf[["date", "macro_series", "value"]]


# ----------------------------------------------------------------------
# Korelasyon
# ----------------------------------------------------------------------
def _daily_ffill(s: pd.Series) -> pd.Series:
    """Seriyi günlük frekansa getir + forward-fill (tcmb aylık, hafta sonu boşlukları)."""
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        return s
    return s.asfreq("D").ffill()


def compute_corr(food_pdf, macro_pdf, macro_source, top_products, max_lag):
    from scipy.stats import pearsonr

    macro_pdf = macro_pdf.copy()
    macro_pdf["date"] = pd.to_datetime(macro_pdf["date"])
    food_pdf = food_pdf.copy()
    food_pdf["date"] = pd.to_datetime(food_pdf["date"])

    results = []
    for series in sorted(macro_pdf["macro_series"].dropna().unique()):
        m_raw = (
            macro_pdf[macro_pdf["macro_series"] == series]
            .set_index("date")["value"]
        )
        m_daily = _daily_ffill(m_raw)
        if m_daily.empty:
            continue

        for prod in top_products:
            f = food_pdf[food_pdf["product_canonical"] == prod].set_index("date").sort_index()
            for target, tcol in (("price", "market_price"), ("margin", "margin_pct")):
                fs = f[tcol].dropna()
                if len(fs) < MIN_OBS:
                    continue
                for basis in ("level", "change"):
                    fs_b = fs.diff().dropna() if basis == "change" else fs
                    m_b = m_daily.diff().dropna() if basis == "change" else m_daily

                    lag_rows = []
                    for lag in range(max_lag + 1):
                        merged = pd.concat(
                            [fs_b.rename("food"), m_b.shift(lag).rename("macro")],
                            axis=1, join="inner",
                        ).dropna()
                        if len(merged) < MIN_OBS:
                            continue
                        try:
                            r, p = pearsonr(merged["food"], merged["macro"])
                        except Exception:
                            continue
                        if pd.isna(r):
                            continue
                        lag_rows.append({
                            "macro_source": macro_source,
                            "macro_series": series,
                            "product_canonical": prod,
                            "target_type": target,
                            "corr_basis": basis,
                            "lag_days": lag,
                            "correlation": float(r),
                            "p_value": float(p),
                            "n_obs": int(len(merged)),
                            "best_lag": False,
                        })
                    if lag_rows:
                        bi = max(range(len(lag_rows)),
                                 key=lambda i: abs(lag_rows[i]["correlation"]))
                        lag_rows[bi]["best_lag"] = True
                        results.extend(lag_rows)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--top-products", type=int, default=TOP_PRODUCTS)
    args = parser.parse_args()

    spark = get_spark_session("gold_macro_price_corr")

    # silver_joined year/month partition'lı → year/month pruning ile S3 okumasını daralt.
    joined = filter_by_date_partitioned(
        spark.read.parquet(SILVER_JOINED), args.start_date, args.end_date
    ).filter(F.col("market_price_per_kg").isNotNull())

    # Top-N ürün (en çok kayıt)
    top = (
        joined.groupBy("product_canonical")
        .agg(F.count("*").alias("n"))
        .orderBy(F.col("n").desc())
        .limit(args.top_products)
        .collect()
    )
    top_products = [r["product_canonical"] for r in top]
    print(f"Top {args.top_products} ürün: {top_products}")

    # Günlük (date, product) → ulusal ortalama fiyat + marj
    food_pdf = (
        joined.filter(F.col("product_canonical").isin(*top_products))
        .groupBy("date", "product_canonical")
        .agg(
            F.avg("market_price_per_kg").alias("market_price"),
            F.avg("margin_pct").alias("margin_pct"),
        )
        .toPandas()
    )
    print(f"Gıda serisi satır: {len(food_pdf):,}")

    # Her makro kaynağı topla — epias graceful degradation
    sources = [
        ("akaryakit", akaryakit_series, DEFAULT_MAX_LAG),
        ("tcmb", tcmb_series, DEFAULT_MAX_LAG),
        ("commodities", commodities_series, COMMODITIES_MAX_LAG),
        ("epias", epias_series, DEFAULT_MAX_LAG),
    ]

    all_results = []
    for name, fn, max_lag in sources:
        try:
            macro_pdf = fn(spark)
        except Exception as e:
            print(f"  ATLANIYOR [{name}]: {e}")
            continue
        if macro_pdf is None or macro_pdf.empty:
            print(f"  ATLANIYOR [{name}]: boş")
            continue
        rows = compute_corr(food_pdf, macro_pdf, name, top_products, max_lag)
        print(f"  {name}: {len(rows):,} korelasyon satırı")
        all_results.extend(rows)

    if not all_results:
        print("UYARI: Hiçbir korelasyon hesaplanamadı.")
        spark.stop()
        return

    out_pdf = pd.DataFrame(all_results)
    print(f"Toplam: {len(out_pdf):,} satır")

    out_df = spark.createDataFrame(out_pdf)
    out_df.printSchema()
    (
        out_df
        .coalesce(1)
        .write
        .mode("overwrite")
        .partitionBy("macro_source")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
