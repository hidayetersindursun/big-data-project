"""
Gold: shock_propagation

Hava olayı tetikleyici (frost / heat / heavy rain) → hal fiyat sıçraması → market fiyat sıçraması
arasındaki lag günü.

Algoritma:
  1. Per (city, date), hava verisinden shock event tespit et:
       frost          : temp_min_c < 0
       heat           : temp_max_c > 35
       heavy_rain     : precipitation_mm > 50
  2. Top-20 iklim-hassas ürün (domates_sofralik, salatalik, biber, vs.)
  3. Her event için:
       baseline = avg(hal_price_t-7..t-1) for this (city, product)
       hal_lag_days = ilk t+k gün (k=1..30) ki hal_price_t+k > 1.1 * baseline
       market_lag_days = aynı şekilde market için
       peak_change_pct = max(hal_price_t..t+30) / baseline - 1
  4. Output: event_date, city, event_type, product_canonical, hal_lag_days, market_lag_days, peak_change_pct
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

import pandas as pd
from pyspark.sql import functions as F
from utils.spark_session import get_spark_session
from utils.cities import normalize_city_expr  # noqa: E402

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_WEATHER = f"{_S3_PREFIX}://s3-bbuckett/silver/weather_daily"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/shock_propagation"

# İklim-hassas ürünler (canonical isimleri ile)
CLIMATE_SENSITIVE = [
    "domates_sofralik", "domates_salkim", "salatalik",
    "biber_sivri", "biber_dolma", "biber_carliston",
    "patlican", "kabak", "marul", "maydanoz", "mantar",
    "elma", "armut", "uzum", "kayisi", "seftali", "kiraz",
    "cilek", "limon", "portakal",
]


def detect_shocks(weather_df):
    return (
        weather_df
        .withColumn("city", normalize_city_expr(F.col("city")))
        .withColumn(
            "event_type",
            F.when(F.col("temp_min_c") < 0, "frost")
             .when(F.col("temp_max_c") > 35, "heat")
             .when(F.col("precipitation_mm") > 50, "heavy_rain")
             .otherwise(None)
        )
        .filter(F.col("event_type").isNotNull())
        .select("date", "city", "event_type")
    )


def compute_propagation(shocks_pdf: pd.DataFrame, prices_pdf: pd.DataFrame) -> list:
    """Her shock için lag hesapla. prices_pdf: (date, city, product_canonical, hal_price, market_price)."""
    results = []
    prices_pdf = prices_pdf.copy()
    prices_pdf["date"] = pd.to_datetime(prices_pdf["date"])
    shocks_pdf = shocks_pdf.copy()
    shocks_pdf["date"] = pd.to_datetime(shocks_pdf["date"])

    # Hızlı index için
    prices_grouped = {
        (city, prod): g.sort_values("date").reset_index(drop=True)
        for (city, prod), g in prices_pdf.groupby(["city", "product_canonical"])
    }

    for _, row in shocks_pdf.iterrows():
        event_date = row["date"]
        city = row["city"]
        event_type = row["event_type"]

        for prod in CLIMATE_SENSITIVE:
            g = prices_grouped.get((city, prod))
            if g is None or len(g) < 10:
                continue

            # Baseline: önceki 7 günün hal ortalaması
            mask_pre = (g["date"] >= event_date - pd.Timedelta(days=7)) & (g["date"] < event_date)
            pre = g.loc[mask_pre]
            if len(pre) < 3 or pre["hal_price_per_kg"].mean() <= 0:
                continue
            baseline_hal = pre["hal_price_per_kg"].mean()
            baseline_mkt = pre["market_price_per_kg"].dropna().mean() if pre["market_price_per_kg"].notna().any() else None

            # Post window: t..t+30
            mask_post = (g["date"] >= event_date) & (g["date"] <= event_date + pd.Timedelta(days=30))
            post = g.loc[mask_post]
            if len(post) < 5:
                continue

            # hal_lag_days
            hal_threshold = baseline_hal * 1.10
            hal_lag_row = post[post["hal_price_per_kg"] > hal_threshold].head(1)
            hal_lag = (hal_lag_row["date"].iloc[0] - event_date).days if not hal_lag_row.empty else None

            # market_lag_days
            mkt_lag = None
            if baseline_mkt and baseline_mkt > 0:
                mkt_threshold = baseline_mkt * 1.10
                mkt_lag_row = post[post["market_price_per_kg"] > mkt_threshold].head(1)
                mkt_lag = (mkt_lag_row["date"].iloc[0] - event_date).days if not mkt_lag_row.empty else None

            peak_hal = post["hal_price_per_kg"].max()
            peak_change_pct = ((peak_hal - baseline_hal) / baseline_hal * 100) if baseline_hal > 0 else None

            results.append({
                "event_date": event_date.date(),
                "city": city,
                "event_type": event_type,
                "product_canonical": prod,
                "baseline_hal_price": float(baseline_hal),
                "peak_hal_price": float(peak_hal) if pd.notna(peak_hal) else None,
                "peak_change_pct": float(peak_change_pct) if peak_change_pct is not None else None,
                "hal_lag_days": int(hal_lag) if hal_lag is not None else None,
                "market_lag_days": int(mkt_lag) if mkt_lag is not None else None,
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    args = parser.parse_args()

    spark = get_spark_session("gold_shock_propagation")
    spark.conf.set("spark.sql.shuffle.partitions", "100")

    weather = spark.read.parquet(SILVER_WEATHER)
    if args.start_date:
        weather = weather.filter(F.col("date") >= args.start_date)
    if args.end_date:
        weather = weather.filter(F.col("date") <= args.end_date)

    shocks = detect_shocks(weather)
    print(f"Detected shocks: {shocks.count():,}")
    shocks.groupBy("event_type").count().show()

    joined = (
        spark.read.parquet(SILVER_JOINED)
        .filter(F.col("product_canonical").isin(*CLIMATE_SENSITIVE))
        .select("date", "city", "product_canonical",
                "hal_price_per_kg", "market_price_per_kg")
    )
    if args.start_date:
        # Genişletilmiş aralık — shock öncesi 7 gün ve sonrası 30 gün için
        joined = joined.filter(F.col("date") >= args.start_date)
    if args.end_date:
        joined = joined.filter(F.col("date") <= args.end_date)

    shocks_pdf = shocks.toPandas()
    prices_pdf = joined.toPandas()
    print(f"Shocks (driver): {len(shocks_pdf):,}  Prices (driver): {len(prices_pdf):,}")

    results = compute_propagation(shocks_pdf, prices_pdf)
    print(f"Propagation kayıt: {len(results)}")

    if not results:
        print("UYARI: Sonuç boş.")
        spark.stop()
        return

    pdf_out = pd.DataFrame(results)
    out_df = spark.createDataFrame(pdf_out)
    out_df.printSchema()
    out_df.show(20, truncate=False)

    (
        out_df
        .write
        .mode("overwrite")
        .partitionBy("event_type")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
