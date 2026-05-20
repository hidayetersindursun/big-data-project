#!/bin/bash
# EC2'da (Amazon Linux 2023 veya Ubuntu 22.04) ES + Kibana ayağa kaldır.
#
# Kullanım:
#   chmod +x bootstrap_es.sh
#   ./bootstrap_es.sh
#
# Gereksinimler:
#   - sudo erişimi
#   - en az 8 GB RAM (t3.large önerilir)
#   - port 9200 ve 5601 security group'ta açık
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 1. ES için sysctl ayarı (vm.max_map_count=262144) ==="
sudo sysctl -w vm.max_map_count=262144
if ! grep -q "vm.max_map_count=262144" /etc/sysctl.conf; then
  echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
fi

echo "=== 2. Docker kurulumu (eğer yoksa) ==="
if ! command -v docker &>/dev/null; then
  if [ -f /etc/amazon-linux-release ] || [ -f /etc/system-release ]; then
    sudo dnf install -y docker
  elif command -v apt-get &>/dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin
  else
    echo "HATA: paket yöneticisi bulunamadı"
    exit 1
  fi
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" || true
fi

echo "=== 3. docker compose plugin kontrolü ==="
if ! docker compose version &>/dev/null; then
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y docker-compose-plugin
  else
    DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
      -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
  fi
fi

echo "=== 4. ES + Kibana ayağa kaldır ==="
sudo docker compose -f docker-compose.yml up -d

echo "=== 5. ES health bekleniyor ==="
for i in {1..40}; do
  if curl -fs http://localhost:9200/_cluster/health &>/dev/null; then
    echo "  ES hazır."
    break
  fi
  echo "  bekliyor... ($i/40)"
  sleep 5
done

echo "=== 6. Kibana hazır mı kontrol ==="
for i in {1..40}; do
  status=$(curl -fs http://localhost:5601/api/status 2>/dev/null | grep -oP '(?<="level":")[^"]+' | head -1 || true)
  if [ "$status" = "available" ]; then
    echo "  Kibana hazır."
    break
  fi
  echo "  bekliyor... ($i/40)"
  sleep 5
done

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")
echo ""
echo "==============================================="
echo "  Elasticsearch : http://${PUBLIC_IP}:9200"
echo "  Kibana        : http://${PUBLIC_IP}:5601"
echo "==============================================="
echo ""
echo "Sonraki adım:"
echo "  1. .env'de ES_HOST=http://${PUBLIC_IP}:9200 ayarla (veya VPN'le localhost)"
echo "  2. python processing/es/index_to_es.py --recreate"
echo "  3. Kibana'da index pattern oluştur: gidaradar_*"
