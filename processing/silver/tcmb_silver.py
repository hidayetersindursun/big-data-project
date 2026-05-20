"""
Bronze tcmb → Silver tcmb

Bronze yapısı: her seri kendi klasöründe (usd_try_alis/, eur_try_alis/, vb.)
Her klasörde: year=/month=/part-0000.parquet
Her satır: date (DD-MM-YYYY), value (double), series (TCMB kodu)

Dönüşümler:
  - date (DD-MM-YYYY string) → date (DATE)
  - series kodu → okunabilir series_name
  - Tüm seriler tek tabloda (tall format)
  - source etiketi eklendi
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

BRONZE_PATH = "s3a://s3-bbuckett/bronze/tcmb"
SILVER_PATH = "s3a://s3-bbuckett/silver/tcmb"

# Bronze'daki tüm seri klasörleri
SERIES_FOLDERS = [
    "usd_try_alis", "usd_try_satis",
    "eur_try_alis", "eur_try_satis",
    "gbp_try_alis",
    "kredi_faiz_ticari", "kredi_faiz_tuketici",
    "tufe_cekirdek_yoy", "tufe_genel_yoy", "tufe_gida_alkolsuz_yoy",
    "tufe_gida_yoy", "tufe_islem_disi_yoy", "tufe_konut_enerji_yoy",
    "tufe_taze_meyve_sebze_yoy", "tufe_ulastirma_yoy",
    "yiufe_elektrik_gaz_yoy", "yiufe_genel_yoy", "yiufe_gida_imalat_yoy",
    "yiufe_hayvancilik_yoy", "yiufe_icecek_imalat_yoy",
    "yiufe_tarim_yoy", "yiufe_ulastirma_yoy",
]


def read_all_series(spark):
    from functools import reduce
    dfs = []
    for series in SERIES_FOLDERS:
        df = (
            spark.read.parquet(f"{BRONZE_PATH}/{series}")
            .withColumn("series_name", F.lit(series))
        )
        dfs.append(df)
    return reduce(lambda a, b: a.union(b), dfs)


def transform(df):
    return (
        df
        # İki farklı tarih formatını handle et:
        #   Günlük seriler (döviz): DD-MM-YYYY
        #   Aylık seriler (TÜFE, faiz): YYYY-MM → ayın ilk günü
        .withColumn(
            "date",
            F.coalesce(
                F.to_date(F.col("date"), "dd-MM-yyyy"),
                F.to_date(F.concat(F.col("date"), F.lit("-01")), "yyyy-MM-dd"),
            )
        )

        # Kaynak etiketi
        .withColumn("source", F.lit("tcmb"))

        # Null tarih veya değer satırlarını at
        .filter(F.col("date").isNotNull() & F.col("value").isNotNull())

        .select("date", "series_name", "value", "source")
    )


def main():
    spark = get_spark_session("tcmb_silver")

    df_bronze = read_all_series(spark)
    df_silver = transform(df_bronze)

    print(f"Bronze satır sayısı : {df_bronze.count():,}")
    print(f"Silver satır sayısı : {df_silver.count():,}")
    df_silver.printSchema()
    df_silver.show(10, truncate=False)

    print("\n=== Seri dağılımı ===")
    df_silver.groupBy("series_name").count().orderBy("series_name").show(truncate=False)

    (
        df_silver
        .write
        .mode("append")
        .partitionBy("series_name")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
