#!/usr/bin/env python3
"""
Build seven live demo flows in NiFi via REST — one per project data source —
each a minimal:

    GenerateFlowFile (realistic synthetic JSON)
          │  success
          ▼
    PublishKafka_2_6  →  dedicated raw_* topic

This mirrors the full project topology (see HW_NiFi_Kafka.md §1.4) so that every
Kafka topic has live data and the NiFi canvas tells the whole story.

Run AFTER infrastructure/setup.sh. Idempotent — deletes and recreates every
`*_demo_flow` process group it creates.

For production, replace the GenerateFlowFile processors with their real
counterparts (InvokeHTTP, ExecuteStreamCommand, ListS3) — the topology and
Kafka contract stay identical.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

NIFI = os.environ.get("NIFI", "http://localhost:8080/nifi-api")

# ---------------------------------------------------------------------------
# 7 sources — matches docker-setup.md §3 + HW_NiFi_Kafka.md §1.4
# Each entry defines: process-group name, target Kafka topic, generator period,
# and a NiFi-expression-language JSON payload that mirrors the real schema.
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "pg": "market_demo_flow",
        "topic": "raw_market_prices",
        "period": "200 ms",
        "payload": (
            '{"productId":"${random():mod(10000):toString()}",'
            '"productName":"Domates Sofralık",'
            '"depotId":"dep-${random():mod(200):toString()}",'
            '"district":"Kadıköy","city":"İstanbul","category":"Sebze",'
            '"price":${random():mod(5000):toNumber():divide(100)},'
            '"currency":"TRY",'
            '"observedAt":"${now():format(\'yyyy-MM-dd HH:mm:ss\')}"}'
        ),
    },
    {
        "pg": "hal_demo_flow",
        "topic": "raw_hal_prices",
        "period": "300 ms",
        "payload": (
            '{"source":"ibb_hal","kategori":"Sebze",'
            '"urun":"Domates Sofralık","birim":"Kg",'
            '"en_dusuk":${random():mod(3000):toNumber():divide(100)},'
            '"en_yuksek":${random():mod(4000):toNumber():divide(100):plus(10)},'
            '"tarih":"${now():format(\'yyyy-MM-dd\')}"}'
        ),
    },
    {
        "pg": "weather_demo_flow",
        "topic": "raw_weather",
        "period": "250 ms",
        "payload": (
            '{"source":"open_meteo",'
            '"lat":36.8969,"lon":30.7133,"region":"Antalya",'
            '"temperature_2m":${random():mod(400):toNumber():divide(10):minus(5)},'
            '"precipitation":${random():mod(50):toNumber():divide(10)},'
            '"soil_moisture":${random():mod(100):toNumber():divide(100)},'
            '"observedAt":"${now():format(\'yyyy-MM-dd HH:mm:ss\')}"}'
        ),
    },
    {
        "pg": "gdelt_demo_flow",
        "topic": "raw_gdelt",
        "period": "400 ms",
        "payload": (
            '{"source":"gdelt",'
            '"globalEventId":"${random():mod(99999999):toString()}",'
            '"theme":"AGRICULTURE_FOOD",'
            '"location":"Turkey","tone":${random():mod(200):toNumber():divide(10):minus(10)},'
            '"sourceUrl":"https://example.tr/haber/${random():mod(10000):toString()}",'
            '"eventTime":"${now():format(\'yyyy-MM-dd HH:mm:ss\')}"}'
        ),
    },
    {
        "pg": "epias_demo_flow",
        "topic": "raw_epias",
        "period": "250 ms",
        "payload": (
            '{"source":"epias",'
            '"dataset":"price_and_cost",'
            '"hour":"${now():format(\'HH:00\')}",'
            '"mcp":${random():mod(500000):toNumber():divide(100)},'
            '"smp":${random():mod(500000):toNumber():divide(100)},'
            '"wap":${random():mod(500000):toNumber():divide(100)},'
            '"timestamp":"${now():format(\'yyyy-MM-dd HH:mm:ss\')}"}'
        ),
    },
    {
        "pg": "tcmb_demo_flow",
        "topic": "raw_tcmb",
        "period": "500 ms",
        "payload": (
            '{"source":"tcmb_evds",'
            '"series":"TP.DK.USD.A.YTL","seriesName":"usd_try_alis",'
            '"value":${random():mod(500):toNumber():divide(10):plus(30)},'
            '"date":"${now():format(\'yyyy-MM-dd\')}"}'
        ),
    },
    {
        "pg": "akaryakit_demo_flow",
        "topic": "raw_akaryakit",
        "period": "300 ms",
        "payload": (
            '{"source":"epdk",'
            '"il":"İstanbul","urun":"Benzin",'
            '"fiyat":${random():mod(1000):toNumber():divide(10):plus(40)},'
            '"birim":"TL/L",'
            '"tarih":"${now():format(\'yyyy-MM-dd\')}"}'
        ),
    },
]


# ---------------------------------------------------------------------------
# tiny REST helper
# ---------------------------------------------------------------------------
def req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        f"{NIFI}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as f:
            txt = f.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP {e.code} {method} {path}\n{e.read().decode()[:400]}\n")
        raise


def log(msg): print(f"[demo] {msg}", flush=True)


# ---------------------------------------------------------------------------
# build one Gen → PublishKafka flow inside its own process group
# ---------------------------------------------------------------------------
def build_source(root_id: str, *, pg: str, topic: str, period: str,
                 payload: str, position: tuple[float, float]) -> None:
    root = req("GET", "/flow/process-groups/root")
    # idempotent delete
    for existing in root["processGroupFlow"]["flow"]["processGroups"]:
        if existing["component"]["name"] == pg:
            pid = existing["id"]
            try:
                req("PUT", f"/flow/process-groups/{pid}",
                    {"id": pid, "state": "STOPPED",
                     "disconnectedNodeAcknowledged": False})
            except Exception:
                pass
            time.sleep(0.5)
            try:
                req("POST",
                    f"/process-groups/{pid}/empty-all-connections-requests", {})
            except Exception:
                pass
            for _ in range(5):
                time.sleep(0.8)
                cur = req("GET", f"/process-groups/{pid}")
                ver = cur["revision"]["version"]
                try:
                    req("DELETE", f"/process-groups/{pid}?version={ver}")
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 409:
                        continue
                    raise
            break

    # 1. create PG
    x, y = position
    pgrp = req("POST", f"/process-groups/{root_id}/process-groups", {
        "revision": {"version": 0},
        "component": {"name": pg, "position": {"x": x, "y": y}},
    })
    pgid = pgrp["id"]

    # 2. GenerateFlowFile
    gen = req("POST", f"/process-groups/{pgid}/processors", {
        "revision": {"version": 0},
        "component": {
            "name": f"GenerateFlowFile_{topic}",
            "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
            "position": {"x": 50.0, "y": 50.0},
            "config": {
                "schedulingPeriod": period,
                "schedulingStrategy": "TIMER_DRIVEN",
                "properties": {
                    "File Size": "0B",
                    "Batch Size": "5",
                    "Data Format": "Text",
                    "Unique FlowFiles": "false",
                    "generate-ff-custom-text": payload,
                },
            },
        },
    })
    gen_id = gen["id"]

    # 3. PublishKafka_2_6 with both relationships auto-terminated
    pub = req("POST", f"/process-groups/{pgid}/processors", {
        "revision": {"version": 0},
        "component": {
            "name": f"PublishKafka_{topic}",
            "type": "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
            "position": {"x": 500.0, "y": 50.0},
            "config": {
                "autoTerminatedRelationships": ["success", "failure"],
                "properties": {
                    "bootstrap.servers": "kafka:9092",
                    "topic": topic,
                    "acks": "all",
                    "use-transactions": "false",
                    "max.request.size": "1 MB",
                    "compression.type": "none",
                },
            },
        },
    })
    pub_id = pub["id"]

    # Belt-and-suspenders auto-term re-PUT
    for _ in range(5):
        cur = req("GET", f"/processors/{pub_id}")
        auto = {r["name"] for r in cur["component"].get("relationships", [])
                if r.get("autoTerminate")}
        if {"success", "failure"} <= auto:
            break
        req("PUT", f"/processors/{pub_id}", {
            "revision": cur["revision"],
            "component": {
                "id": pub_id,
                "config": {"autoTerminatedRelationships":
                           ["success", "failure"]},
            },
        })
        time.sleep(0.5)

    # 4. connect gen -> pub
    req("POST", f"/process-groups/{pgid}/connections", {
        "revision": {"version": 0},
        "component": {
            "source": {"id": gen_id, "groupId": pgid, "type": "PROCESSOR"},
            "destination": {"id": pub_id, "groupId": pgid, "type": "PROCESSOR"},
            "selectedRelationships": ["success"],
            "backPressureObjectThreshold": 10000,
            "backPressureDataSizeThreshold": "1 GB",
        },
    })

    # 5. start everything in the PG
    req("PUT", f"/flow/process-groups/{pgid}", {
        "id": pgid, "state": "RUNNING",
        "disconnectedNodeAcknowledged": False,
    })
    log(f"{pg:24} → topic {topic}  ({period})  ✓ running")


def main() -> None:
    root = req("GET", "/flow/process-groups/root")
    root_id = root["processGroupFlow"]["id"]
    log(f"root PG: {root_id}")

    # lay process groups out in a grid so the canvas is readable
    cols = 3
    col_w = 500.0
    row_h = 250.0
    for i, src in enumerate(SOURCES):
        x = 100.0 + (i % cols) * col_w
        y = 100.0 + (i // cols) * row_h
        build_source(root_id, position=(x, y), **src)

    print()
    print(f"  ✓ {len(SOURCES)} flows live — open http://localhost:8080/nifi")
    print(f"  ✓ each PG publishes to its raw_* Kafka topic")
    print(f"  ✓ verify all topics receive data:")
    print(f"      for t in raw_market_prices raw_hal_prices raw_weather \\")
    print(f"              raw_gdelt raw_epias raw_tcmb raw_akaryakit; do")
    print(f"        echo \"--- $t ---\"")
    print(f"        docker exec kafka kafka-run-class kafka.tools.GetOffsetShell \\")
    print(f"            --broker-list kafka:9092 --topic $t")
    print(f"      done")


if __name__ == "__main__":
    main()
