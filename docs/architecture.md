# Fleet Intelligence — Architecture

## 1. System Overview

Fleet Intelligence is a real-time vehicle telemetry processing platform designed to ingest telemetry from a large simulated fleet, normalize OEM-specific payloads, detect incidents, calculate vehicle health, persist operational data, and expose analytics through secure APIs and a dashboard.

## 2. High-Level Flow

```text
Vehicle Simulator
       |
       v
Redis Stream: telemetry_raw
       |
       v
Telemetry Stream Processor
       |
       +--> Normalization
       |
       +--> Duplicate / Out-of-Order Detection
       |
       +--> Incident Detection
       |
       +--> Health Scoring
       |
       v
PostgreSQL
       |
       +--> FastAPI
       |      |
       |      v
       |   React Dashboard
       |
       +--> FAISS Vector Search

## 3. Components

### Vehicle Simulator
Generates telemetry for 100K+ simulated vehicles with configurable duplicate and out-of-order event rates.

### Redis Streams
Provides durable stream-based buffering between telemetry generation and processing.

### Telemetry Processor
Consumes events using a Redis consumer group, normalizes OEM-specific payloads, detects duplicates and out-of-order events, persists telemetry, detects incidents, and updates vehicle health.

### PostgreSQL
Stores vehicles, telemetry, incidents, fleets, drivers, subscriptions, and audit information.

### FAISS
Provides semantic similarity search over incident descriptions using vector embeddings.

### FastAPI
Exposes dashboard, vehicle, analytics, authentication, and semantic-search APIs.

### React Dashboard
Provides fleet overview, incident analytics, fleet health, critical vehicles, and semantic incident search.

## 4. Data Flow

1. Simulator generates vehicle telemetry.
2. Events are written to the Redis `telemetry_raw` stream.
3. The processor consumes events through the `telemetry_processors` consumer group.
4. OEM-specific payloads are normalized.
5. Duplicate and out-of-order events are identified.
6. Vehicle telemetry is persisted in PostgreSQL.
7. Rule-based incident detection generates incidents.
8. Vehicle health score is updated.
9. FastAPI queries PostgreSQL for operational analytics.
10. Incident embeddings are searched through FAISS.
11. React dashboard displays fleet state and analytics.

## 5. Storage Strategy

| Storage | Responsibility |
|---|---|
| Redis Streams | Real-time telemetry buffering |
| PostgreSQL | Relational operational data and analytics |
| FAISS | Vector similarity search |

## 6. Processing Characteristics

- Redis consumer groups provide stream-based processing.
- Duplicate events are detected using event identifiers.
- Out-of-order events are explicitly tracked.
- Incident detection is rule-based.
- Vehicle health is maintained as a bounded score from 0–100.
- Top-K problematic vehicles use a min-heap with O(n log k) complexity.
- Incident escalation uses a sliding time window.

## 7. Security

- JWT-based authentication.
- Role validation for protected endpoints.
- Protected semantic search endpoint.
- Search rate limiting.
- CORS restricted to configured dashboard origins.
