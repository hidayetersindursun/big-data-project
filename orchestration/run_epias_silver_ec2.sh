#!/bin/bash
# EC2'da epias_silver'ı 4 grup halinde çalıştırır.
# Her grup ayrı spark-submit → her grup yeni JVM → RAM birikmesi sıfırlanır
# (EC2 8GB; ES+Kibana ~4GB kullandığı için tek seferde 26 dataset GC baskısı yapar).
#
# Grup A → Gold (macro_price_corr) için ZORUNLU.
# Grup B/C/D → Silver tamlığı için; Gold'a girmez, zaman kısıtında atlanabilir.
#
# Kullanım:
#   nohup bash orchestration/run_epias_silver_ec2.sh > /tmp/run_epias.log 2>&1 &
#   # yalnızca Grup A:
#   nohup bash orchestration/run_epias_silver_ec2.sh A > /tmp/run_epias.log 2>&1 &

cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; source .env; set +a

SUBMIT="$HOME/spark/bin/spark-submit \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  --driver-memory 3g"

GROUP_A="price_and_cost,mcp_smp_imbalance,zero_balance_adjustment,natural_gas_spot"
GROUP_B="real_time_generation,realtime_consumption,consumption,kgup,injection_quantity"
GROUP_C="renewable_realtime_generation,renewable_injection_quantity,wind_forecast,renewable_unit_cost,renewable_total_cost,dam_volume,intraday_market,primary_frequency_capacity,secondary_frequency_capacity,transmission_loss_factor"
GROUP_D="dam_daily_level,dam_active_fullness,dam_active_volume,natural_gas_balancing,natural_gas_daily_transmission,planned_outages,unplanned_outages"

run_group() {
  label="$1"; datasets="$2"
  echo ""
  echo "=== EPIAS GRUP $label START $(date +%H:%M:%S) ==="
  $SUBMIT processing/silver/epias_silver.py --datasets "$datasets"
  rc=$?
  echo "=== EPIAS GRUP $label DONE rc=$rc $(date +%H:%M:%S) ==="
}

ONLY="${1:-ALL}"

case "$ONLY" in
  A) run_group A "$GROUP_A" ;;
  ALL)
    run_group A "$GROUP_A"
    run_group B "$GROUP_B"
    run_group C "$GROUP_C"
    run_group D "$GROUP_D"
    ;;
  *) echo "Kullanım: run_epias_silver_ec2.sh [A|ALL]"; exit 1 ;;
esac

echo ""
echo "=== EPIAS_SILVER_COMPLETE $(date +%H:%M:%S) ==="
