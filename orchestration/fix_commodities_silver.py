"""
Commodities silver fix — mode("append") riskini kapat, bronze'dan temiz yaz.

Sorun: commodities_silver.py mode("append") kullanıyor → tekrar çalışırsa duplicate oluşur.
Çözüm: silver'ı silerek bronze'dan sıfırdan yaz.
"""

import io
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs

BUCKET = "s3-bbuckett"
BRONZE_PREFIX = "bronze/commodities"
SILVER_PREFIX = "silver/commodities"
REGION = "eu-central-1"


def read_bronze(s3):
    pg = s3.get_paginator("list_objects_v2")
    keys = [
        o["Key"]
        for page in pg.paginate(Bucket=BUCKET, Prefix=BRONZE_PREFIX + "/")
        for o in page.get("Contents", [])
        if o["Key"].endswith(".parquet")
    ]
    dfs = []
    for k in keys:
        obj = s3.get_object(Bucket=BUCKET, Key=k)
        dfs.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))
    return pd.concat(dfs, ignore_index=True)


def transform(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce").dt.date
    df["commodity_name"] = df["commodity_name"].str.replace("_", " ", regex=False)
    if "_ingested_at" in df.columns:
        df = df.drop(columns=["_ingested_at"])
    df["source"] = "commodities"
    df = df.dropna(subset=["date", "close"])
    return df[["date", "ticker", "commodity_name", "open", "high", "low", "close", "volume", "source"]]


def delete_silver(s3):
    pg = s3.get_paginator("list_objects_v2")
    keys = [
        {"Key": o["Key"]}
        for page in pg.paginate(Bucket=BUCKET, Prefix=SILVER_PREFIX + "/")
        for o in page.get("Contents", [])
    ]
    if keys:
        for i in range(0, len(keys), 1000):
            s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys[i:i+1000]})
        print(f"  Silindi: {len(keys)} eski silver dosyası")


def main():
    s3 = boto3.client("s3", region_name=REGION)
    fs = s3fs.S3FileSystem()

    print("=== Commodities Silver Fix ===")

    print("Bronze okunuyor...")
    bronze = read_bronze(s3)
    print(f"Toplam bronze: {len(bronze):,} satır")

    silver = transform(bronze)
    print(f"Dönüştürüldü: {len(silver):,} satır")

    summary = silver.groupby("commodity_name").agg(
        rows=("date", "count"),
        min_date=("date", "min"),
        max_date=("date", "max"),
    ).sort_index()
    print(summary.to_string())

    print("\nEski silver siliniyor...")
    delete_silver(s3)

    print("Silver yazılıyor...")
    table = pa.Table.from_pandas(silver, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=f"s3://{BUCKET}/{SILVER_PREFIX}",
        partition_cols=["commodity_name"],
        filesystem=fs,
        compression="snappy",
        existing_data_behavior="overwrite_or_ignore",
    )

    s3.put_object(Bucket=BUCKET, Key=f"{SILVER_PREFIX}/_SUCCESS", Body=b"")
    print(f"Silver yazıldı → s3://{BUCKET}/{SILVER_PREFIX}")
    print("=== Commodities Silver Fix TAMAMLANDI ===")


if __name__ == "__main__":
    main()
