#!/bin/bash
# EMR bootstrap — her node'da çalışır.
# Yalnızca EMR pipeline step'lerinin (silver_joined, gdelt_silver, 6 Gold)
# ihtiyaç duyduğu Python kütüphaneleri kurulur.
# elasticsearch / python-Levenshtein / anthropic EMR'da KULLANILMAZ
# (index_to_es ve entity resolution EC2'da çalışır) — bootstrap'ı hafif tut.
#
# S3'e koy: aws s3 cp install_libs.sh s3://s3-bbuckett/bootstrap/install_libs.sh
set -euxo pipefail

# pip rpm ile kurulu → düz --upgrade "Cannot uninstall, RECORD not found" verir.
# --ignore-installed eski pip'i silmeden üzerine kurar; başarısızlığı tolere et.
sudo python3 -m pip install --upgrade --ignore-installed pip || true

sudo python3 -m pip install \
  pandas \
  statsmodels \
  scipy \
  prophet \
  python-dotenv
