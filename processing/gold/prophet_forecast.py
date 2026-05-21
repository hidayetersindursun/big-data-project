"""
Gold: prophet_forecast

Meta Prophet ile top-20 ürünün zaman serisi tahmini.
Pandemic changepoint detection — 2020-03 civarı otomatik tespit edilirse 'is_changepoint' flag.

Sürücü-tabanlı sıralı fit: top-20 ürün × tek Prophet model.
NOT: Prophet'in Stan backend'i Spark executor sandbox'ında çalışmadığı için
applyInPandas ile DAĞITILMAZ — fit sürücüde (AM) yapılır. Veri küçük olduğu için
(20 ürün × günlük seri) sürücüde toPandas + döngü RAM-safe ve yeterince hızlı.

Çıktı: gold/price_forecast/
  product_canonical, date, yhat, yhat_lower, yhat_upper,
  is_changepoint (bool), is_forecast (bool)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

import pandas as pd
from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_HAL = f"{_S3_PREFIX}://s3-bbuckett/silver/hal_prices"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/price_forecast"

FORECAST_DAYS = 30


def fit_one(pdf: pd.DataFrame, product: str, forecast_days: int) -> pd.DataFrame:
    from prophet import Prophet

    ts = (
        pdf
        .dropna(subset=["price_avg"])
        .groupby("date")["price_avg"]
        .mean()
        .reset_index()
        .rename(columns={"date": "ds", "price_avg": "y"})
    )
    ts["ds"] = pd.to_datetime(ts["ds"])
    if len(ts) < 30:
        return None

    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        interval_width=0.8,
    )
    m.fit(ts)

    future = m.make_future_dataframe(periods=forecast_days, freq="D")
    fcst = m.predict(future)

    # Changepoint detection
    cps = pd.to_datetime(m.changepoints)
    fcst["is_changepoint"] = fcst["ds"].isin(cps)
    fcst["is_forecast"] = fcst["ds"] > ts["ds"].max()
    fcst["product_canonical"] = product

    return fcst[[
        "product_canonical", "ds", "yhat", "yhat_lower", "yhat_upper",
        "is_changepoint", "is_forecast",
    ]].rename(columns={"ds": "date"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-products", type=int, default=20)
    parser.add_argument("--forecast-days", type=int, default=FORECAST_DAYS)
    parser.add_argument("--products", type=str, default=None,
                        help="Belirli ürünler (comma-separated hal product_name)")
    args = parser.parse_args()

    spark = get_spark_session("gold_prophet_forecast")

    hal = spark.read.parquet(SILVER_HAL).filter(F.col("price_avg").isNotNull())

    if args.products:
        products = args.products.split(",")
    else:
        # En çok kayıt sayısına sahip ürünleri al
        top = (
            hal
            .groupBy("product_name")
            .agg(F.count("*").alias("n"))
            .orderBy(F.col("n").desc())
            .limit(args.top_products)
            .collect()
        )
        products = [r["product_name"] for r in top]
    print(f"Forecast ürünleri: {products}")

    # Top-20 ürünün hal verisini sürücüye al (20 ürün × günlük seri = küçük, RAM-safe)
    pdf = (
        hal
        .filter(F.col("product_name").isin(*products))
        .select("date", "product_name", "price_avg")
        .toPandas()
    )
    print(f"Driver'da satır: {len(pdf):,}")

    all_results = []
    for prod in products:
        sub = pdf[pdf["product_name"] == prod]
        print(f"  Fit ediliyor: {prod}  ({len(sub)} satır)")
        try:
            res = fit_one(sub, prod, args.forecast_days)
        except Exception as e:
            print(f"    HATA: {e}")
            continue
        if res is not None:
            all_results.append(res)

    if not all_results:
        print("UYARI: Hiçbir model fit edilemedi.")
        spark.stop()
        return

    out_pdf = pd.concat(all_results, ignore_index=True)
    print(f"Toplam forecast satır: {len(out_pdf):,}")

    out_df = spark.createDataFrame(out_pdf)
    out_df.printSchema()

    (
        out_df
        .coalesce(1)
        .write
        .mode("overwrite")
        .partitionBy("product_canonical")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
