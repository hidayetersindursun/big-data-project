"""
Gold: rockets_feathers

Asimetrik fiyat geçişi: hal fiyatı arttığında market hızlı yansıtır mı, düştüğünde yavaş mı?

Algoritma (Asymmetric Error Correction Model — Engle-Granger varyantı):
  Δmkt_t = α + β⁺·max(Δhal_t, 0) + β⁻·min(Δhal_t, 0)
         + Σᵢ γ⁺ᵢ·max(Δhal_{t-i}, 0) + Σᵢ γ⁻ᵢ·min(Δhal_{t-i}, 0)
         + δ·(mkt_{t-1} - hal_{t-1})      [error-correction term]
         + ε

  asymmetry_score = (Σγ⁺ + β⁺) / (|Σγ⁻| + |β⁻|)
    > 1 → rockets (artışta hızlı yansıt)
    < 1 → feathers (düşüşte yavaş yansıt)
    1'in üstü tüketici aleyhine

Spark side : (product, market_name) gruplarında lag(1..7) feature engineering
Driver side: gözlem sayısı yeterli olan gruplarda statsmodels OLS

Çıktı: gold/rockets_feathers/  (~120 satır, flat)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql import Window
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/rockets_feathers"

MIN_OBS = 100         # bir grup için minimum gözlem
MAX_LAG = 7           # lag sayısı


def build_features(df):
    """Per (city, product, market) gün bazında lag feature'larını üret."""
    base = (
        df
        .filter(
            F.col("hal_price_per_kg").isNotNull()
            & F.col("market_price_per_kg").isNotNull()
            & (F.col("hal_price_per_kg") > 0)
        )
        .select(
            "date", "city", "product_canonical", "market_name",
            "hal_price_per_kg", "market_price_per_kg",
        )
    )

    # Aynı (date, product, market) için şehirler arası ortalama —
    # rockets&feathers chain-level analiz, şehir-spesifik değil
    chain_daily = (
        base
        .groupBy("date", "product_canonical", "market_name")
        .agg(
            F.avg("hal_price_per_kg").alias("hal"),
            F.avg("market_price_per_kg").alias("mkt"),
        )
    )

    w = Window.partitionBy("product_canonical", "market_name").orderBy("date")
    out = chain_daily
    for i in range(MAX_LAG + 1):
        out = (
            out
            .withColumn(f"hal_lag{i}", F.lag("hal", i).over(w))
            .withColumn(f"mkt_lag{i}", F.lag("mkt", i).over(w))
        )
    return out


def fit_group(pdf: pd.DataFrame) -> dict:
    """statsmodels ile asimetrik ECM fit et."""
    import statsmodels.api as sm

    # Δhal_t-i ve Δmkt_t hesapla
    df = pdf.sort_values("date").reset_index(drop=True)
    if len(df) < MIN_OBS:
        return None

    # Δmkt_t = mkt - mkt_lag1
    df["d_mkt"] = df["mkt"] - df["mkt_lag1"]

    # Δhal_t = hal - hal_lag1, ve geçmiş laglar Δhal_{t-i} = hal_lag(i) - hal_lag(i+1)
    df["d_hal_0"] = df["hal"] - df["hal_lag1"]
    for i in range(1, MAX_LAG):
        df[f"d_hal_{i}"] = df[f"hal_lag{i}"] - df[f"hal_lag{i+1}"]

    # Pozitif/negatif ayırma
    features = []
    for i in range(MAX_LAG):
        col = f"d_hal_{i}"
        df[f"{col}_pos"] = df[col].clip(lower=0)
        df[f"{col}_neg"] = df[col].clip(upper=0)  # negatif değerler korunur (<=0)
        features.append(f"{col}_pos")
        features.append(f"{col}_neg")

    # Error correction term: mkt_{t-1} - hal_{t-1}
    df["ec"] = df["mkt_lag1"] - df["hal_lag1"]
    features.append("ec")

    df_clean = df.dropna(subset=["d_mkt"] + features)
    if len(df_clean) < MIN_OBS:
        return None

    X = df_clean[features].values
    y = df_clean["d_mkt"].values
    X_const = sm.add_constant(X)

    try:
        model = sm.OLS(y, X_const).fit()
    except Exception:
        return None

    coefs = dict(zip(["const"] + features, model.params))
    pvals = dict(zip(["const"] + features, model.pvalues))

    pos_sum = sum(coefs[f"d_hal_{i}_pos"] for i in range(MAX_LAG))
    neg_sum = sum(coefs[f"d_hal_{i}_neg"] for i in range(MAX_LAG))

    # asymmetry_score: 0 koruması ile
    asym = abs(pos_sum) / (abs(neg_sum) + 1e-9)

    # half-life of EC term (eğer δ < 0 anlamlı ise stabilize ediyor demektir)
    delta = coefs["ec"]
    half_life = (np.log(0.5) / np.log(1 + delta)) if -1 < delta < 0 else np.nan

    return {
        "beta_up": float(pos_sum),
        "beta_down": float(neg_sum),
        "asymmetry_score": float(asym),
        "ec_coef": float(delta),
        "half_life_days": float(half_life) if not np.isnan(half_life) else None,
        "n_obs": int(len(df_clean)),
        "r_squared": float(model.rsquared),
        "ec_pvalue": float(pvals["ec"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--top-products", type=int, default=20,
                        help="En çok gözlemli ilk N ürünü işle (default: 20)")
    args = parser.parse_args()

    spark = get_spark_session("gold_rockets_feathers")
    spark.conf.set("spark.sql.shuffle.partitions", "100")

    df = spark.read.parquet(SILVER_JOINED)
    if args.start_date:
        df = df.filter(F.col("date") >= args.start_date)
    if args.end_date:
        df = df.filter(F.col("date") <= args.end_date)

    features = build_features(df)

    # Ürün × chain grup sayılarına göre top-N ürünü seç
    obs = (
        features
        .filter(F.col("hal").isNotNull() & F.col("mkt").isNotNull())
        .groupBy("product_canonical")
        .agg(F.count("*").alias("n"))
        .orderBy(F.col("n").desc())
        .limit(args.top_products)
    )
    top_products = [r["product_canonical"] for r in obs.collect()]
    print(f"Top {args.top_products} ürün: {top_products}")

    features_top = features.filter(F.col("product_canonical").isin(*top_products))

    # Driver tarafına çek (top N × ~6 chain × günler = manageable)
    print("Driver'a çekiyor...")
    pdf = features_top.toPandas()
    print(f"Driver'da satır: {len(pdf):,}")

    results = []
    for (prod, chain), group in pdf.groupby(["product_canonical", "market_name"]):
        if len(group) < MIN_OBS:
            continue
        res = fit_group(group)
        if res is None:
            continue
        res["product_canonical"] = prod
        res["market_name"] = chain
        results.append(res)

    print(f"Fit edilen (ürün × chain): {len(results)}")
    if not results:
        print("UYARI: Hiçbir grup yeterli gözlem alamadı.")
        spark.stop()
        return

    pdf_out = pd.DataFrame(results)
    out_df = spark.createDataFrame(pdf_out)
    out_df.printSchema()
    out_df.orderBy(F.col("asymmetry_score").desc()).show(30, truncate=False)

    (
        out_df
        .write
        .mode("overwrite")
        .partitionBy("market_name")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
