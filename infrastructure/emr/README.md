# EMR — GıdaRadar Pipeline (Transient Cluster)

Bu klasör, GıdaRadar Silver→Gold pipeline'ını **AWS EMR** üzerinde tek seferlik
(_transient_) bir cluster'da çalıştırır: **aç → hesapla → kendiliğinden kapan**.
EMR sürekli açık kalmaz.

## Tek komut

```bash
cd infrastructure/emr
bash launch_demo.sh
```

`launch_demo.sh` sırayla: `deps.zip` üretir → kodu S3'e yükler → **pre-flight**
doğrulaması yapar (FAIL ise cluster açılmaz) → EMR cluster'ı başlatır. Cluster
`--auto-terminate` ile işi bitince otomatik kapanır.

## Dosyalar

| Dosya | İşlev |
|---|---|
| `launch_demo.sh` | Orkestrasyon: build → sync → preflight → create-cluster |
| `preflight.py` | Cluster'sız statik doğrulama (compile, deps.zip, steps.json, S3) |
| `build_deps.py` | `processing/silver/utils/` → `deps.zip` paketler |
| `steps.json` | EMR step tanımları (smoke + 9 pipeline step) |
| `install_libs.sh` | Bootstrap — her node'a Python kütüphaneleri kurar |
| `deps.zip` | Üretilen artefakt (`build_deps.py` çıktısı) |

## Doğrulama — 3 katman

EMR'da yaşanan hataların hiçbiri Spark mantığında değil, dağıtım katmanındaydı.
Bu üç katman o katmanı cluster açmadan / ucuza doğrular:

1. **Mantık zaten test edildi** — scriptler EC2'da (Spark local mode) çalışıp tüm
   Silver/Gold tablolarını üretti. Dönüşümler doğru.
2. **Pre-flight** (`preflight.py`, $0, cluster yok) — paketleme / S3 yolu / step
   format hatalarını yakalar. `launch_demo.sh` cluster açmadan ÖNCE çalıştırır;
   FAIL → durur, bir kuruş harcanmaz. Tek başına da çalışır:
   `python preflight.py --no-s3` (yalnızca yerel kontroller).
3. **Smoke step** (~$0.10, ~3 dk) — 9 ağır step'ten önce `silver_joined --debug-day`
   (yazmayan, tek gün) çalışır; cluster + paketleme + S3 erişimini uçtan uca
   kanıtlar. Fail ederse cluster `TERMINATE_CLUSTER` ile anında kapanır.

## Pipeline (steps.json)

| # | Step | Açıklama |
|---|---|---|
| 0 | smoke-silver-joined | `--debug-day` — yazmaz, doğrular. Fail → cluster kapanır |
| 1 | silver-joined | market + hal → `silver/market_hal_joined` (trunk) |
| 2 | gdelt-silver | `bronze/gdelt` → `silver/gdelt_daily` |
| 3-9 | 7 Gold analizi | daily_margin, price_inequality, rockets_feathers, shock_propagation, news_price_corr, prophet_forecast, macro_price_corr |

Step 1-9 `ActionOnFailure=CONTINUE` — biri patlasa diğerleri çalışır, cluster yine
kapanır. Veri kapsamı: **1 yıllık demo subset** (2025-05-20 → 2026-05-20).

## İzleme

```bash
aws emr list-steps --cluster-id <id> --query 'Steps[*].[Name,Status.State]' --output table
aws emr describe-cluster --cluster-id <id> --query 'Cluster.Status.State' --output text
```

İş bitince cluster state = `TERMINATED`. Loglar: `s3://s3-bbuckett/emr-logs/<cluster-id>/`.

## Maliyet

4× m5.xlarge (1 master + 3 core), ~30-45 dk → yaklaşık **1 USD / çalıştırma**.
`--auto-terminate` sayesinde cluster boşta para yakmaz.

## Neden EC2'da çalışıp EMR'da patlıyordu?

Hatalar Spark mantığında değil, EMR dağıtım katmanındaydı:

| Sorun | Kök neden | Çözüm |
|---|---|---|
| `utils` import bulunamadı | cluster-mode tek `.py` indirir | `deps.zip` + `--py-files` |
| `s3a` vs `s3` şeması | EC2 → s3a, EMR → EMRFS s3 | `ON_EMR` env değişkeni → `_S3_PREFIX` |
| "spark-submit does not exist" | EMR `Type:Spark` onu kendi ekler | Args'tan çıkarıldı |
| Bootstrap fail | Python 3.7 / pip RECORD | emr-7.2.0 + `--ignore-installed` |
| HDFS DataStreamer timeout (port 9866) | spark-submit, Spark jar'larını HDFS staging'e yüklerken master→datanode bağlanamıyor | `spark.yarn.jars=local:` + `spark.yarn.stagingDir=s3://` — submission HDFS'i hiç kullanmaz |

## Sorun giderme

- **Pre-flight FAIL** → çıktıdaki sorunu düzelt, `launch_demo.sh`'i tekrar çalıştır.
  Cluster açılmamıştır, ücret yok.
- **Smoke step (0) FAILED** → cluster kapandı. YARN log:
  `s3://s3-bbuckett/emr-logs/<id>/containers/`. Genelde girdi tablosu eksik veya
  gerçek kod hatası — 9 boş step çalışmadan yakalandı.
- **Bir Gold step FAILED, diğerleri COMPLETED** → `CONTINUE` ile beklenen davranış;
  o analizin çıktısı boş kalır, gerisi tamamlanır.
- **Cluster `WAITING`'de kaldı** → olmamalı (`--auto-terminate` var). Olursa:
  `aws emr terminate-clusters --cluster-ids <id>`.
