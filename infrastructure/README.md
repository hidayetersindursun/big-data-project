# Infrastructure — Local Dev Stack (Docker)

One-command reproducible stack for the Turkey Food Supply Chain project.
Runs everything needed for the NiFi → Kafka homework (HW_NiFi_Kafka.md):
Zookeeper, Kafka, Kafka-UI, Apache NiFi, MinIO (S3).

---

## Prerequisites

Install **Docker** and **Docker Compose v2** (the `docker compose` subcommand).

| OS | How |
|---|---|
| macOS / Windows | [Docker Desktop](https://www.docker.com/products/docker-desktop/) — includes compose v2 |
| Ubuntu / Debian | `sudo apt-get install -y docker.io docker-compose` |
| RHEL / Fedora | `sudo dnf install -y docker docker-compose` |

Give your user permission (Linux only, once):

```bash
sudo usermod -aG docker $USER   # then log out + back in
```

Check:

```bash
docker --version          # ≥ 20
docker compose version    # (v2) or: docker-compose --version
```

Minimum machine: **8 GB RAM**, **10 GB free disk**. NiFi alone wants ~2 GB heap.

---

## Quick start (the whole HW stack in one command)

```bash
cd infrastructure
./setup.sh
```

That's it. The script:

1. Picks `docker compose` vs `docker-compose` automatically.
2. Uses `sudo` only if your user isn't in the docker group.
3. Pulls images (~3 GB first time, cached after).
4. Brings up 6 services.
5. Creates the 7 Kafka topics (`raw_market_prices`, `raw_hal_prices`, `raw_weather`, `raw_gdelt`, `raw_epias`, `raw_tcmb`, `raw_akaryakit`).
6. Creates the 3 MinIO buckets (`bronze`, `silver`, `gold`).
7. Waits until Kafka + NiFi are actually ready.
8. Prints the URLs.

### URLs

All services bind on `0.0.0.0` inside their containers, so they're reachable
from the host **and** from any remote client that can reach this machine's IP.

| Service | URL (local dev) | URL (remote / EC2) | Credentials |
|---|---|---|---|
| **NiFi UI** | http://localhost:8080/nifi | http://`$HOST_IP`:8080/nifi | no login (HTTP mode) |
| **Kafka UI** | http://localhost:8090 | http://`$HOST_IP`:8090 | — |
| **MinIO Console** | http://localhost:9001 | http://`$HOST_IP`:9001 | `admin` / `admin12345` |
| Kafka broker (external) | `localhost:29092` | `$HOST_IP:29092` | — |
| Kafka broker (docker net) | `kafka:9092` | — | — |

`$HOST_IP` is read from `infrastructure/.env`, which `setup.sh` auto-creates
on first run by detecting your public IP. Override it by editing `.env`:

```bash
# infrastructure/.env
HOST_IP=3.72.105.132                                     # your EC2 public IP
HOST_DNS=ec2-3-72-105-132.eu-central-1.compute.amazonaws.com
```

Then `docker compose down && ./setup.sh` so Kafka re-advertises the new IP
and NiFi reloads the proxy-host whitelist.

**Firewall / Security Group:** on EC2, open inbound TCP **8080, 8090, 9001,
29092** (and optionally 2181, 9000) from your laptop's IP.

### What runs out of the box

`setup.sh` auto-builds **seven live demo flows** inside NiFi via REST — one
per project data source. Each is a minimal `GenerateFlowFile → PublishKafka_2_6`
pipeline publishing realistic JSON to its own `raw_*` Kafka topic:

| Process Group | Cadence | Topic | Sample payload |
|---|---|---|---|
| `market_demo_flow`    | 2 s | `raw_market_prices` | `productId, productName, depotId, district, city, price, ...` |
| `hal_demo_flow`       | 5 s | `raw_hal_prices`    | `kategori, urun, birim, en_dusuk, en_yuksek, tarih` |
| `weather_demo_flow`   | 3 s | `raw_weather`       | `lat, lon, region, temperature_2m, precipitation, soil_moisture` |
| `gdelt_demo_flow`     | 4 s | `raw_gdelt`         | `globalEventId, theme, location, tone, sourceUrl` |
| `epias_demo_flow`     | 3 s | `raw_epias`         | `dataset, hour, mcp, smp, wap, timestamp` |
| `tcmb_demo_flow`      | 6 s | `raw_tcmb`          | `series, seriesName, value, date` |
| `akaryakit_demo_flow` | 5 s | `raw_akaryakit`     | `il, urun, fiyat, birim, tarih` |

Open `http://$HOST_IP:8080/nifi` and you'll see all 7 process groups on the canvas
with live throughput counters. Open Kafka-UI (`http://$HOST_IP:8090`) and every
`raw_*` topic has growing offsets.

Schemas deliberately mirror the real scrapers in `ingestion/` — for production,
swap `GenerateFlowFile` for its real counterpart (`InvokeHTTP` for
marketfiyati/TCMB/EPİAŞ/Open-Meteo/Akaryakıt, `ExecuteStreamCommand` for the
Hal Selenium/curl_cffi scrapers, `ListS3`+`FetchS3Object` for GDELT) — the PG
name, Kafka topic, and downstream contract stay identical.

Tail any topic:

```bash
docker exec kafka kafka-console-consumer \
    --bootstrap-server kafka:9092 \
    --topic raw_market_prices --from-beginning --max-messages 5
```

If Python3 isn't on the host, `setup.sh` just skips the demo-build step;
re-run it any time with:

```bash
python3 nifi_build_demo_flow.py
```

### Import the full 7-source flow template (optional)

The homework-scale design flow is packaged as a template at
`infrastructure/nifi_flow_template.xml` and mounted read-only into the NiFi
container at `/opt/nifi/templates/nifi_flow_template.xml`.

1. Open http://localhost:8080/nifi.
2. In the **Operate palette** (left sidebar), click **Upload Template**, browse to `infrastructure/nifi_flow_template.xml`, click Upload.
3. Drag the **Template** icon (stack of papers, 8th in top palette) onto canvas, pick `turkey_food_supply_chain_ingest`.
4. Seven process groups appear — one per data source (`market`, `hal`, `epias`, `tcmb`, `gdelt`, `weather`, `akaryakit`).
5. Right-click canvas → **Start** to run the flow. (Note: the template references vendor APIs and secrets — individual processors will show warnings until you fill them in.)

---

## Teardown

```bash
./teardown.sh          # stop containers, keep volumes (fast restart later)
./teardown.sh --wipe   # stop AND delete volumes (fresh state next time)
```

Equivalent raw command: `docker compose down [-v]`.

---

## Fresh reset

```bash
./setup.sh --clean
```

Wipes all volumes first (NiFi flow, Kafka logs, MinIO data) and brings the
stack back up from scratch — useful if something got into a weird state.

---

## What's running

```
┌────────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐
│ zookeeper  │◄──│  kafka   │──►│ kafka-ui │   │   nifi    │──► publishes to kafka
│ :2181      │   │ :9092    │   │ :8090    │   │ :8080     │
└────────────┘   │ :29092   │   └──────────┘   └───────────┘
                 └──────────┘
                       ▲            ┌───────────┐
                       │            │   minio   │
               kafka-setup          │ :9000/:9001│
               creates topics       └───────────┘
                                          ▲
                                          │
                                     minio-setup
                                     creates bronze/silver/gold
```

All services share the `bdp` bridge network so they resolve each other by
hostname (`kafka:9092`, `minio:9000`, etc.).

Named volumes persist data across restarts:
`zk-data`, `kafka-data`, `nifi-{conf,content,db,flowfile,provenance,state,logs}`,
`minio-data`.

---

## Common issues

**Port already in use (8080 / 9092 / 2181).** Another service is bound on
your host. Find it: `sudo ss -tlnp | grep ':8080\|:9092\|:2181'` and stop it,
or change the port on the left side of the `ports:` mapping in
`docker-compose.yml`.

**Mac: "docker compose up" hangs on NiFi startup.** NiFi needs ~90 s on first
boot. If the health check still fails after 3 min, check
`docker logs nifi | tail -50` — usually a memory issue; raise Docker Desktop's
memory limit to 6 GB.

**NiFi page shows "System Error" / can't load.** Hard-refresh the browser;
the JS bundle sometimes caches mid-startup. If it persists:
`docker restart nifi`.

**Kafka topics missing after `setup.sh`.** Look at the one-shot
initializer: `docker logs kafka-setup`. Re-run: `docker compose up -d kafka-setup`.

**Want to produce a test message from your laptop:**

```bash
echo '{"ping":"hello"}' | docker exec -i kafka \
    kafka-console-producer --bootstrap-server kafka:9092 --topic raw_market_prices
docker exec kafka kafka-console-consumer \
    --bootstrap-server kafka:9092 --topic raw_market_prices \
    --from-beginning --max-messages 1 --timeout-ms 5000
```

---

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions |
| `setup.sh` | One-command bring-up + topic/bucket init + health wait |
| `teardown.sh` | Stop (optionally wipe volumes) |
| `nifi_flow_template.xml` | Importable NiFi 1.x flow template — 7 process groups |
