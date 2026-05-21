#!/bin/bash
# EMR bootstrap — her node'da (master + core) çalışır.
# Yalnızca EMR pipeline step'lerinin (silver_joined, gdelt_silver, 7 Gold)
# ihtiyaç duyduğu Python kütüphaneleri kurulur.
# elasticsearch / python-Levenshtein / anthropic EMR'da KULLANILMAZ
# (index_to_es ve entity resolution EC2'da çalışır) — bootstrap'ı hafif tut.
#
# S3'e koy: aws s3 cp install_libs.sh s3://s3-bbuckett/bootstrap/install_libs.sh
set -euxo pipefail

# pip rpm ile kurulu → düz --upgrade "Cannot uninstall, RECORD not found" verir.
# --ignore-installed eski pip'i silmeden üzerine kurar; başarısızlığı tolere et.
sudo python3 -m pip install --upgrade --ignore-installed pip || true

# Çekirdek paketler — Gold step'lerinin çoğu bunlara bağlı.
# Bu satır fail ederse bootstrap (ve dolayısıyla cluster) HAKLI olarak durur.
# Sürümler pin'li + --prefer-binary: pip resolver backtracking'i ve kaynaktan
# derlemeyi engeller → manylinux wheel garantisi, daha hızlı bootstrap.
# pyarrow ZORUNLU: shock/rockets/prophet step'leri applyInPandas (cogroup/groupBy
# pandas UDF) kullanıyor — bu Arrow olmadan çalışmaz; executor'larda kurulu olmalı.
sudo python3 -m pip install --prefer-binary \
  "pandas==2.2.3" \
  "numpy==1.26.4" \
  "scipy==1.13.1" \
  "statsmodels==0.14.4" \
  "pyarrow==15.0.2" \
  "python-dotenv==1.0.1"

# prophet ağır + yavaş kurulum (cmdstanpy/stan). Kurulamasa bile cluster açılsın:
# yalnızca step-8 (prophet_forecast) etkilenir, o da ActionOnFailure=CONTINUE.
sudo python3 -m pip install --prefer-binary "prophet==1.1.6" || true
