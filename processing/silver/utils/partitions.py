"""
Partition pruning yardımcısı.

silver/market_prices ve silver/market_hal_joined tabloları S3'te year/month ile
partition'lı. `date` bir partition kolonu DEĞİL — yalnızca `WHERE date >= ...`
filtresi Spark'ın partition pruning yapmasını sağlamaz; tüm yıllar taranır.

`filter_by_date_partitioned` aynı `date` filtresine ek olarak kaba bir year/month
predikatı ekler; Spark bunu S3 partition pruning'e pushdown eder → yalnızca ilgili
ay klasörleri okunur.
"""

from pyspark.sql import functions as F


def filter_by_date_partitioned(df, start_date=None, end_date=None):
    """date kolonuyla kesin filtre + year/month partition predikatıyla S3 pruning.

    df'te `year` ve `month` partition kolonları bulunmalıdır
    (market_prices, market_hal_joined). Sonuç, yalnızca `date` ile filtrelenmiş
    halle aynıdır — year/month predikatı yalnızca okumayı daraltır.
    """
    if start_date:
        sy, sm = int(start_date[:4]), int(start_date[5:7])
        df = df.filter(F.col("date") >= start_date).filter(
            (F.col("year") > sy) | ((F.col("year") == sy) & (F.col("month") >= sm))
        )
    if end_date:
        ey, em = int(end_date[:4]), int(end_date[5:7])
        df = df.filter(F.col("date") <= end_date).filter(
            (F.col("year") < ey) | ((F.col("year") == ey) & (F.col("month") <= em))
        )
    return df
