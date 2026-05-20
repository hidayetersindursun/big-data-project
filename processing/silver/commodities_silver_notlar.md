# Commodities Silver Geçişi — Notlar

## Bronze Kaynak

- **Path**: `s3://s3-bbuckett/bronze/commodities/`
- **Yapı**: `year={yil}/month={ay}/part-0000.parquet`
- **Kapsam**: 2020 → 2024 (77 dosya)
- **Boyut**: ~1.0 MiB
- **Kaynak**: Yahoo Finance vadeli işlem fiyatları (USD bazlı)

## Bronze Şeması (Ham)

| Sütun | Tip | Notlar |
|---|---|---|
| `date` | string | `YYYY-MM-DD` — zaten standart |
| `ticker` | string | Yahoo Finance kodu (ZW=F, ZC=F vb.) |
| `commodity_name` | string | Alt çizgili isim (Brent_Oil, Natural_Gas vb.) |
| `open` | double | Açılış fiyatı (USD) |
| `high` | double | Günlük en yüksek (USD) |
| `low` | double | Günlük en düşük (USD) |
| `close` | double | Kapanış fiyatı (USD) |
| `volume` | double | İşlem hacmi |
| `_ingested_at` | string | Ingestion zaman damgası — Silver'da gerek yok |

## Emtialar

| Ticker | Emtia | Projedeki Rolü |
|---|---|---|
| `ZW=F` | Wheat (Buğday) | Ekmek/un fiyatlarına etki |
| `ZC=F` | Corn (Mısır) | Yem maliyeti → et/süt fiyatları |
| `ZS=F` | Soybeans (Soya) | Yem + yağ maliyeti |
| `BZ=F` | Brent Oil (Brent Petrol) | Nakliye + enerji maliyeti |
| `NG=F` | Natural Gas (Doğalgaz) | Isınma + üretim maliyeti |
| `SB=F` | Sugar (Şeker) | Doğrudan gıda fiyatı |
| `CT=F` | Cotton (Pamuk) | Ambalaj maliyeti |
| `KC=F` | Coffee (Kahve) | Doğrudan gıda fiyatı |
| `LE=F` | Live Cattle (Canlı sığır) | Et fiyatlarına etki |
| `ZL=F` | Soybean Oil (Soya yağı) | Yemeklik yağ fiyatı |

## Mimari Kararlar

- `_ingested_at` kaldırıldı — Silver'da anlamsız metadata
- `commodity_name` alt çizgi temizlendi (`Brent_Oil` → `Brent Oil`)
- Partition: `commodity_name` — 10 emtia, her biri tüm tarihleri içerir (TCMB gibi)
- USD bazlı fiyatlar olduğu gibi korundu — Gold'da TCMB kuru ile TL'ye çevrilebilir

## Silver commodities — Final Tablo

| Sütun | Tip | Örnek |
|---|---|---|
| `date` | DATE | `2020-01-02` |
| `ticker` | string | `ZW=F` |
| `commodity_name` | string | `Wheat` |
| `open` | double | `559.5` |
| `high` | double | `567.5` |
| `low` | double | `558.25` |
| `close` | double | `560.25` |
| `volume` | double | `49931.0` |
| `source` | string | `commodities` |

## Çalıştırma

```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
SPARK_HOME=/home/ubuntu/spark PYSPARK_PYTHON=python3 \
/home/ubuntu/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  processing/silver/commodities_silver.py
```
