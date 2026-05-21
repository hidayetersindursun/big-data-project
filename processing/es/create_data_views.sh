#!/bin/bash
# Kibana data view'lerini oluştur — index_to_es sonrası çalıştır.
# Her dashboard için uygun time field ile ayrı data view.

KIBANA="${KIBANA_HOST:-http://localhost:5601}"

create_dv() {
  local title="$1"
  local name="$2"
  local time_field="$3"
  echo "=== Data view: $name (time: ${time_field:-yok}) ==="
  local body
  if [ -n "$time_field" ]; then
    body=$(cat <<EOF
{
  "data_view": {
    "title": "$title",
    "name": "$name",
    "timeFieldName": "$time_field"
  }
}
EOF
)
  else
    body=$(cat <<EOF
{
  "data_view": {
    "title": "$title",
    "name": "$name"
  }
}
EOF
)
  fi
  curl -s -X POST "$KIBANA/api/data_views/data_view" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$body" | head -200
  echo ""
}

create_dv "gidaradar_daily_margin"          "Daily Margin"        "date"
create_dv "gidaradar_price_inequality_hal"  "Price Inequality (Hal)"   "date"
create_dv "gidaradar_price_inequality_market" "Price Inequality (Market)" "date"
create_dv "gidaradar_rockets_feathers"      "Rockets & Feathers"  ""
create_dv "gidaradar_shocks"                "Shock Propagation"   "event_date"
create_dv "gidaradar_forecast"              "Price Forecast"      "date"
create_dv "gidaradar_macro_corr"            "Macro Correlation"   ""
create_dv "gidaradar_*"                     "GidaRadar (All)"     "date"

echo "=== Listeleme ==="
curl -s "$KIBANA/api/data_views" -H "kbn-xsrf: true" | head -200
