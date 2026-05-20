#!/bin/bash
# Lokal/EC2'dan tüm Silver → Gold → ES pipeline'ını ardışık çalıştır.
# EMR'a alternatif olarak küçük ölçekli ya da debug amaçlı.
#
# Kullanım:
#   ./orchestration/run_pipeline.sh                            # tam aralık
#   ./orchestration/run_pipeline.sh 2025-05-20 2026-05-20      # demo aralık
#   ./orchestration/run_pipeline.sh skip-silver                # silver atla, gold + es
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

START_DATE="${1:-}"
END_DATE="${2:-}"
SKIP_SILVER="${SKIP_SILVER:-false}"

if [ "${1:-}" = "skip-silver" ]; then
  SKIP_SILVER=true
  START_DATE=""
fi

DATE_ARGS=""
if [ -n "$START_DATE" ]; then
  DATE_ARGS="--start-date $START_DATE --end-date $END_DATE"
fi

if [ "$SKIP_SILVER" != "true" ]; then
  echo "=== 1. silver_joined ==="
  python processing/silver/silver_joined.py $DATE_ARGS

  echo "=== 2. gdelt_silver ==="
  python processing/silver/gdelt_silver.py --skip-articles
fi

echo "=== 3. gold/daily_margin ==="
python processing/gold/daily_margin.py $DATE_ARGS

echo "=== 4. gold/price_inequality ==="
python processing/gold/price_inequality.py $DATE_ARGS

echo "=== 5. gold/rockets_feathers ==="
python processing/gold/rockets_feathers.py $DATE_ARGS

echo "=== 6. gold/shock_propagation ==="
python processing/gold/shock_propagation.py $DATE_ARGS

echo "=== 7. gold/pandemic_gap ==="
python processing/gold/pandemic_gap.py

echo "=== 8. gold/news_price_corr ==="
python processing/gold/news_price_corr.py

echo "=== 9. gold/prophet_forecast ==="
python processing/gold/prophet_forecast.py

echo "=== 10. index_to_es ==="
python processing/es/index_to_es.py --recreate

echo ""
echo "=== Pipeline tamam ==="
