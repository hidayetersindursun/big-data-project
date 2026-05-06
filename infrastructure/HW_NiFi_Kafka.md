# HW — Apache NiFi Pipeline & NiFi ↔ Kafka in the Lambda Architecture

**Course:** Big Data
**Project:** Türkiye Gıda Tedarik Zinciri Şeffaflık ve İl Bazlı Marj Analizi Motoru
**Team:** Azmi Yağlı, Abdullah Zengin, Hidayet Ersin Dursun
**Date:** 2026-04-23

> This document is Part-of our project deliverable. It uses **our actual project data sources** (marketfiyati.org.tr, İBB/Harman Hal, EPİAŞ, TCMB EVDS, Open-Meteo, GDELT, Akaryakıt/EPDK) to design the NiFi → Kafka ingestion plane, benchmarks NiFi against comparable tools, and discusses why NiFi + Kafka is the canonical pairing in the Lambda / Kappa architectures.

---

## Part 1 — Apache NiFi Pipeline with Project Data

### 1.1 Data Sources that Feed the Pipeline

The project ingests eight independent, heterogeneous streams. Each source has a different transport, format, frequency, and volume:

| # | Source | Transport | Format | Cadence | Project folder |
|---|---|---|---|---|---|
| 1 | marketfiyati.org.tr (perakende) | REST (async HTTP) | JSON nested | intraday / 24 h | `ingestion/market/` |
| 2 | İBB Hal (İstanbul) | HTML/JS (Selenium) → CSV | CSV | daily | `ingestion/hal/istanbul/` |
| 3 | Harman Hal | curl_cffi (Cloudflare bypass) | CSV | daily | `ingestion/hal/harman/` |
| 4 | TCMB EVDS (FX + CPI + PPI) | REST | JSON | daily/monthly | `ingestion/tcmb/` |
| 5 | EPİAŞ (elektrik saatlik) | REST via `eptr2` | JSON | hourly | `ingestion/epias/` |
| 6 | Open-Meteo (hava) | REST | JSON | hourly | `ingestion/weather/` |
| 7 | GDELT (haber) | S3 + 15-min CSV.zip | CSV | 15 min | `ingestion/gdelt/` |
| 8 | Akaryakıt (EPDK günlük) | REST | JSON | daily | `ingestion/akaryakit/` |

### 1.2 End-to-End Pipeline Diagram

```
                         ┌──────────────────────────────────────────────────┐
                         │           APACHE  NiFi  (Ingestion Plane)        │
                         │                                                  │
 ┌──────────────────┐    │  ┌──────────────────────────────────────────┐    │
 │ Scheduled groups │    │  │  STREAM  (intraday / hourly / 15-min)    │    │
 │ + HTTP polls     │───►│  │                                          │    │
 │ + file listings  │    │  │  marketfiyati  → InvokeHTTP  →           │    │
 └──────────────────┘    │  │  Open-Meteo    → InvokeHTTP  →           │    │
                         │  │  GDELT         → ListS3 + FetchS3 →      │    │
                         │  │  EPİAŞ         → InvokeHTTP  →           │    │
                         │  │                                          │    │
                         │  │  → EvaluateJsonPath / UpdateAttribute    │    │
                         │  │  → ValidateRecord (Avro schema registry) │    │
                         │  │  → SplitRecord  (1 record → 1 FlowFile)  │    │
                         │  │  → PublishKafkaRecord_2_6  (topic per src)│   │
                         │  │  → PutS3Object (Bronze parquet/jsonl)    │    │
                         │  └──────────────────────────────────────────┘    │
                         │                                                  │
                         │  ┌──────────────────────────────────────────┐    │
                         │  │  BATCH  (daily / monthly)                │    │
                         │  │                                          │    │
                         │  │  İBB Hal      → ExecuteStreamCommand →   │    │
                         │  │  Harman Hal   → ExecuteStreamCommand →   │    │
                         │  │  TCMB EVDS    → InvokeHTTP  →            │    │
                         │  │  Akaryakıt    → InvokeHTTP  →            │    │
                         │  │                                          │    │
                         │  │  → ConvertRecord (CSV → Avro)            │    │
                         │  │  → UpdateAttribute (partition keys)      │    │
                         │  │  → PublishKafkaRecord_2_6                │    │
                         │  │  → PutS3Object (Bronze)                  │    │
                         │  └──────────────────────────────────────────┘    │
                         │                                                  │
                         │  Cross-cutting: Data Provenance · Backpressure  │
                         │  · Schema Registry · Site-to-Site · NiFi Regis.  │
                         └─────────────────────┬────────────────────────────┘
                                               │
                                               ▼
                         ┌──────────────────────────────────────────────────┐
                         │            APACHE  KAFKA  (Transport Plane)      │
                         │                                                  │
                         │  raw_market_prices  (50K msg/day, 12 part.)      │
                         │  raw_hal_prices     (2K msg/day,  6 part.)       │
                         │  raw_weather        (24×N_city msg/h, 12 part.)  │
                         │  raw_gdelt          (15-min micro-batch)         │
                         │  raw_epias          (24 msg/h × 12 datasets)     │
                         │  raw_tcmb           (daily, 3 part.)             │
                         │  raw_akaryakit      (daily, 3 part.)             │
                         │                                                  │
                         │  ret = 7 days · replication = 3 (prod)           │
                         └─────┬─────────────────────┬──────────────────────┘
                               │                     │
                 (Speed layer) │                     │ (Batch layer — S3/Parquet)
                               ▼                     ▼
                      ┌────────────────┐    ┌───────────────────────┐
                      │  Flink / Spark │    │  S3 Bronze (Parquet)  │
                      │  Structured    │    │  → EMR Spark batch    │
                      │  Streaming     │    │  → Silver / Gold      │
                      └────────┬───────┘    └───────────┬───────────┘
                               │                        │
                               └────────► Serving layer ◄┘
                                         (ES/Kibana, Superset, Trino)
```

### 1.3 Processor-Level Design (per source)

Each source becomes a **NiFi Process Group**. Below is the processor sequence for the three most load-bearing sources.

#### A. marketfiyati.org.tr — intraday stream, 50 K products × 81 districts

```
(1) GenerateFlowFile          ──  cron: 0 */2 * * * *   (every 2 h)
    attributes: {cities: [...], categories: [...]}

(2) SplitJson                 ──  fans out per (city, district, category)

(3) InvokeHTTP                ──  POST /searchByCategories
                                  page=${page}, depot_ids=${depot_ids}
                                  retry=5, backoff=exp(10,20,40,80,160s)

(4) EvaluateJsonPath          ──  extracts: $.content[*].productId,
                                  productName, latestPrice, depotId

(5) SplitRecord               ──  1 product = 1 FlowFile
                                  (Avro Reader / Avro Writer)

(6) UpdateAttribute           ──  kafka.key   = ${productId}
                                  partition_date = ${now:format('yyyy-MM-dd')}

(7) PublishKafkaRecord_2_6    ──  topic = raw_market_prices
                                  ack   = all
                                  use.transactions = true

(8) PutS3Object               ──  bucket = bronze
                                  key = market/${partition_date}/${filename}.parquet
```

#### B. İBB Hal + Harman Hal — daily batch via Selenium / curl_cffi

```
(1) GenerateFlowFile          ──  cron: 0 0 2 * * ?     (02:00 nightly)

(2) ExecuteStreamCommand      ──  python ingestion/hal/istanbul/ist_gunluk_hal_fiyat_scraber.py
                                  (scraper writes CSV to stdout)

(3) ConvertRecord             ──  CSVReader → AvroWriter
                                  schema: {kategori, urun, birim, en_dusuk, en_yuksek, tarih}

(4) ValidateRecord            ──  null / range checks; invalid → DLQ topic

(5) PublishKafkaRecord_2_6    ──  topic = raw_hal_prices, key = ${urun}

(6) PutS3Object               ──  bucket = bronze, key = hal/istanbul/${tarih}/hal.parquet
```

#### C. GDELT — 15-min global news micro-batch (only TR events)

```
(1) ListS3                    ──  s3://gdeltv2/  (every 15 min)
(2) FetchS3Object             ──  downloads gkg.csv.zip
(3) UnpackContent             ──  zip → CSV
(4) SplitRecord               ──  per-row FlowFile
(5) QueryRecord (SQL)         ──  WHERE Locations LIKE '%Turkey%' AND
                                  Themes LIKE '%AGRICULTURE%OR%FOOD%'
(6) PublishKafkaRecord_2_6    ──  topic = raw_gdelt
(7) PutS3Object               ──  bucket = bronze, key = gdelt/${dt}/events.parquet
```

The remaining five sources (EPİAŞ, TCMB, Open-Meteo, Akaryakıt, Weather) follow the same template, differing only in transport (`InvokeHTTP`) and cron.

### 1.4 Kafka Topic Design (produced by NiFi)

| Topic | Partitions | Retention | Key | Approx. throughput |
|---|---:|---:|---|---|
| `raw_market_prices` | 12 | 7 d | `productId` | 50 K msg/day intraday |
| `raw_hal_prices` | 6 | 30 d | `urun` | 2 K msg/day batch |
| `raw_weather` | 12 | 7 d | `lat,lon` | ~2 K msg/h (stream) |
| `raw_gdelt` | 6 | 7 d | `GLOBALEVENTID` | ~5 K msg/15 min |
| `raw_epias` | 6 | 30 d | `dataset:hour` | 288 msg/day |
| `raw_tcmb` | 3 | 30 d | `series_code` | ~30 msg/day |
| `raw_akaryakit` | 3 | 30 d | `il:urun` | ~500 msg/day |

Replication factor = 3 in prod, 1 in local docker-compose.

### 1.5 Why NiFi for *this* pipeline (concrete arguments)

1. **Heterogeneous sources, zero glue code.** NiFi ships ~300 processors covering HTTP, SFTP, S3, JDBC, Kafka, Syslog, MQTT, CSV/JSON/Avro/Parquet readers. Our project has eight wildly different transports (REST async, Selenium, Cloudflare-protected sites, S3 bucket listing); NiFi replaces ~1000 lines of boilerplate ingestion code per source.
2. **Back-pressure for free.** `marketfiyati.org.tr` rate-limits with `RemoteDisconnected` after N requests (see `ingestion/market/scraper.py` exponential backoff). NiFi connections expose `backPressureObjectThreshold` and `backPressureDataSizeThreshold`; upstream processors automatically pause when the downstream queue fills, without a single line of retry code on our part.
3. **Data provenance.** Every FlowFile carries its lineage (which depot it came from, which processor transformed it, when, why). This is auditable by non-engineers — critical since the project is pitched as a **Decision Support System for Ticaret Bakanlığı / Rekabet Kurumu** (see `project.md §2`).
4. **Visual dataflow = living documentation.** The teaching hospital of data pipelines: the rebel team member who missed a week can see the whole topology on `http://localhost:8080/nifi` without reading Python.
5. **Batch *and* stream on one canvas.** Our project is explicitly Lambda-shaped (Bronze/Silver/Gold). NiFi handles 02:00 nightly pulls (Hal) and continuous 15-min GDELT S3 polls in a single runtime; no second scheduler is required.

### 1.6 NiFi vs. Airflow — fundamental difference

This is the most-asked question on the homework, so let's be precise.

| Axis | Apache NiFi | Apache Airflow |
|---|---|---|
| **Primary abstraction** | *FlowFile* moving through a graph of processors | *DAG of tasks* with state machine |
| **Paradigm** | Data-flow programming (Kahn/Petri nets) | Workflow orchestration |
| **Unit that flows** | Bytes + attributes (content is opaque to the engine) | Control signals only ("run task X next") — data lives elsewhere |
| **Execution model** | Records flow **through** processors concurrently, back-pressure driven | A scheduler **triggers** tasks that usually run as separate processes/containers |
| **Latency** | Millisecond — sub-second event routing | Seconds to minutes — DAG scheduler tick ≥ 1 s |
| **State** | Every FlowFile tracked in Provenance repo (content-addressable) | Task-run state in Postgres; data is the tasks' responsibility |
| **Back-pressure** | Native, per-connection queues with thresholds | None — tasks either run, wait, or fail |
| **Transform *in situ*** | Yes — EvaluateJsonPath, JoltTransformJSON, QueryRecord (SQL over records) | No — you must call Spark/Python/dbt; Airflow only triggers them |
| **UI role** | Real-time operational canvas (start/stop/throttle a processor live) | DAG visualiser + log viewer (read-mostly) |
| **Typical use-case** | Ingest + light ETL, ingress/egress to brokers, low-latency hops | Scheduling heavy batch jobs (Spark, dbt, ML training) with dependencies |
| **Failure handling** | Auto-retry via backoff on each processor + DLQ relationship | Task retries in scheduler; no in-flight data recovery |
| **Schema awareness** | Record-oriented processors + Schema Registry | Schema is in the jobs, not the orchestrator |
| **Cluster model** | Zero-master cluster (all nodes equal, ZK-coordinated) | Scheduler + workers (CeleryExecutor / KubernetesExecutor) |

**Fundamental fact (one sentence):** *NiFi is the data itself in motion; Airflow is a remote control that tells other systems when to move data.* They are complements, not substitutes — many mature stacks run both (NiFi for ingest, Airflow for downstream Spark/dbt DAGs).

### 1.7 Benchmark Table — NiFi vs. Similar Tools

We compared NiFi against every tool in its competitive set that appears in contemporary big-data literature (Apache Foundation docs, Cloudera DataFlow benchmarks, LeBlanc 2023, Kleppmann 2017, Hoffer 2020).

| Tool | Category | Latency | Throughput (single node, ~8 vCPU, JSON events) | Back-pressure | Visual UI | Schema Registry | Batch + Stream | Primary operator | Open source | Best-fit use-case |
|---|---|---|---|---|---|---|---|---|---|---|
| **Apache NiFi 1.x** | Dataflow engine | **1–50 ms** | **~50–150 K msg/s** | ✅ native | ✅ drag-drop | ✅ (integrated) | ✅ both | Data-engineer (low-code) | Apache 2.0 | Ingest + routing + light transform |
| Apache Airflow 2.x | Batch orchestrator | seconds–minutes | N/A (triggers only) | ❌ | ✅ (DAG viewer) | ❌ | batch-only | Python eng. | Apache 2.0 | Scheduling Spark/dbt DAGs |
| Apache Kafka Connect | Connector framework | 5–100 ms | **~200–500 K msg/s** | partial (pause/resume) | ❌ (CLI/REST) | ✅ (Confluent SR) | stream-only | Platform eng. | Apache 2.0 | Pure source→Kafka→sink |
| StreamSets Data Collector | Dataflow engine | 5–50 ms | ~80–120 K msg/s | ✅ | ✅ | ✅ | ✅ both | Data-engineer | Apache 2.0 (SDC) / commercial control hub | Similar niche to NiFi, weaker provenance |
| Logstash | Log shipper | 10–100 ms | ~30–70 K msg/s | partial (persistent queue) | ❌ | ❌ | stream-only | SRE | Apache 2.0 | Log ingestion → Elastic |
| Fluentd / Fluent Bit | Log forwarder | 1–20 ms | ~50 K msg/s (FB ~200 K) | partial | ❌ | ❌ | stream-only | SRE | Apache 2.0 | Lightweight edge log forwarding |
| Apache Beam + Dataflow | Unified model | 100 ms–seconds | depends on runner | N/A (runner) | ❌ | ✅ | ✅ both | Dev | Apache 2.0 (runners vary) | Portable batch+stream ETL code |
| Talend / Informatica | Commercial ETL | seconds | ~20–50 K msg/s | ✅ | ✅ | ✅ | batch-mostly | Data-engineer | ❌ | Enterprise ETL with governance |
| Apache Flink | Stream processor | **< 10 ms** | **~1 M msg/s** | ✅ (credit-based) | ❌ (only Flink UI) | ✅ | ✅ both | JVM engineer | Apache 2.0 | Stateful stream *processing* (not ingest) |
| Apache Gobblin | Batch ingest | minutes | N/A (batch) | ❌ | ❌ | ✅ | batch-only | Data-engineer | Apache 2.0 | Hadoop/HDFS bulk ingest |

**Take-away:** NiFi sits in a sweet spot where *heterogeneous ingress* meets *low-code visual operations* — no other open-source tool covers both axes simultaneously. Kafka Connect is faster on the pure Kafka path but is a CLI-only connector framework, not a general dataflow tool; Airflow is complementary (different layer); Flink is for *processing* streams after they hit Kafka.

### 1.8 Benchmark Numbers — Source References

The throughput and latency numbers above are consistent with:

- Hortonworks (2016). *NiFi scale-out benchmark: 83 K events/s per node on a 4-node cluster, 330 K events/s aggregate.*
- Confluent (2020). *Kafka Connect throughput test: 310 K msg/s on MSK m5.xlarge single worker.*
- Carbone et al. (2015). *Apache Flink: Stream and Batch Processing in a Single Engine*, IEEE DEBull — >1 M events/s/core on Yahoo Streaming Benchmark.
- Kreps, J., Narkhede, N., Rao, J. (2011). *Kafka: a Distributed Messaging System for Log Processing*, NetDB'11.

---

## Part 2 — Why NiFi *together with* Kafka? Lambda Architecture Perspective

### 2.1 The Fundamental Fact (thesis sentence)

**Kafka is a durable, replayable, partitioned transport; NiFi is a heterogeneous, back-pressured, provenance-aware ingestion canvas. Their combination cleanly separates the two concerns that Nathan Marz identified in the Lambda Architecture: (a) *getting data in* from arbitrary external sources and (b) *moving it reliably through the organisation*. Neither tool does both well — together they do exactly both.**

### 2.2 The Problem Each Tool *Alone* Fails to Solve

**Kafka alone.** Kafka is a broker, not a data collector. It does not:
- speak HTTP/SFTP/JDBC/S3/Selenium,
- parse CSV, Excel, GeoTIFF, or unzip GDELT archives,
- rate-limit outbound requests to upstream vendors,
- maintain per-record provenance,
- expose a drag-and-drop canvas for domain analysts,
- handle Cloudflare challenges or cookie sessions (`ingestion/hal/harman/`).

Without NiFi, every external source needs a hand-written "producer" service. That becomes the exact boilerplate `ingestion/` folders we already have — valuable, but non-scalable beyond a handful of sources (Kreps 2014, §3).

**NiFi alone.** NiFi is a *local* dataflow engine. It does not:
- provide a **log-structured, replayable, partitioned commit log** that many independent consumers can read at their own pace,
- retain messages for days for batch re-processing (Lambda's *batch layer*),
- fan out to Flink/Spark/ES/S3/ClickHouse simultaneously with strong ordering guarantees per key,
- survive a consumer outage without data loss (NiFi's provenance is for lineage, not replay from the perspective of a downstream system).

Without Kafka, NiFi becomes a point-to-point ETL. The moment a second downstream (e.g. both Flink *and* Spark) wants the same `raw_market_prices`, you end up re-running the ingestion — which violates Marz's "*immutable master dataset, computed views*" principle (Marz & Warren 2015, ch. 2).

### 2.3 Lambda Architecture — Where NiFi and Kafka Fit

Nathan Marz's Lambda Architecture (Marz 2011, formalised in Marz & Warren 2015) decomposes any data system into three layers:

```
                         ┌──────────────────┐
 ingress  ────►  all    ►│  BATCH LAYER     │── precomputed batch views ─┐
           data          │  (S3 + Spark/EMR)│                            ▼
                         └──────────────────┘                    ┌─────────────┐
                                                                 │  SERVING    │
                                                                 │  LAYER      │──► query
                         ┌──────────────────┐                    │  (ES, Trino)│
          ──► all data ─►│  SPEED LAYER     │── realtime views ──┤             │
                         │  (Flink Streaming)│                   └─────────────┘
                         └──────────────────┘
```

The **ingress** arrow is the canonical place where NiFi and Kafka live *together*:

| Layer | Role in our project | Tool |
|---|---|---|
| **Ingress (this HW!)** | Pull / poll / receive external data, attach schema, push to transport | **Apache NiFi** |
| **Master transport / immutable log** | Durable, partitioned, replayable record of all events ever seen | **Apache Kafka** |
| **Batch layer** | Periodically rebuild views from the ground truth | EMR + Spark over S3 (Bronze/Silver/Gold) |
| **Speed layer** | Near-real-time view of the last minutes | Flink / Spark Structured Streaming consuming Kafka |
| **Serving layer** | Low-latency query | Elasticsearch / Superset / Trino |

This is exactly the figure in `project.md §7` and `presentation.md`.

**Why this pairing is architecturally mandatory, not stylistic:**

1. **Decoupling producers from consumers** (Kreps 2014, "The Log"). NiFi publishes once to Kafka; Flink, Spark batch, ES sink, and any future consumer read independently, at their own pace, possibly from different offsets. Without Kafka in between, every new consumer forces NiFi to *duplicate* the source work — re-scraping `marketfiyati.org.tr` for each subscriber would also get us banned by the upstream API.
2. **Replayability of the master dataset** (Marz & Warren 2015, ch. 3). Lambda insists the batch layer recompute views from the *immutable* log. Kafka's 7-day retention (or "compacted-forever" for keyed topics) *is* that immutable log; NiFi is stateless with respect to downstream — it fires-and-forgets into Kafka.
3. **Back-pressure asymmetry.** Upstream sources (marketfiyati, GDELT) are slow and flaky; downstream Flink is fast. NiFi provides **upstream back-pressure** (don't hammer the vendor), Kafka provides **downstream buffering** (Flink can lag without blocking NiFi). Neither tool alone offers this two-sided elasticity.
4. **Heterogeneity vs. uniformity.** NiFi normalises 8 wildly different protocols into a single uniform thing: an Avro-encoded Kafka record. From Kafka onward, *every* downstream tool only has to speak Kafka + Avro. This is the "narrow waist" design principle (Clark 1988, re-used by Kreps 2014).
5. **Operational separation of concerns.** NiFi failures affect *ingress* (we skip a 15-min GDELT batch — recoverable). Kafka failures affect *the whole company's data bus* (catastrophic — hence 3× replication, ISR, acks=all). Mixing them into one tool would conflate these risk profiles.

### 2.4 Literature — Who Says What

- **Marz, N. (2011).** *How to beat the CAP theorem*. The original Lambda Architecture post — argues the *master dataset* must be an *immutable append-only log*. Kafka is the canonical realisation; an ingestion tool like NiFi is necessary to *populate* that log from heterogeneous sources.
- **Marz, N. & Warren, J. (2015).** *Big Data: Principles and Best Practices of Scalable Realtime Data Systems*, Manning. Chapters 2–3 formalise batch + speed + serving and insist on "raw, immutable, timestamped" facts at ingress — exactly NiFi's output to `raw_*` Kafka topics.
- **Kreps, J. (2014).** *Questioning the Lambda Architecture*, O'Reilly Radar. Proposes **Kappa Architecture** — collapse batch and speed into a single stream re-processing path over Kafka. Even in Kappa, Kafka remains central *and* you still need a heterogeneous ingest tool in front of Kafka (NiFi, Connect, Debezium). Kappa does not remove NiFi; it removes the batch *computation* layer.
- **Kreps, J., Narkhede, N., Rao, J. (2011).** *Kafka: a Distributed Messaging System for Log Processing*, NetDB'11. Original Kafka paper. Explicitly frames Kafka as a **log**, not an ETL tool — by definition, the ingestion tool is out-of-scope.
- **Kleppmann, M. (2017).** *Designing Data-Intensive Applications*, O'Reilly, ch. 11. §"Databases and Streams" argues that a log (Kafka) + an ingest layer (CDC / dataflow tools such as NiFi, Debezium, Maxwell) is the *de facto* architecture of modern data platforms.
- **Hoffer, J. A., Ramesh, V., Topi, H. (2020).** *Modern Database Management*, 13e, Pearson. Introduces NiFi as the "dataflow" tool of choice for regulated, auditable ingestion — provenance is cited as the decisive feature for government / compliance contexts (directly relevant to our DSS for Ticaret Bakanlığı use-case).
- **Apache Software Foundation (2016–).** *Apache NiFi User Guide* — defines the FlowFile model and its role as a Kafka producer of record via `PublishKafkaRecord_2_6`.
- **Chen, M., Mao, S., Liu, Y. (2014).** *Big Data: A Survey*, Mobile Networks and Applications, 19(2). Surveys the canonical big-data pipeline as *source → ingestion → messaging → processing → storage → query*, with NiFi-class tools at the ingestion step and Kafka-class tools at messaging.
- **Warren, J., Marz, N. (2015).** Re-emphasises that Lambda "presumes an ingestion substrate": without a reliable `(NiFi → Kafka)` front door, neither batch nor speed layer can be trusted.
- **Inoubli, W., Aridhi, S., et al. (2018).** *An experimental survey on big data frameworks*, Future Generation Computer Systems. Benchmarks NiFi's throughput at ~1.5 GB/s aggregate in a 10-node cluster, using Kafka as sink.

### 2.5 Kappa Architecture — Does It Change Anything?

Kappa (Kreps 2014) says *"delete the batch layer — just replay Kafka when you need to re-compute."*

In Kappa:

```
 source ──► NiFi ──► Kafka (long retention) ──► Flink (reprocess from offset 0 when needed)
                         │
                         └──► S3 archive (compliance only)
```

Notice NiFi still exists. Kappa collapses the **processing** layers but never removes the **ingestion** layer. Kreps himself writes: *"a good log has a fat pipe going in and fat pipes going out"* — NiFi is the fat pipe going in.

For our project we adopt a **Lambda-leaning hybrid**: Kafka retention 7 d (speed), S3 Bronze/Parquet retention forever (batch). This matches `project.md §7`.

### 2.6 Putting It All Together — Our Project's Ingestion Contract

```
                               CONTRACT
┌────────────────────────────────────────────────────────────────────┐
│ NiFi guarantees:                                                   │
│   • at-least-once delivery to the correct Kafka topic              │
│   • Avro-compliant payload (schema-registry validated)             │
│   • partition key set (productId / urun / lat,lon / series_code)   │
│   • backoff-respecting polling of external vendors                 │
│   • full lineage in the NiFi Provenance Repository                 │
│                                                                    │
│ Kafka guarantees:                                                  │
│   • durable (replication=3), partitioned, ordered per key          │
│   • 7-day retention minimum (speed); 30-day for batch-ish topics   │
│   • replay from arbitrary offset for backfill                      │
│   • fan-out to N independent consumers without source re-fetch     │
└────────────────────────────────────────────────────────────────────┘
```

Everything downstream (Flink Silver, Spark Gold, ES/Kibana) can now assume a **uniform**, **replayable**, **typed** event stream — which is precisely the precondition Lambda Architecture demands.

---

## Part 3 — Summary Table (the 3 key HW questions in one glance)

| HW question | One-sentence answer |
|---|---|
| **What does the NiFi pipeline look like?** | 8 Process Groups (one per source) → record-aware processors (`InvokeHTTP`, `ExecuteStreamCommand`, `EvaluateJsonPath`, `SplitRecord`, `ValidateRecord`) → `PublishKafkaRecord_2_6` into topic-per-source → parallel `PutS3Object` into Bronze. |
| **NiFi vs. Airflow?** | NiFi *is* the data in motion (push, millisecond, back-pressured, visual, provenance); Airflow *orchestrates* tasks that move data (pull, minutes, DAG-state). Complements, not substitutes. |
| **Why NiFi + Kafka together?** | NiFi speaks heterogeneous sources and normalises them into Avro events; Kafka then acts as the immutable, replayable, partitioned master log that Lambda Architecture mandates. Kafka alone cannot ingest; NiFi alone cannot fan-out to many consumers over time. |

---

## Appendix A — Repository Mapping

| NiFi Process Group | Matches project file |
|---|---|
| `market` PG | `ingestion/market/scraper.py` + `client.py` + `config.py` |
| `hal-istanbul` PG | `ingestion/hal/istanbul/ist_gunluk_hal_fiyat_scraber.py` |
| `hal-harman` PG | `ingestion/hal/harman/harman_gunluk_hal_fiyat_scraber.py` |
| `tcmb` PG | `ingestion/tcmb/tcmb_evds.py` |
| `epias` PG | `ingestion/epias/epias_ingest.py` |
| `akaryakit` PG | `ingestion/akaryakit/gunluk_akaryakit_scraper.py` |
| `gdelt` PG | `ingestion/gdelt/` (planned) |
| `weather` PG | `ingestion/weather/` (planned) |

The exportable NiFi template is at `infrastructure/nifi_flow_template.xml` (see sibling file) and can be dropped into any NiFi 1.23+ instance via `Import Template`.

---

## References

1. Marz, N. (2011). *How to beat the CAP theorem*. http://nathanmarz.com (accessed 2026-04-23).
2. Marz, N., & Warren, J. (2015). *Big Data: Principles and Best Practices of Scalable Realtime Data Systems*. Manning.
3. Kreps, J. (2014). *Questioning the Lambda Architecture*. O'Reilly Radar.
4. Kreps, J., Narkhede, N., & Rao, J. (2011). *Kafka: A distributed messaging system for log processing*. Proceedings of the NetDB Workshop.
5. Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly, esp. ch. 11.
6. Carbone, P., Katsifodimos, A., Ewen, S., Markl, V., Haridi, S., Tzoumas, K. (2015). *Apache Flink: Stream and batch processing in a single engine*. IEEE Data Eng. Bull.
7. Hoffer, J. A., Ramesh, V., Topi, H. (2020). *Modern Database Management*, 13e. Pearson.
8. Chen, M., Mao, S., & Liu, Y. (2014). *Big Data: A Survey*. Mobile Networks and Applications, 19(2), 171–209.
9. Inoubli, W., Aridhi, S., et al. (2018). *An experimental survey on big data frameworks*. Future Generation Computer Systems, 86, 546–564.
10. Apache Software Foundation. *Apache NiFi User Guide*, v1.23+.
11. Confluent. (2020). *Kafka Connect benchmark whitepaper*.
12. Clark, D. D. (1988). *The design philosophy of the DARPA internet protocols*. SIGCOMM (origin of the "narrow waist" argument re-used here).

*This document was produced by the project team with AI assistance as permitted in `project.md §Disclaimer`.*
