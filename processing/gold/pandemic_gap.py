"""
Gold: pandemic_gap

Pandemi öncesi (2019) vs sonrası dönemler (2021, 2022, 2023, 2024) marj farkı.

Önemli: market verisi 2019-2025 arası sentetik (market_synthetic). Bunu net olarak hocaya söyle.

Per (product_canonical, market_name):
  baseline_year = 2019
  comparison_year ∈ {2021, 2022, 2023, 2024}
  baseline_margin = avg(margin_pct) for baseline_year
  post_margin     = avg(margin_pct) for comparison_year
  gap_widening_pct = (post - baseline) / |baseline| * 100
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "silver"))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
SILVER_JOINED = f"{_S3_PREFIX}://s3-bbuckett/silver/market_hal_joined"
GOLD_OUT = f"{_S3_PREFIX}://s3-bbuckett/gold/pandemic_gap"

BASELINE_YEAR = 2019
COMPARISON_YEARS = [2021, 2022, 2023, 2024]


def main():
    spark = get_spark_session("gold_pandemic_gap")

    df = (
        spark.read.parquet(SILVER_JOINED)
        .filter(F.col("margin_pct").isNotNull())
        .filter(F.col("year").isin(BASELINE_YEAR, *COMPARISON_YEARS))
    )

    yearly = (
        df
        .groupBy("year", "product_canonical", "market_name")
        .agg(
            F.avg("margin_pct").alias("avg_margin_pct"),
            F.avg("hal_price_per_kg").alias("avg_hal"),
            F.avg("market_price_per_kg").alias("avg_market"),
            F.count("*").alias("n_obs"),
        )
    )

    baseline = (
        yearly
        .filter(F.col("year") == BASELINE_YEAR)
        .select(
            "product_canonical", "market_name",
            F.col("avg_margin_pct").alias("baseline_margin"),
            F.col("avg_hal").alias("baseline_hal"),
            F.col("avg_market").alias("baseline_market"),
            F.col("n_obs").alias("baseline_n"),
        )
    )

    comparison = (
        yearly
        .filter(F.col("year").isin(*COMPARISON_YEARS))
        .select(
            F.col("year").alias("comparison_year"),
            "product_canonical", "market_name",
            F.col("avg_margin_pct").alias("post_margin"),
            F.col("avg_hal").alias("post_hal"),
            F.col("avg_market").alias("post_market"),
            F.col("n_obs").alias("post_n"),
        )
    )

    out = (
        comparison
        .join(baseline, ["product_canonical", "market_name"], "inner")
        .withColumn("baseline_year", F.lit(BASELINE_YEAR))
        .withColumn(
            "gap_widening_pct",
            F.when(
                F.col("baseline_margin").isNotNull() & (F.abs(F.col("baseline_margin")) > 1e-6),
                (F.col("post_margin") - F.col("baseline_margin")) / F.abs(F.col("baseline_margin")) * 100,
            )
        )
        .select(
            "product_canonical", "market_name",
            "baseline_year", "comparison_year",
            "baseline_margin", "post_margin", "gap_widening_pct",
            "baseline_hal", "post_hal", "baseline_market", "post_market",
            "baseline_n", "post_n",
        )
    )

    out.printSchema()
    n = out.count()
    print(f"\nPandemic gap satır: {n:,}")
    out.orderBy(F.col("gap_widening_pct").desc()).show(30, truncate=False)

    (
        out
        .write
        .mode("overwrite")
        .partitionBy("comparison_year")
        .parquet(GOLD_OUT)
    )
    print(f"Yazıldı → {GOLD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
