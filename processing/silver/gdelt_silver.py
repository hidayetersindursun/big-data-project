"""
Bronze gdelt → Silver gdelt

Bronze schema: id, date (YYYYMMDDHHMMSS), source, url, tone (double), themes (CSV), _ingested_at

Dönüşümler:
  - date string → DATE (günlük granülarite)
  - tone → tone (double)
  - themes string → food_related bool + turkey_related bool flag
  - url → has_turkey bool (URL'de turkey/turkiye/tr içeriyor mu)

Silver çıktısı iki tabloya yazılır:
  silver/gdelt_articles      → makale bazlı (filtre öncesi)
  silver/gdelt_daily          → günlük aggregate (food_security, Turkey filtered)

Gold/news_price_corr için silver/gdelt_daily yeterli olur.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

_S3_PREFIX = "s3" if os.environ.get("ON_EMR", "false").lower() == "true" else "s3a"
BRONZE_PATH = f"{_S3_PREFIX}://s3-bbuckett/bronze/gdelt"
SILVER_ARTICLES = f"{_S3_PREFIX}://s3-bbuckett/silver/gdelt_articles"
SILVER_DAILY = f"{_S3_PREFIX}://s3-bbuckett/silver/gdelt_daily"

# Food-related GDELT themes (GKG taxonomy)
FOOD_THEMES = [
    "FOOD_SECURITY",
    "WB_199_FOOD_SECURITY",
    "WB_435_AGRICULTURE_AND_FOOD_SECURITY",
    "WB_1967_AGRICULTURAL_RISK_AND_SECURITY",
    "UNGP_AFFORDABLE_NUTRITIOUS_FOOD",
    "ECON_PRICE",
    "AGRICULTURE",
    "WB_198_AGRICULTURE",
    "WB_433_AGRICULTURAL_VALUE_CHAIN",
    "FOOD_STAPLE",
    "ECON_INFLATION",
]

# Turkey-related GDELT themes
TURKEY_THEMES = [
    "TAX_WORLDLANGUAGES_TURKISH",
    "TAX_ETHNICITY_TURK",
    "TAX_ETHNICITY_TURKISH",
]


def has_any_theme_expr(themes_col, theme_list):
    """themes string'i bu listedeki theme'lardan birini içeriyor mu?"""
    cond = F.lit(False)
    for t in theme_list:
        cond = cond | F.col("themes").contains(t)
    return cond


def transform_articles(df):
    return (
        df
        # date: YYYYMMDDHHMMSS string → DATE
        .withColumn("date_str", F.substring(F.col("date"), 1, 8))
        .withColumn("date", F.to_date(F.col("date_str"), "yyyyMMdd"))
        .withColumn("food_related", has_any_theme_expr(F.col("themes"), FOOD_THEMES))
        .withColumn(
            "turkey_related",
            has_any_theme_expr(F.col("themes"), TURKEY_THEMES)
            | F.lower(F.col("url")).rlike(r"turkey|turkiye|t[uü]rk")
        )
        .withColumn("source", F.lit("gdelt"))
        .filter(F.col("date").isNotNull())
        .select(
            "id", "date", "url", "tone",
            "food_related", "turkey_related",
            "source",
        )
    )


def transform_daily(articles_df):
    """Günlük aggregate: total + food-only + turkey-food alt setler için count/mean tone."""
    return (
        articles_df
        .groupBy("date")
        .agg(
            F.count("*").alias("n_articles"),
            F.avg("tone").alias("avg_tone"),
            F.sum(F.when(F.col("tone") < -2.0, 1).otherwise(0)).alias("n_negative"),
            F.sum(F.when(F.col("food_related"), 1).otherwise(0)).alias("n_food"),
            F.avg(F.when(F.col("food_related"), F.col("tone"))).alias("avg_tone_food"),
            F.sum(F.when(F.col("food_related") & F.col("turkey_related"), 1).otherwise(0))
                .alias("n_turkey_food"),
            F.avg(F.when(F.col("food_related") & F.col("turkey_related"), F.col("tone")))
                .alias("avg_tone_turkey_food"),
        )
        .withColumn("year", F.year(F.col("date")))
        .withColumn("month", F.month(F.col("date")))
        .withColumn("source", F.lit("gdelt"))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--skip-articles", action="store_true",
                        help="Sadece daily aggregate yaz, articles tablosunu üretme (büyük)")
    args = parser.parse_args()

    spark = get_spark_session("gdelt_silver")
    spark.conf.set("spark.sql.shuffle.partitions", "100")

    df = spark.read.parquet(BRONZE_PATH)
    # Partition pruning: bronze/gdelt year/month/day partition'lı.
    # year/month kolonları üzerinden filtrele — yoksa tüm 90M+ satır taranır.
    if args.start_date:
        sy, sm = int(args.start_date[:4]), int(args.start_date[5:7])
        df = df.filter((F.col("year") * 100 + F.col("month")) >= sy * 100 + sm)
    if args.end_date:
        ey, em = int(args.end_date[:4]), int(args.end_date[5:7])
        df = df.filter((F.col("year") * 100 + F.col("month")) <= ey * 100 + em)

    articles = transform_articles(df)
    # cache: show + count + write üç action — cache'siz DAG 3 kez çalışır
    daily = transform_daily(articles).cache()

    print(f"=== silver/gdelt_daily ===")
    daily.printSchema()
    daily_count = daily.count()
    print(f"Daily satır: {daily_count:,}")
    daily.show(10, truncate=False)

    (
        daily
        .write
        .mode("overwrite")
        .partitionBy("year", "month")
        .parquet(SILVER_DAILY)
    )
    print(f"Yazıldı → {SILVER_DAILY}")

    if not args.skip_articles:
        articles_w = articles.withColumn("year", F.year("date")).withColumn("month", F.month("date"))
        (
            articles_w
            .write
            .mode("overwrite")
            .partitionBy("year", "month")
            .parquet(SILVER_ARTICLES)
        )
        print(f"Yazıldı → {SILVER_ARTICLES}")

    spark.stop()


if __name__ == "__main__":
    main()
