#  Fleet Intelligence

### Connected Vehicle Intelligence Platform

Fleet Intelligence is a real-time connected-vehicle intelligence platform that
ingests telemetry from simulated multi-OEM vehicle fleets, handles duplicate
and out-of-order events, detects vehicle incidents, calculates vehicle health,
supports semantic incident search, and converts high-risk vehicles into
actionable recovery cases.


---



#  Problem Statement

Connected vehicle fleets continuously generate telemetry from multiple OEM
systems. In a real fleet environment, telemetry can contain:

* Different OEM payload formats
* Duplicate events
* Out-of-order events
* High-volume telemetry
* Vehicle faults that require rapid detection
* Large volumes of historical incidents
* Manual recovery follow-up

The operational problem is not only receiving telemetry. The system must answer:

1. Which vehicles currently have problems?
2. What type of problem occurred?
3. How severe is the problem?
4. Can similar historical incidents be found using natural language?
5. Which vehicles should be prioritized for recovery?
6. Has a recovery agent been assigned?
7. Has the recovery case been resolved?

Fleet Intelligence addresses these requirements through one end-to-end pipeline.

---

# Solution

Fleet Intelligence combines:

* Large-scale vehicle simulation
* Redis Streams ingestion
* Real-time stream processing
* Duplicate and out-of-order detection
* Rule-based incident detection
* Vehicle health scoring
* PostgreSQL persistence
* FAISS semantic search
* FastAPI APIs with JWT authentication and search rate limiting
* Recovery risk scoring and recovery case management
* React dashboard

The simulator intentionally injects duplicate and out-of-order events so that
data-quality handling is demonstrated rather than assumed.

---

#  Key Features

## 100K Vehicle Simulator

* Up to 100,000 vehicles
* OEM A and OEM B telemetry formats
* Battery, engine temperature, speed, GPS, timestamp and sequence information
* Duplicate and out-of-order events
* One-time and continuous execution

Example 100K run:

```text
Vehicles:        100,000
Normal events:   100,000
Duplicates:        1,952
Out-of-order:      2,035
```

## Redis Streams Ingestion

Telemetry is published to the `telemetry_raw` stream and consumed by the
`telemetry_processors` consumer group. Redis Streams provides durable
buffering, consumer groups, pending-entry tracking, lag visibility and
replayable processing.

## Duplicate Detection

Events are identified by their event identity. Duplicates are detected before
they are processed as new telemetry, so they are not double-counted.

## Out-of-Order Detection

The processor compares ordering information and flags events that arrive out
of sequence. They are counted and tracked rather than silently ignored.

## OEM Payload Normalization

OEM A and OEM B use different telemetry formats. The processor maps them into
one canonical structure:

```text
vehicle, OEM, timestamp, GPS, speed, battery, temperature, sequence
```

---

#  Incident Detection

The current rule engine detects three incident types.

| Condition                       | Incident           | Severity |
| ------------------------------- | ------------------ | -------- |
| Battery < 20                    | `LOW_BATTERY`      | MEDIUM   |
| Temperature > 100               | `OVERHEATING`      | HIGH     |
| Temperature > 100 AND speed < 5 | `OVERHEATING_STOP` | CRITICAL |

The rules are deliberately explicit and explainable.

```text
Temperature = 105, Speed = 2   →   OVERHEATING_STOP (CRITICAL)
```

---

#  Vehicle Health Score

Each vehicle receives a health score from 0 to 100, reduced by:

* Low battery
* High engine temperature
* Overheating
* Overheating while stopped

The score is persisted in PostgreSQL and exposed through the API and dashboard.
It is a rule-based score, not a trained ML model.

---

# 📊 Analytics

**Fleet overview:** total vehicles, active vehicles, average health, average
battery, average temperature, total incidents, critical incidents.

**Incident analytics:** incidents by type, incidents by OEM, incidents by
hour, average temperature by OEM.

---

# Incident Escalation

Escalation uses a rolling time window per vehicle:

```text
0–1 incidents  →  NORMAL
2 incidents    →  ELEVATED
3+ incidents   →  ESCALATED
```

Repeated problems within a short period receive greater attention.

---

#  Top-K Problematic Vehicles

The most problematic vehicles are found with a min-heap of size K, giving
`O(n log K)` rather than sorting all vehicles. Incident severity contributes
to the problem score:

```text
CRITICAL → 3
HIGH     → 2
MEDIUM   → 1
```

---

# 🔎 Semantic Incident Search

Incident text is embedded with `sentence-transformers` (`all-MiniLM-L6-v2`)
and stored in a FAISS index.

Example query:

```text
vehicles overheating while stopped
```

Semantically related incidents are returned even when the exact words do not
match. The FAISS index is a derived data structure: rebuild it from the
PostgreSQL incident table whenever incident data changes significantly.

---

#  Recovery Operations

```text
Incident → Recovery Risk Score → Recovery Case → Assign Agent → Resolve
```

## Recovery Risk Score

Risk is calculated from accumulated incident severity.

|  Score | Risk Level | Priority  |
| -----: | ---------- | --------- |
| 81–100 | CRITICAL   | IMMEDIATE |
|  61–80 | HIGH       | URGENT    |
|  31–60 | MEDIUM     | NORMAL    |
|   0–30 | LOW        | LOW       |

These thresholds are design choices calibrated on synthetic data. They are not
presented as production-calibrated risk models.

## Recovery Case Lifecycle

```text
OPEN → ASSIGNED → RESOLVED
```

A case stores: case ID, vehicle, risk score, risk level, priority, status,
assigned agent, created timestamp and resolved timestamp.

---

#  Dashboard

The React dashboard provides:

* **Fleet Overview:** total and active vehicles, average health, battery, temperature
* **Incident Analytics:** incident counts, severity, critical incidents
* **Critical Vehicles:** vehicles requiring attention based on health and incident severity
* **Recovery Operations:** cases with risk score, priority, status and assigned agent; agents can be assigned directly from the interface

---

# Architecture

```text
                         ┌──────────────────────┐
                         │   Vehicle Simulator  │
                         │     100K Vehicles    │
                         │     OEM A / OEM B    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Redis Streams     │
                         │    telemetry_raw     │
                         └──────────┬───────────┘
                                    │
                              Consumer Group
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Stream Processor   │
                         │ • Normalize          │
                         │ • Deduplicate        │
                         │ • Order Check        │
                         │ • Incident Rules     │
                         │ • Health Score       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      PostgreSQL      │
                         │ • Vehicles           │
                         │ • Telemetry          │
                         │ • Incidents          │
                         │ • Recovery Cases     │
                         │ • Fleet / Driver     │
                         │ • Audit              │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │ • JWT Authentication │
                         │ • Analytics          │
                         │ • Search             │
                         │ • Recovery API       │
                         └───────┬───────┬──────┘
                                 │       │
                       ┌─────────┘       └─────────┐
                       ▼                           ▼
              ┌─────────────────┐        ┌─────────────────┐
              │      FAISS      │        │ React Dashboard │
              │ MiniLM vectors  │        │ Fleet Overview  │
              │ Incident Search │        │ Incidents       │
              └─────────────────┘        │ Critical Fleet  │
                                         │ Recovery Ops    │
                                         └─────────────────┘
```

---

# Technology Stack

| Layer            | Technology       | Purpose                      |
| ---------------- | ---------------- | ---------------------------- |
| Simulation       | Python           | Vehicle telemetry generation |
| Streaming        | Redis Streams    | Durable telemetry ingestion  |
| Processing       | Python           | Normalization and detection  |
| Database         | PostgreSQL       | System of record             |
| Backend          | FastAPI          | REST API                     |
| Authentication   | JWT              | API protection               |
| Vector Search    | FAISS            | Semantic incident search     |
| Embeddings       | all-MiniLM-L6-v2 | Incident embeddings          |
| Frontend         | React + Vite     | Fleet dashboard              |
| Testing          | pytest           | Automated testing            |
| Containerization | Docker           | Reproducible deployment      |

---

# Data Architecture

PostgreSQL is the primary system of record. Main entities:

```text
fleet, vehicle, vehicle_telemetry, incident, driver,
subscription, audit_log, recovery_case
```

| Store         | Responsibility                 |
| ------------- | ------------------------------ |
| Redis Streams | Raw telemetry ingestion buffer |
| PostgreSQL    | Relational system of record    |
| FAISS         | Derived semantic-search index  |

---

#  Entity Relationships

```text
Fleet
  └── Vehicle
        ├── Vehicle Telemetry
        ├── Incidents
        ├── Recovery Cases ── Audit Log
        ├── Subscriptions
        └── Driver
```


---

#  Real-Time Processing

```text
OEM Telemetry → Redis Stream (telemetry_raw) → Consumer Group (telemetry_processors)
   → Normalize → Duplicate Check → Out-of-Order Check
   → Incident Detection → Health Score → PostgreSQL
```

The processor writes system state; FastAPI reads and exposes that state to the
dashboard and clients. Ingestion and API concerns are kept separate.

---

# Security

JWT authentication protects the dashboard, critical vehicles, analytics,
semantic search, escalation, Top-K, recovery risk and recovery cases.

**Search rate limiting.** Verified behaviour:

```text
Unauthenticated request  → 401
Authenticated request    → 200
Rate limit exceeded      → 429
```

**Data security.** All vehicle data is synthetic; no real vehicle or personal
data is used. A production deployment should keep credentials in environment
variables or a secret manager and use production-grade IAM.

---

#  Performance Evidence

## Simulation Results (100K run)

```text
Vehicles:          100,000
Normal events:     100,000
Duplicates:          1,952
Out-of-order:        2,035
```

## Database State at the Documented Measurement Point

```text
Vehicles:           100,000
Telemetry rows:     122,555
Incidents:           45,605
Critical incidents:   1,314
Recovery cases:          48   (OPEN 30, ASSIGNED 17, RESOLVED 1)
```

## Producer Benchmark

```text
Events:       10,000
Elapsed:      ~6.35 seconds
Throughput:   ~1,576 events/second
```

> This is a producer benchmark. The project does **not** claim 100K events/second.

## Redis Backlog Recovery

```text
During a burst:    Pending 51, Lag 1,211
After processing:  Pending 0,  Lag 0
```

The consumer group catches up after a burst.

## PostgreSQL Query Optimization

The critical-vehicle query was optimized with a composite index
(`idx_incident_severity_vehicle`), measured with `EXPLAIN ANALYZE`:

```text
Before: ~23.9 ms    After: ~17.2 ms    (~28% reduction)
```


---

# Testing

```bash
python -m pytest -q
```

Current result:

```text
3 passed in 20.06s
```

Tests cover Top-K problematic vehicle selection, incident escalation and
rolling-window expiration.

Also verified manually: JWT authentication, protected endpoints, semantic
search, search rate limiting, Docker API execution, Redis backlog recovery and
PostgreSQL query optimization.

---

#  Observability

Currently available: Redis consumer-group pending count and lag, duplicate and
out-of-order counters, API access logs, and PostgreSQL `EXPLAIN ANALYZE`.

A Prometheus/Grafana stack is not included. Future work can expose ingestion
rate, duplicate and out-of-order rates, consumer lag, pending entries, API
latency, error rate and recovery workload.

---

#  Algorithms and Data Structures

| Problem             | Approach                | Complexity      |
| ------------------- | ----------------------- | --------------- |
| Duplicate detection | Event identity lookup   | O(1) per event  |
| Top-K vehicles      | Min-heap                | O(n log K)      |
| Incident escalation | Rolling time window     | O(window)       |
| Semantic search     | FAISS nearest-neighbour | Index dependent |
| Incident rules      | Rule engine             | O(1) per event  |

---

#  API

Interactive documentation: <http://localhost:8000/docs>

| Method  | Endpoint                                | Purpose                  |
| ------- | --------------------------------------- | ------------------------ |
| `POST`  | `/api/login`                            | Obtain JWT               |
| `GET`   | `/api/dashboard`                        | Fleet overview           |
| `GET`   | `/api/vehicles/critical`                | Critical vehicles        |
| `GET`   | `/api/analytics/escalation`             | Escalation analysis      |
| `GET`   | `/api/analytics/top-vehicles`           | Top-K vehicles           |
| `GET`   | `/api/analytics/batch`                  | Batch analytics          |
| `GET`   | `/api/recovery/risk`                    | Recovery risk            |
| `POST`  | `/api/recovery/cases/create`            | Create recovery cases    |
| `GET`   | `/api/recovery/cases`                   | List recovery cases      |
| `PATCH` | `/api/recovery/cases/{case_id}/assign`  | Assign agent             |
| `PATCH` | `/api/recovery/cases/{case_id}/resolve` | Resolve case             |
| `GET`   | `/api/search`                           | Semantic incident search |

Authentication flow:

```text
POST /api/login → JWT → Authorization: Bearer <token> → protected endpoints
```

---


# Project Structure

```text
fleet-intelligence/
│
├── api/
│   ├── main.py
│   └── Dockerfile
│
├── dashboard/
│   ├── src/
│   ├── package.json
│   └── vite.config.*
│
├── db/
│   └── init.sql
│
├── docs/
│   ├── architecture.md
│   └── erd.md
│
├── processor/
│   ├── consumer.py
│   └── vector_search.py
│
├── simulator/
│   ├── simulator.py
│   └── simulator_backup.py
│
├── tests/
│   └── test_api.py
│
├── vector_index/
│   ├── incidents.faiss
│   └── incident_ids.pkl
│
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── README.md
```

---



# Known Limitations

This is a hackathon-scale prototype.

1. Producer throughput was measured at approximately 1.6K events/second.
2. 100K events/second was not benchmarked.
3. Testing has primarily been performed on a single-node setup.
4. Detection thresholds are calibrated on synthetic data.
5. Recovery risk weights are design choices and are not production-calibrated.
6. FAISS is a derived local index and must be rebuilt when incident data changes.
7. API p95/p99 latency has not been formally load-tested.
8. No Prometheus/Grafana stack is included.
9. Device-level authentication is not implemented.
10. Automated test coverage is limited.
11. Cloud deployment is not part of the current implementation.

---

# Future Enhancements

* Automatic FAISS re-indexing
* Multi-consumer load testing
* CI/CD pipeline
* Prometheus/Grafana observability
* Cloud deployment
* Device authentication
* Time-series storage for long-term telemetry
* Learned anomaly detection
* Formal semantic-search evaluation
* Expanded unit and integration tests
* API p95/p99 load testing

---

---

#  Design Decisions

**Redis Streams over Kafka.** This is a focused solo implementation that needs
durable stream processing and consumer groups without Kafka's operational
overhead. Kafka remains an option for higher-scale distributed ingestion.

**PostgreSQL as the system of record.** ACID transactions, relational
modelling, indexing, joins, query planning and `EXPLAIN ANALYZE`.

**FAISS for vector search.** Local semantic search without another hosted
service. The index is derived and rebuildable from incident data.

**Rule-based detection.** No labelled real-world vehicle dataset was
available, so detection and recovery scoring use explicit, explainable rules.

---


