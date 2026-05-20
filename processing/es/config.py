"""ES bağlantı ayarları — .env veya env değişkenlerinden okur."""

import os
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ES_HOST = os.environ.get("ES_HOST", "http://localhost:9200")
ES_USER = os.environ.get("ES_USER")
ES_PASSWORD = os.environ.get("ES_PASSWORD")
ES_VERIFY_CERTS = os.environ.get("ES_VERIFY_CERTS", "false").lower() == "true"
ES_BULK_BATCH = int(os.environ.get("ES_BULK_BATCH", "5000"))
ES_TIMEOUT = int(os.environ.get("ES_TIMEOUT", "120"))


def get_es_client():
    from elasticsearch import Elasticsearch
    kwargs = {
        "hosts": [ES_HOST],
        "request_timeout": ES_TIMEOUT,
        "verify_certs": ES_VERIFY_CERTS,
    }
    if ES_USER and ES_PASSWORD:
        kwargs["basic_auth"] = (ES_USER, ES_PASSWORD)
    return Elasticsearch(**kwargs)
