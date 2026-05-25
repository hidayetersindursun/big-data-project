#!/bin/bash
# GidaRadar EMR — TEK STEP: pandemic_gap.
# Demo run'da unutulan pandemic_gap Gold step'ini ayrı bir transient cluster ile
# koşturur. Küçük cluster (1 master + 1 core, m5.xlarge) — pandemic_gap hafif iş.
#
# Akış (launch_demo.sh'ın küçük varyantı):
#   1. build_deps.py  -> deps.zip
#   2. aws s3 sync    -> processing/ kodunu S3'e
#   3. aws s3 cp      -> deps.zip + install_libs.sh S3'e
#   4. create-cluster -> bootstrap -> pandemic_gap step -> AUTO-TERMINATE
#
# Preflight ATLANDI: steps_pandemic.json sadece market_hal_joined okur (silver_joined
# çıktısı zaten S3'te); diğer girdileri kontrol etmeye gerek yok.
#
# Çalıştır:  cd infrastructure/emr && bash launch_pandemic.sh
set -euo pipefail

REGION="${AWS_REGION:-eu-central-1}"
BUCKET="${BUCKET:-s3-bbuckett}"
CLUSTER_NAME="${CLUSTER_NAME:-GidaRadar-PandemicGap-$(date +%Y%m%d-%H%M)}"
RELEASE="emr-7.2.0"
LOG_URI="s3://${BUCKET}/emr-logs/"
KEY_NAME="${EMR_KEY_NAME:-azmi-yagli-h23}"

# Küçük cluster — pandemic_gap = groupBy + avg + join, ~750 MB parquet.
MASTER_TYPE="${MASTER_TYPE:-m5.xlarge}"
CORE_TYPE="${CORE_TYPE:-m5.xlarge}"
CORE_COUNT="${CORE_COUNT:-1}"

EMR_CONFIG="[{\"Classification\":\"spark\",\"Properties\":{\"maximizeResourceAllocation\":\"true\"}},{\"Classification\":\"spark-defaults\",\"Properties\":{\"spark.yarn.stagingDir\":\"s3://${BUCKET}/spark-staging/\"}}]"

PY="${PYTHON:-}"
if [ -z "${PY}" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python
  else echo "HATA: python bulunamadi"; exit 1
  fi
fi

echo "=== 1/3  deps.zip olustur ==="
"${PY}" build_deps.py

echo ""
echo "=== 2/3  Kodu S3'e senkronize et ==="
aws s3 sync ../../processing/ "s3://${BUCKET}/code/processing/" \
  --region "${REGION}" \
  --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".pytest_cache/*"
aws s3 cp deps.zip "s3://${BUCKET}/code/deps.zip" --region "${REGION}"
aws s3 cp install_libs.sh "s3://${BUCKET}/bootstrap/install_libs.sh" --region "${REGION}"

echo ""
echo "=== 3/3  EMR transient cluster (1 master + ${CORE_COUNT} core) ==="
CLUSTER_ID=$(aws emr create-cluster \
  --name "${CLUSTER_NAME}" \
  --release-label "${RELEASE}" \
  --applications Name=Spark Name=Hadoop \
  --ec2-attributes "KeyName=${KEY_NAME}" \
  --instance-groups \
    "InstanceGroupType=MASTER,InstanceCount=1,InstanceType=${MASTER_TYPE}" \
    "InstanceGroupType=CORE,InstanceCount=${CORE_COUNT},InstanceType=${CORE_TYPE}" \
  --bootstrap-actions \
    "Path=s3://${BUCKET}/bootstrap/install_libs.sh,Name=install-libs" \
  --steps file://steps_pandemic.json \
  --use-default-roles \
  --auto-terminate \
  --log-uri "${LOG_URI}" \
  --region "${REGION}" \
  --configurations "${EMR_CONFIG}" \
  --query 'ClusterId' \
  --output text)

echo ""
echo "Cluster: ${CLUSTER_ID}  (${CLUSTER_NAME})"
echo ""
echo "TRANSIENT: bootstrap -> 1 step -> KENDILIGINDEN TERMINATE."
echo ""
echo "Durum takibi:"
echo "  aws emr list-steps --cluster-id ${CLUSTER_ID} --region ${REGION} --query 'Steps[*].[Name,Status.State]' --output table"
echo "  aws emr describe-cluster --cluster-id ${CLUSTER_ID} --region ${REGION} --query 'Cluster.Status.State' --output text"
echo ""
echo "Loglar:  ${LOG_URI}${CLUSTER_ID}/"
echo "Acil kapatma:  aws emr terminate-clusters --cluster-ids ${CLUSTER_ID} --region ${REGION}"
echo ""
echo "${CLUSTER_ID}" > /tmp/pandemic_cluster_id.txt
echo "Cluster ID kaydedildi: /tmp/pandemic_cluster_id.txt"
