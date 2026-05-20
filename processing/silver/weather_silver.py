"""
Bronze weather → Silver weather_daily

Dönüşümler:
  - time (timestamp) → date (DATE)
  - cloud_amt kaldırıldı (%100 null)
  - Teknik sütun isimleri okunabilir hale getirildi
  - source etiketi eklendi
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.sql import functions as F
from utils.spark_session import get_spark_session

BRONZE_PATH = "s3a://s3-bbuckett/bronze/weather"
SILVER_PATH = "s3a://s3-bbuckett/silver/weather_daily"


def transform(df):
    return (
        df
        # timestamp → DATE
        .withColumn("date", F.to_date(F.col("time")))

        # Sütun isimlerini okunabilir hale getir
        .withColumnRenamed("t2m_max", "temp_max_c")
        .withColumnRenamed("t2m_min", "temp_min_c")
        .withColumnRenamed("t2m", "temp_avg_c")
        .withColumnRenamed("t2mdew", "dew_point_c")
        .withColumnRenamed("prectotcorr", "precipitation_mm")
        .withColumnRenamed("ws10m", "wind_speed_ms")
        .withColumnRenamed("wd10m", "wind_dir_deg")
        .withColumnRenamed("ws10m_max", "wind_speed_max_ms")
        .withColumnRenamed("rh2m", "humidity_pct")
        .withColumnRenamed("allsky_sfc_sw_dwn", "solar_rad_mj")
        .withColumnRenamed("ps", "pressure_kpa")
        .withColumnRenamed("et0_fao_evapotranspiration", "evapotranspiration_mm")

        # cloud_amt kaldır (%100 null)
        .drop("cloud_amt", "time")

        # Kaynak etiketi
        .withColumn("source", F.lit("weather"))

        # Sütun sırası
        .select(
            "date", "city_id", "city", "region",
            "temp_max_c", "temp_min_c", "temp_avg_c", "dew_point_c",
            "precipitation_mm", "humidity_pct",
            "wind_speed_ms", "wind_speed_max_ms", "wind_dir_deg",
            "solar_rad_mj", "pressure_kpa",
            "evapotranspiration_mm", "soil_moisture_mm",
            "source"
        )
    )


def main():
    spark = get_spark_session("weather_silver")

    df_bronze = spark.read.parquet(BRONZE_PATH)
    df_silver = transform(df_bronze)

    print(f"Bronze satır sayısı : {df_bronze.count():,}")
    print(f"Silver satır sayısı : {df_silver.count():,}")
    df_silver.printSchema()
    df_silver.show(5, truncate=False)

    (
        df_silver
        .write
        .mode("append")
        .partitionBy("date")
        .parquet(SILVER_PATH)
    )

    print(f"Silver yazıldı → {SILVER_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
