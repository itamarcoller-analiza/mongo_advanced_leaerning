# MySQL Subscriber Service - Product Requirements Document

**Version:** 1.0
**Status:** Draft
**Last Updated:** 2026-02-08

---

## 1. Product Overview

### 1.1 Purpose

The MySQL Subscriber Service is a Change Data Capture (CDC) system that captures row-level changes from MySQL databases and propagates them to downstream systems in near-real-time. It serves as the authoritative bridge between operational databases and event-driven architectures.

### 1.2 Supported Change Capture Modes

| Mode | Description | Trade-offs |
|------|-------------|------------|
| **Binlog-based CDC** (Primary) | Reads MySQL binary log in ROW format | Lowest latency, minimal source impact, requires binlog enabled |
| **Logical Replication** | Uses MySQL replication protocol as replica | Native semantics, consumes replication slot |
| **Query-based Polling** (Fallback) | Polls tables using timestamp columns | No binlog required, higher latency |

**Recommendation:** Binlog-based CDC with ROW format for sub-second latency and minimal source impact.

### 1.3 Target Consumers

```
                    MySQL Subscriber Service
                             │
                             ▼
                       Apache Kafka
                             │
        ┌────────┬───────────┼───────────┬────────┐
        ▼        ▼           ▼           ▼        ▼
     Search    Cache    Analytics    Internal   Data
     Index     Layer    Pipeline     Services   Lake
```

### 1.4 Primary Value

| Dimension | Value |
|-----------|-------|
| **Business** | Real-time analytics, search freshness, cache consistency, audit compliance |
| **Technical** | Decoupled architectures, event sourcing, CQRS patterns |
| **Operational** | Single source of truth, replay capability, debugging |

---

## 2. Goals & Non-Goals

### 2.1 Goals

| Priority | Goal |
|----------|------|
| P0 | Near-real-time replication (p99 < 1 second) |
| P0 | At-least-once delivery with idempotency keys |
| P0 | Deterministic reprocessing from any position |
| P1 | Horizontal scalability with linear throughput |
| P1 | Full observability into lag, throughput, errors |
| P1 | Schema evolution support without manual intervention |

### 2.2 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Cross-database transactions | Use Saga pattern downstream |
| Full ETL replacement | CDC is change-only; use batch for backfill |
| Complex transformations | Keep CDC thin; transform in stream processors |
| Sub-millisecond latency | Network + Kafka overhead makes impractical |

---

## 3. Stakeholders & Users

| Stakeholder | Interest |
|-------------|----------|
| **Platform Engineering** | Core infrastructure reliability |
| **Backend Services** | Event consumption for business logic |
| **Data Engineering** | Analytics pipeline integration |
| **Analytics Teams** | Real-time dashboards and reports |
| **DevOps/SRE** | System reliability and incident response |
| **Security/Compliance** | Data governance and audit |

---

## 4. Functional Requirements

### 4.1 Change Data Capture

**Supported Events:**

| Event | Captured Data |
|-------|---------------|
| INSERT | After image (full row) |
| UPDATE | Before + After images |
| DELETE | Before image |
| DDL | Schema change metadata (optional) |

**MySQL Compatibility:**
- MySQL 5.7.x, 8.0.x
- MariaDB 10.3+
- Aurora MySQL 2.x/3.x
- Binlog format: ROW (required)
- GTID support: native on MySQL 8.x

**Initial Snapshot Strategy:**

```
Is table empty in target?
    │
    ├── YES → Full snapshot required
    │           ├── < 1M rows → Single-threaded SELECT
    │           └── >= 1M rows → Chunked parallel snapshot
    │
    └── NO → Incremental from last known position
              ├── GTID available → Resume from GTID
              └── Position only → Validate binlog exists
```

### 4.2 Event Processing Pipeline

```
Binlog Stream
     │
     ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ PARSING │───►│NORMALIZE│───►│TRANSFORM│───►│ ROUTING │───►│ PUBLISH │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │              │
  Raw bytes    Typed values   Enriched      Topic/key       Kafka
  parsed       + nulls        + metadata    assigned        produce
```

**Event Envelope Fields:**
- `event_type`: Operation (create/update/delete)
- `event_id`: Unique identifier (UUID)
- `timestamp`: Event time (milliseconds)
- `entity_id`: Primary key of affected row
- `source`: Database, table, binlog position, GTID
- `before`: Previous row state (update/delete)
- `after`: New row state (insert/update)
- `transaction`: Transaction ID and ordering

**Ordering Guarantees:**

| Scope | Guarantee | Mechanism |
|-------|-----------|-----------|
| Per-row | Total order | Kafka partition by PK |
| Per-table | Causal order | Configurable single partition |
| Per-transaction | Atomic visibility | Transaction markers |
| Cross-table | No global order | Transaction ID correlation |

### 4.3 Offset & State Management

**Position Tracking:**
- GTID-based (preferred): Unique transaction identifier, survives failover
- File-based (fallback): Binlog filename + byte position

**Checkpointing Strategy:**

```
Binlog Event
     │
     ▼
┌─────────────┐
│  In-Memory  │◄── Buffer (max 1000 events or 100ms)
│   Buffer    │
└─────────────┘
     │
     │ Flush triggers: buffer full, time elapsed,
     │                 transaction boundary, shutdown
     ▼
┌─────────────┐
│   Kafka     │◄── Produce batch with acks=all
│   Produce   │
└─────────────┘
     │
     │ On successful ack
     ▼
┌─────────────┐
│ Checkpoint  │◄── Persist position atomically
│   Store     │
└─────────────┘
```

**Checkpoint Storage Options:**

| Storage | Durability | Latency | Use Case |
|---------|------------|---------|----------|
| Kafka offsets | High | Medium | Default |
| MySQL (source) | High | Low | Self-contained |
| Redis | Medium | Very Low | Performance-critical |

**Recovery Flow:**
1. Load last checkpointed position
2. Validate binlog still exists at position
3. If binlog purged and no GTID: re-snapshot required
4. Resume streaming from checkpoint
5. Events between checkpoint and crash will be re-sent (duplicates)

### 4.4 Delivery Guarantees

| Level | Strategy | Trade-off |
|-------|----------|-----------|
| At-most-once | Checkpoint before produce | Fast, may lose events |
| **At-least-once** | Checkpoint after produce ack | Safe, may duplicate |
| Exactly-once | Kafka transactions + idempotent consumers | Correct, higher latency |

**Default: At-least-once with idempotency keys**

**Idempotency Key Generation:**
- Components: server_id, gtid/position, table, primary_key, operation, row_number
- Deterministic: same event always produces same key
- Stable across replays

**Failure Recovery Matrix:**

| Failure | Detection | Recovery | Data Impact |
|---------|-----------|----------|-------------|
| Process crash | Heartbeat timeout | Restart from checkpoint | Duplicates possible |
| MySQL disconnect | Connection error | Reconnect with backoff | No impact |
| Kafka unavailable | Produce timeout | Buffer locally, retry | Lag accumulates |
| Binlog purged | Position validation | Re-snapshot required | Full re-sync |

### 4.5 Schema Management

**Schema Discovery:**
- Introspect from information_schema on startup
- Track DDL events in binlog
- Version schemas with monotonic increment

**Compatibility Rules:**

| Change Type | Backward | Forward | Action |
|-------------|----------|---------|--------|
| Add nullable column | Yes | Yes | Auto-accept |
| Add non-null with default | Yes | No | Warning |
| Remove column | No | Yes | Require confirmation |
| Rename column | No | No | Require migration |
| Widen type (int→bigint) | Yes | Yes | Auto-accept |
| Narrow type | No | No | Require confirmation |

**Schema Registry Integration:**
- Centralized schema storage
- Compatibility enforcement
- Consumer schema negotiation

### 4.6 Filtering & Routing

**Filter Levels:**

| Level | Examples |
|-------|----------|
| Table | Include `orders.*`, exclude `*.audit_log` |
| Column | Exclude `password_hash`, mask `email` |
| Row | Predicate: `after.total_cents > 10000` |

**Routing Rules:**
- Pattern matching: `orders.*` → `orders.changes`
- Predicates: high priority orders → dedicated topic
- Fan-out: single event to multiple topics
- Default: `cdc.{database}.{table}`

### 4.7 Configuration Management

**Configuration Categories:**

| Category | Hot Reload | Examples |
|----------|------------|----------|
| Processing | Yes | batch_size, timeout, filters |
| Routing | Yes | topic rules, partition keys |
| Features | Yes | feature flags |
| Source connection | No | MySQL host, credentials |
| Kafka bootstrap | No | Broker addresses |

**Secret Management:**
- Environment variables
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes Secrets

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Target |
|--------|--------|
| Peak throughput | 50,000 rows/sec per instance |
| Sustained throughput | 30,000 rows/sec per instance |
| Snapshot speed | 100,000 rows/sec (parallel) |

**Latency SLA:**

| Percentile | Target |
|------------|--------|
| p50 | < 100ms |
| p95 | < 500ms |
| p99 | < 1000ms |
| p99.9 | < 5000ms |

**Backpressure Strategy:**
- Monitor buffer size against high/low watermarks
- Increase processing delay when buffer exceeds threshold
- Exponential backoff up to max delay
- Resume normal speed when buffer drains

### 5.2 Scalability

**Horizontal Scaling Model:**

```
              ┌─────────────┐
              │ Coordinator │
              │  (Leader)   │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │Worker 1 │  │Worker 2 │  │Worker 3 │
   │         │  │         │  │         │
   │users.*  │  │orders.* │  │products │
   │auth.*   │  │payments │  │inventory│
   └─────────┘  └─────────┘  └─────────┘
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
                   Kafka
```

**Work Distribution:**
- Consistent hashing for stable table assignment
- Automatic rebalance on worker count change
- Minimal table movement during scaling

### 5.3 Reliability & Fault Tolerance

**Failure Domains:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   MySQL     │     │ CDC Worker  │     │   Kafka     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
 Failure Modes:      Failure Modes:      Failure Modes:
 - Primary down      - Process crash      - Broker down
 - Network split     - OOM killed         - Disk full
 - Binlog purged     - Config error       - Network issue
       │                   │                   │
       ▼                   ▼                   ▼
 Mitigations:        Mitigations:        Mitigations:
 - Failover          - Restart            - Retry
 - Read replica      - Checkpoint         - Buffer
                     - Alerts             - Backpressure
```

**Retry Policies:**

| Component | Max Attempts | Backoff |
|-----------|--------------|---------|
| MySQL connection | 10 | Exponential 100ms → 30s |
| Kafka produce | 5 | Exponential 100ms → 10s |
| Checkpoint | 3 | Fixed 1s |

---

## 6. System Architecture

### 6.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Control Plane                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │ Admin API │  │  Metrics  │  │ Alerting  │  │ Config Mgr│            │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                               Data Plane                                 │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                           CDC Worker                              │   │
│  │                                                                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │   │
│  │  │ Binlog   │─►│  Event   │─►│Transform │─►│Publisher │         │   │
│  │  │ Reader   │  │  Parser  │  │ Engine   │  │          │         │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────┬─────┘         │   │
│  │       │                                          │               │   │
│  │       │         ┌──────────┐                    │               │   │
│  │       └────────►│  State   │◄───────────────────┘               │   │
│  │                 │  Store   │                                     │   │
│  │                 └──────────┘                                     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
              │                                          │
              ▼                                          ▼
       ┌───────────┐                              ┌───────────┐
       │   MySQL   │                              │   Kafka   │
       │  (Source) │                              │  (Target) │
       └───────────┘                              └───────────┘
```

### 6.2 Component Responsibilities

| Component | Responsibility | Failure Impact |
|-----------|---------------|----------------|
| **Binlog Reader** | Connect to MySQL, read binlog stream | Total stop |
| **Event Parser** | Deserialize binlog to structured format | Data corruption |
| **State Store** | Persist checkpoint, schema cache | Recovery failure |
| **Transform Engine** | Apply filters, enrichment, routing | Event loss |
| **Publisher** | Produce to Kafka with guarantees | Lag accumulation |
| **Admin API** | Operational control, health checks | No ops visibility |
| **Metrics Exporter** | Export observability data | Blind operations |

---

## 7. Observability & Monitoring

### 7.1 Key Metrics

| Category | Metric | Purpose |
|----------|--------|---------|
| **Throughput** | events_processed_total | Capacity monitoring |
| **Throughput** | events_published_total | Kafka delivery |
| **Latency** | replication_lag_ms | SLA compliance |
| **Latency** | processing_duration_seconds | Performance |
| **Buffer** | buffer_size, buffer_bytes | Backpressure |
| **Position** | binlog_position, gtid_count | Progress tracking |
| **Errors** | errors_total by type | Quality indicator |
| **Checkpoint** | checkpoint_lag_events | Recovery window |

### 7.2 Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| Replication lag > 1 min | lag_ms > 60000 for 5m | Critical |
| Replication lag > 10s | lag_ms > 10000 for 10m | Warning |
| No events processed | rate = 0 for 10m | Critical |
| High error rate | rate > 1/sec for 5m | Warning |
| Checkpoint stale | age > 5 min | Critical |
| Buffer full | size > 90% capacity | Warning |

### 7.3 Logging Strategy

**Structured JSON logging with fields:**
- timestamp, level, logger
- connector, table, operation
- binlog_file, binlog_pos
- latency_ms, batch_size
- error_type, retry_attempt

### 7.4 Distributed Tracing

**Span hierarchy:**
- `cdc.process_event` (parent)
  - `cdc.parse`
  - `cdc.transform`
  - `cdc.publish`

**Trace context propagation:** Event headers carry trace IDs for end-to-end visibility.

---

## 8. Security & Compliance

### 8.1 Authentication

| Component | Method |
|-----------|--------|
| MySQL | Static credentials, IAM auth (Aurora), Vault dynamic secrets |
| Kafka | SASL/SCRAM, mTLS |
| Admin API | OAuth2/JWT, API keys |

### 8.2 Authorization

**Minimum MySQL Privileges:**
- SELECT on captured tables
- REPLICATION SLAVE, REPLICATION CLIENT
- LOCK TABLES (for consistent snapshots)

### 8.3 Data Protection

**PII Handling Strategies:**

| Strategy | Description |
|----------|-------------|
| Exclude | Drop column entirely |
| Mask | Partial reveal (last 4 digits) |
| Hash | One-way hash (email → hash@domain) |
| Encrypt | Reversible with key management |
| Tokenize | Replace with reference token |

### 8.4 Audit Logging

**Logged Events:**
- Data access (READ, EXPORT, REPLAY)
- Configuration changes
- Offset modifications
- Authentication attempts

---

## 9. API & Control Plane

### 9.1 Management API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component status |
| `/connectors` | GET/POST | List or create connectors |
| `/connectors/{name}` | GET/PUT/DELETE | Connector CRUD |
| `/connectors/{name}/status` | GET | Current state, lag, throughput |
| `/connectors/{name}/pause` | POST | Pause processing |
| `/connectors/{name}/resume` | POST | Resume processing |
| `/connectors/{name}/restart` | POST | Restart with optional position |
| `/connectors/{name}/offsets` | GET/PUT | View or modify position |
| `/connectors/{name}/snapshot` | POST | Trigger table snapshot |
| `/config/reload` | POST | Hot-reload configuration |

### 9.2 Admin Operations

| Operation | Use Case |
|-----------|----------|
| **Rebalance** | Redistribute tables after worker changes |
| **Reset offset** | Rewind to specific position (causes duplicates) |
| **Rebuild state** | Clear cache, re-introspect schemas |
| **Drain node** | Graceful shutdown for maintenance |
| **Force snapshot** | Re-capture specific tables |

---

## 10. Rollout & Migration Plan

### 10.1 Deployment Phases

```
Phase 1: Shadow Mode (Week 1-2)
┌────────────────────────────────────────────────────────────────┐
│                                                                 │
│   MySQL ──► CDC ──► Shadow Topic ──► Validator                 │
│              │                           │                      │
│              └───────────────────────────┼───► Comparison       │
│                                          │        Report        │
│   MySQL ──► Legacy System ──► Prod Topic ┘                     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
- CDC runs parallel with existing system
- Events to shadow topics only
- Compare CDC vs legacy events
- No production impact

Phase 2: Dual Write (Week 3-4)
┌────────────────────────────────────────────────────────────────┐
│                                                                 │
│   MySQL ──► CDC ──────────┬──► Prod Topic (primary)            │
│              │            │                                     │
│              │            └──► Comparison                       │
│              │                    │                             │
│   MySQL ──► Legacy ───────────────┘ (validation only)          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
- CDC becomes primary
- Legacy continues for validation
- Alerts on divergence
- Quick rollback available

Phase 3: CDC Only (Week 5+)
┌────────────────────────────────────────────────────────────────┐
│                                                                 │
│   MySQL ──► CDC ──► Prod Topics                                │
│                                                                 │
│   Legacy: Decommissioned                                       │
└────────────────────────────────────────────────────────────────┘
```

### 10.2 Rollback Procedures

| Scenario | Procedure | Time |
|----------|-----------|------|
| **Full rollback** | Stop CDC, enable legacy, switch routing | < 5 min |
| **Offset rollback** | Pause, reset position, resume | < 2 min |
| **Re-snapshot** | Pause, clear checkpoint, trigger snapshot | Varies |

### 10.3 Validation Steps

| Validation | Method |
|------------|--------|
| **Completeness** | Compare row counts: MySQL vs Kafka events |
| **Correctness** | Sample events, verify against source |
| **Ordering** | Check sequence monotonicity per partition |
| **Latency** | Measure commit-to-Kafka time distribution |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Data Loss** | Low | Critical | At-least-once delivery, validation, checksums |
| **Data Drift** | Medium | High | Periodic reconciliation, divergence alerts |
| **Lag Accumulation** | Medium | Medium | Backpressure, auto-scaling, lag alerts |
| **Schema Breakage** | Medium | High | Schema registry, compatibility checks |
| **Binlog Purged** | Low | High | Monitor retention, alert before expiry |
| **MySQL Overload** | Low | High | Read from replica, connection pooling |
| **Kafka Outage** | Low | Critical | Local buffering, multi-cluster setup |
| **Human Error** | Medium | High | RBAC, audit logs, confirmation prompts |

---

## 12. Success Metrics (KPIs)

### 12.1 Primary Metrics

| Metric | Target |
|--------|--------|
| **Replication Lag (p99)** | < 1 second |
| **Data Correctness Rate** | 99.999% |
| **Availability** | 99.9% |
| **Recovery Time (MTTR)** | < 5 minutes |
| **Throughput Utilization** | > 80% capacity |

### 12.2 Secondary Metrics

| Metric | Target |
|--------|--------|
| Events per Second | > 30,000 |
| Checkpoint Frequency | Every 1000 events |
| Error Rate | < 0.01% |
| Consumer Lag | < 10,000 events |
| Cost per GB replicated | < $0.10 |

---

## 13. Open Questions & Future Work

### 13.1 Open Questions

| Question | Decision Needed By |
|----------|-------------------|
| Multi-source support architecture? | Phase 2 planning |
| Cross-region replication strategy? | DR planning |
| Stream processing integration (Flink/Spark)? | Analytics roadmap |
| Governance and lineage tracking? | Compliance review |

### 13.2 Future Phases

| Phase | Scope |
|-------|-------|
| **Phase 2** | Multi-source, unified schema registry, cross-source correlation |
| **Phase 3** | Exactly-once transactions, schema automation, anomaly detection |
| **Phase 4** | Self-service onboarding, multi-tenant, cost attribution |

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **CDC** | Change Data Capture - technology for tracking database changes |
| **Binlog** | MySQL binary log containing all database modifications |
| **GTID** | Global Transaction ID - unique transaction identifier |
| **ROW format** | Binlog format recording actual row data changes |
| **Checkpoint** | Persistent record of processing position |
| **At-least-once** | Events may duplicate but never lost |
| **Exactly-once** | Events delivered exactly one time |
| **Backpressure** | Flow control when downstream can't keep up |
| **Replication lag** | Time from MySQL commit to downstream availability |

---

**Document Control:**
- Created: 2026-02-08
- Owner: Platform Engineering
- Next Review: 2026-03-08
