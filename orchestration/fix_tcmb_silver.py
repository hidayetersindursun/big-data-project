"""
TCMB silver fix — duplicate temizle + overwrite

Sorun: tcmb_silver.py mode("append") kullandı → tüm 22 seri 2x duplicate.
Çözüm: bronze'dan sıfırdan oku, dönüştür, silver'ı silerek yeniden yaz.
"""

import io
import sys
import os
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs

BUCKET = "s3-bbuckett"
BRONZE_PREFIX = "bronze/tcmb"
SILVER_PREFIX = "silver/tcmb"
REGION = "eu-central-1"

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


def read_bronze(s3, series):
    prefix = f"{BRONZE_PREFIX}/{series}/"
    pg = s3.get_paginator("list_objects_v2")
    keys = [
        o["Key"]
        for page in pg.paginate(Bucket=BUCKET, Prefix=prefix)
        for o in page.get("Contents", [])
        if o["Key"].endswith(".parquet")
    ]
    if not keys:
        return pd.DataFrame()
    dfs = []
    for k in keys:
        obj = s3.get_object(Bucket=BUCKET, Key=k)
        dfs.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))
    df = pd.concat(dfs, ignore_index=True)
    df["series_name"] = series
    return df


def transform(df):
    # İki tarih formatını handle et: DD-MM-YYYY (günlük) ve YYYY-MM (aylık)
    dates = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    monthly_mask = dates.isna()
    if monthly_mask.any():
        monthly = pd.to_datetime(
            df.loc[monthly_mask, "date"].astype(str) + "-01",
            format="%Y-%m-%d",
            errors="coerce",
        )
        dates[monthly_mask] = monthly

    df = df.copy()
    df["date"] = dates.dt.date
    df["source"] = "tcmb"
    df = df.dropna(subset=["date", "value"])
    return df[["date", "series_name", "value", "source"]]


def delete_silver(s3):
    pg = s3.get_paginator("list_objects_v2")
    keys = [
        {"Key": o["Key"]}
        for page in pg.paginate(Bucket=BUCKET, Prefix=SILVER_PREFIX + "/")
        for o in page.get("Contents", [])
    ]
    if keys:
        # batch delete 1000'er
        for i in range(0, len(keys), 1000):
            s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys[i:i+1000]})
        print(f"  Silindi: {len(keys)} eski silver dosyası")


def main():
    s3 = boto3.client("s3", region_name=REGION)
    fs = s3fs.S3FileSystem(key=None, secret=None)  # ~/.aws/credentials kullanır

    print("=== TCMB Silver Fix ===")

    # 1. Bronze oku
    print("Bronze okunuyor...")
    dfs = []
    for series in SERIES_FOLDERS:
        df = read_bronze(s3, series)
        if df.empty:
            print(f"  UYARI: {series} bronzda yok, atlandı")
            continue
        dfs.append(df)
        print(f"  {series}: {len(df)} satır")

    all_bronze = pd.concat(dfs, ignore_index=True)
    print(f"Toplam bronze: {len(all_bronze):,} satır")

    # 2. Dönüştür
    all_silver = transform(all_bronze)
    print(f"Dönüştürüldü: {len(all_silver):,} satır")

    # Duplicate kontrol
    dup = all_silver.duplicated(subset=["date", "series_name"]).sum()
    print(f"Duplicate (bronze'da): {dup}")

    # Seri bazlı özet
    summary = all_silver.groupby("series_name").agg(
        rows=("date", "count"),
        min_date=("date", "min"),
        max_date=("date", "max"),
    ).sort_index()
    print(summary.to_string())

    # 3. Eski silver sil
    print("\nEski silver siliniyor...")
    delete_silver(s3)

    # 4. Yeniden yaz
    print("Silver yazılıyor...")
    table = pa.Table.from_pandas(all_silver, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=f"s3://{BUCKET}/{SILVER_PREFIX}",
        partition_cols=["series_name"],
        filesystem=fs,
        compression="snappy",
        existing_data_behavior="overwrite_or_ignore",
    )

    # _SUCCESS marker
    s3.put_object(Bucket=BUCKET, Key=f"{SILVER_PREFIX}/_SUCCESS", Body=b"")
    print(f"Silver yazıldı → s3://{BUCKET}/{SILVER_PREFIX}")
    print("=== TCMB Silver Fix TAMAMLANDI ===")


if __name__ == "__main__":
    main()
