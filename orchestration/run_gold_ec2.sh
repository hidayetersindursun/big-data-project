#!/bin/bash
# EC2'da gdelt_silver + Gold scriptlerini sıralı çalıştırır (spark-submit, local mode).
# silver_joined.py'ın ÖNCEDEN çalışmış olması gerekir (silver/market_hal_joined).
#
# Kullanım:
#   nohup bash orchestration/run_gold_ec2.sh > /tmp/run_gold.log 2>&1 &
#
# Demo dönemi: 2025-05-20 → 2026-05-20 (1 yıl subset, EC2 RAM kısıtı).
# pandemic_gap ATLANDI: 2019 baseline + 2021-2024 verisi demo subset'te yok
#   → full backfill gerektirir, EMR turunda çalıştırılır.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; source .env; set +a

SUBMIT="$HOME/spark/bin/spark-submit \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  --driver-memory 3g"
DEMO="--start-date 2025-05-20 --end-date 2026-05-20"

run() {
  name="$1"; shift
  echo ""
  echo "=== STEP $name START $(date +%H:%M:%S) ==="
  $SUBMIT "processing/$name" "$@"
  rc=$?
  echo "=== STEP $name DONE rc=$rc $(date +%H:%M:%S) ==="
}

# NOT: gdelt_silver (full GDELT ~150M satır) + news_price_corr EC2 t3.large
#      için fazla ağır — EMR turunda çalıştırılır. Bu batch yalnızca EC2'da
#      makul süren 6 Gold analizini 1 yıl demo subset ile koşar.
run gold/daily_margin.py $DEMO
run gold/price_inequality.py $DEMO
run gold/rockets_feathers.py $DEMO
run gold/shock_propagation.py $DEMO
run gold/prophet_forecast.py
run gold/macro_price_corr.py $DEMO

echo ""
echo "=== PIPELINE_COMPLETE $(date +%H:%M:%S) ==="
