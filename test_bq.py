from google.cloud import bigquery
import json, os

creds_file = os.path.join(os.path.dirname(__file__), "gcp-credentials.json")
with open(creds_file) as f:
    creds_data = json.load(f)

project_id = creds_data.get("project_id")
print("Project:", project_id)

client = bigquery.Client(project=project_id)
query = """
SELECT COUNT(*) as cnt
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME = TIMESTAMP("2026-05-10")
"""
result = list(client.query(query).result())
print("Test OK, satir:", result[0].cnt)
