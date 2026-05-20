#!/bin/bash
# EMR bootstrap script - her node'da çalışır, Python kütüphanelerini kurar.
# S3'e koy: aws s3 cp install_libs.sh s3://s3-bbuckett/bootstrap/install_libs.sh
set -euo pipefail

sudo python3 -m pip install --upgrade pip
sudo python3 -m pip install \
  elasticsearch \
  prophet \
  statsmodels \
  scipy \
  python-Levenshtein \
  python-dotenv \
  anthropic
