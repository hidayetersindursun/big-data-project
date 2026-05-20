import os
from pathlib import Path

from pyspark.sql import SparkSession

# ON_EMR=true olduğunda YARN + instance profile kullanılır (credential/master config atlanır)
_ON_EMR = os.environ.get("ON_EMR", "false").lower() == "true"

# Proje kökü: processing/silver/utils/spark_session.py → 3 seviye yukarı
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_env():
    """Proje kökündeki .env'i ortama yükle (zaten set olanları ezmez)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
    except ImportError:
        pass


def _aws_credentials():
    """
    AWS anahtarlarını ortamdan al.
    .env'de proje genelinde `AWS_ACCESS_KEY` kullanılıyor; boto3/standart `AWS_ACCESS_KEY_ID`
    de destekleniyor — ikisinden hangisi varsa onu kullan.
    """
    key = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not key or not secret:
        raise RuntimeError(
            "AWS kimlik bilgileri bulunamadı. .env'de AWS_ACCESS_KEY (veya "
            "AWS_ACCESS_KEY_ID) ve AWS_SECRET_ACCESS_KEY tanımlı olmalı."
        )
    return key, secret


def get_spark_session(app_name: str) -> SparkSession:
    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.session.timeZone", "Europe/Istanbul")
    )

    if not _ON_EMR:
        _load_env()
        aws_key, aws_secret = _aws_credentials()
        builder = (
            builder
            .master("local[*]")
            .config("spark.hadoop.fs.defaultFS", "file:///")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.hadoop.fs.s3a.access.key", aws_key)
            .config("spark.hadoop.fs.s3a.secret.key", aws_secret)
            .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com")
            .config("spark.hadoop.fs.s3a.path.style.access", "false")
        )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
