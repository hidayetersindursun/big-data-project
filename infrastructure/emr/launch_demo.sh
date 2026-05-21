#!/bin/bash
# GidaRadar EMR — TRANSIENT cluster: dogrula -> hesapla -> kendiliginden kapan.
#
# Akis (tek komut):
#   1. build_deps.py   -> deps.zip (processing/silver/utils/ paketi)
#   2. aws s3 sync     -> processing/ kodunu S3'e
#   3. aws s3 cp       -> deps.zip + install_libs.sh S3'e
#   4. preflight.py    -> cluster ACMADAN dogrulama; FAIL ise BURADA durur (ucret yok)
#   5. create-cluster  -> bootstrap -> smoke step -> 9 step -> AUTO-TERMINATE
#
# Onkosullar:
#   - AWS CLI kurulu + `aws configure` yapilmis
#   - `aws emr create-default-roles` bir kez calistirilmis
#   - Girdi Silver/Bronze tablolari S3'te (preflight kontrol eder)
#
# infrastructure/emr/ ICINDEN calistir:
#   cd infrastructure/emr && bash launch_demo.sh
#
# TRANSIENT cluster: --auto-terminate ile is bitince KENDILIGINDEN kapanir;
# cluster acik kalamaz. Smoke step (step-0) fail ederse cluster ANINDA kapanir.
set -euo pipefail

REGION="${AWS_REGION:-eu-central-1}"
BUCKET="${BUCKET:-s3-bbuckett}"
CLUSTER_NAME="${CLUSTER_NAME:-GidaRadar-Demo-$(date +%Y%m%d-%H%M)}"
RELEASE="emr-7.2.0"   # Spark 3.5.1 + Python 3.9
LOG_URI="s3://${BUCKET}/emr-logs/"
KEY_NAME="${EMR_KEY_NAME:-azmi-yagli-h23}"

# Cluster boyutu — 1 master + 3 core.
# Core node'lar m5.2xlarge (8 vCPU / 32 GB): CPU-bound silver/gold adimlari hizlanir;
# cluster-mode'da driver (AM) core node'da kostugu icin toPandas-agir Gold adimlari
# (shock/prophet/rockets/macro) daha buyuk driver bellegi de kazanir.
# Master hafif is yapar -> m5.xlarge yeterli.
MASTER_TYPE="${MASTER_TYPE:-m5.xlarge}"
CORE_TYPE="${CORE_TYPE:-m5.2xlarge}"
CORE_COUNT="${CORE_COUNT:-3}"

# Spark config:
#   maximizeResourceAllocation -> her node icin tek buyuk executor.
#   spark.yarn.stagingDir=s3   -> job conf + spark libs HDFS yerine S3'e stage edilir;
#                                 submission HDFS'e dokunmaz.
# NOT: spark.yarn.jars=local:/usr/lib/spark/jars/* ayari KALDIRILDI. O ayar EMR'in
# AM/executor classpath'ine EMRFS jar'ini (com.amazon.ws.emr.hadoop.fs.EmrFileSystem)
# eklemesini bypass ediyordu -> AM s3:// yolunu cozemeyip exitCode 13 ile cokuyordu.
# Onceki master->datanode:9866 / master->NM:8041 ConnectTimeout'larin sebebi ayriydi:
# ElasticMapReduce-master SG egress'i Hadoop portlarini kapatmisti; SG'ye master->core
# tum-port egress eklenerek cozuldu.
EMR_CONFIG="[{\"Classification\":\"spark\",\"Properties\":{\"maximizeResourceAllocation\":\"true\"}},{\"Classification\":\"spark-defaults\",\"Properties\":{\"spark.yarn.stagingDir\":\"s3://${BUCKET}/spark-staging/\"}}]"

# python / python3 — hangisi varsa onu kullan
PY="${PYTHON:-}"
if [ -z "${PY}" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python
  else echo "HATA: python bulunamadi (python3/python)"; exit 1
  fi
fi

echo "=== 1/4  deps.zip olustur ==="
"${PY}" build_deps.py

echo ""
echo "=== 2/4  Kodu S3'e senkronize et ==="
aws s3 sync ../../processing/ "s3://${BUCKET}/code/processing/" \
  --region "${REGION}" \
  --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".pytest_cache/*"
aws s3 cp deps.zip "s3://${BUCKET}/code/deps.zip" --region "${REGION}"
aws s3 cp install_libs.sh "s3://${BUCKET}/bootstrap/install_libs.sh" --region "${REGION}"

echo ""
echo "=== 3/4  Pre-flight dogrulama (cluster ACILMADAN) ==="
if ! "${PY}" preflight.py; then
  echo ""
  echo "PRE-FLIGHT FAIL — cluster ACILMADI, ucret yok."
  echo "Yukaridaki sorunlari duzelt, sonra bu scripti tekrar calistir."
  exit 1
fi

echo ""
echo "=== 4/4  EMR transient cluster spin up ==="
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
  --steps file://steps.json \
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
echo "TRANSIENT cluster: bootstrap -> smoke step -> 9 step -> KENDILIGINDEN TERMINATE."
echo "  - --auto-terminate: is bitince cluster otomatik kapanir, acik kalamaz."
echo "  - smoke step (0) fail ederse cluster ANINDA kapanir (9 bos step calismaz)."
echo ""
echo "Durum takibi:"
echo "  aws emr list-steps --cluster-id ${CLUSTER_ID} --region ${REGION} --query 'Steps[*].[Name,Status.State]' --output table"
echo "  aws emr describe-cluster --cluster-id ${CLUSTER_ID} --region ${REGION} --query 'Cluster.Status.State' --output text"
echo ""
echo "Loglar:  ${LOG_URI}${CLUSTER_ID}/"
echo "Acil kapatma (gerekirse):  aws emr terminate-clusters --cluster-ids ${CLUSTER_ID} --region ${REGION}"
