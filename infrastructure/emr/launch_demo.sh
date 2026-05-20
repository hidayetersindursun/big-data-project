#!/bin/bash
# EMR cluster spin up + Silver→Gold pipeline + auto-terminate.
#
# Önkoşullar:
#   1. AWS CLI kurulu ve `aws configure` ile credentials ayarlı.
#   2. EC2 default rolleri var: aws emr create-default-roles
#   3. processing/ klasörü S3'e yüklenmiş:
#        aws s3 sync processing/ s3://s3-bbuckett/code/processing/ --exclude '*.pyc' --exclude '__pycache__/*'
#   4. install_libs.sh yüklü:
#        aws s3 cp infrastructure/emr/install_libs.sh s3://s3-bbuckett/bootstrap/install_libs.sh
#   5. Mevcut Silver tabloları S3'te var (yoksa önce processing/silver/*.py'ı çalıştır).
#
# Sunum cümlesi: "40 GB Bronze veri 4× m5.xlarge node'da 20 dakikada işleniyor."
set -euo pipefail

REGION="${AWS_REGION:-eu-central-1}"
BUCKET="${BUCKET:-s3-bbuckett}"
CLUSTER_NAME="${CLUSTER_NAME:-GidaRadar-Demo-$(date +%Y%m%d-%H%M)}"
RELEASE="emr-6.15.0"
LOG_URI="s3://${BUCKET}/emr-logs/"
KEY_NAME="${EMR_KEY_NAME:-azmi-yagli-h23}"

# Cluster boyutu — sunum için 1 master + 3 core önerilir
MASTER_TYPE="${MASTER_TYPE:-m5.xlarge}"
CORE_TYPE="${CORE_TYPE:-m5.xlarge}"
CORE_COUNT="${CORE_COUNT:-3}"

echo "=== Code'u S3'e senkronize et ==="
aws s3 sync ../../processing/ s3://${BUCKET}/code/processing/ \
  --region "${REGION}" \
  --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".pytest_cache/*"

aws s3 cp install_libs.sh s3://${BUCKET}/bootstrap/install_libs.sh \
  --region "${REGION}"

echo ""
echo "=== EMR cluster spin up ==="
aws emr create-cluster \
  --name "${CLUSTER_NAME}" \
  --release-label "${RELEASE}" \
  --applications Name=Spark Name=Hadoop \
  --ec2-attributes "KeyName=${KEY_NAME}" \
  --instance-groups \
    "InstanceGroupType=MASTER,InstanceCount=1,InstanceType=${MASTER_TYPE}" \
    "InstanceGroupType=CORE,InstanceCount=${CORE_COUNT},InstanceType=${CORE_TYPE}" \
  --bootstrap-actions \
    "Path=s3://${BUCKET}/bootstrap/install_libs.sh,Name=install-libs" \
  --steps file://steps.json \
  --auto-terminate \
  --use-default-roles \
  --log-uri "${LOG_URI}" \
  --region "${REGION}" \
  --configurations '[{"Classification":"spark","Properties":{"maximizeResourceAllocation":"true"}}]' \
  --query 'ClusterId' \
  --output text

echo ""
echo "Cluster ayağa kalkıyor (~3-5 dk). 'aws emr describe-cluster --cluster-id <id>' ile takip et."
echo "Beklenen toplam wall-clock (1y subset): 18-22 dk."
echo ""
echo "Sunum sırasında durum takibi:"
echo "  watch -n 30 \"aws emr list-steps --cluster-id <id> --query 'Steps[].[Name,Status.State]' --output table\""
