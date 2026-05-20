import os
from pyspark.sql import SparkSession

# ON_EMR=true olduğunda YARN + instance profile kullanılır (credential/master config atlanır)
_ON_EMR = os.environ.get("ON_EMR", "false").lower() == "true"


def get_spark_session(app_name: str) -> SparkSession:
    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.session.timeZone", "Europe/Istanbul")
    )

    if not _ON_EMR:
        aws_key = os.environ["AWS_ACCESS_KEY_ID"]
        aws_secret = os.environ["AWS_SECRET_ACCESS_KEY"]
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
