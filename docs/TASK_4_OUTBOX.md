# Task 4: Outbox Implementation

## 1. Outbox Pattern Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OUTBOX PATTERN                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PROBLEM: Dual-write inconsistency                                          │
│  ═══════════════════════════════════                                        │
│                                                                             │
│    Service writes to DB ────► Success                                       │
│    Service writes to Kafka ──► Failure (network issue)                      │
│                                                                             │
│    Result: DB has data, Kafka doesn't. Inconsistent state.                  │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  SOLUTION: Transactional Outbox                                             │
│  ══════════════════════════════                                             │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │  ATOMIC TRANSACTION                                             │      │
│    │                                                                 │      │
│    │    1. Write Entity ─────────────────┐                           │      │
│    │    2. Write Outbox Record ──────────┤ Same MongoDB session      │      │
│    │    3. Commit ───────────────────────┘                           │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                           │                                                 │
│                           │ Transaction committed                           │
│                           ▼                                                 │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │  BACKGROUND WORKER (async)                                      │      │
│    │                                                                 │      │
│    │    1. Poll outbox for pending records                           │      │
│    │    2. Publish to Kafka                                          │      │
│    │    3. Mark as published                                         │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  GUARANTEE: If entity exists, event WILL be published (eventually)          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Outbox Collection Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OUTBOX DOCUMENT                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  EVENT IDENTIFICATION                                               │    │
│  │  ────────────────────                                               │    │
│  │  event_id: str ─────────────► UUID for idempotency                  │    │
│  │  event_type: str ───────────► "user.created"                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ENTITY CONTEXT                                                     │    │
│  │  ──────────────                                                     │    │
│  │  entity_type: str ──────────► "user", "order", etc.                 │    │
│  │  entity_id: str ────────────► MongoDB ObjectId                      │    │
│  │  entity_version: int ───────► For ordering                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  KAFKA ROUTING                                                      │    │
│  │  ─────────────                                                      │    │
│  │  topic: str ────────────────► "sc.domain.user"                      │    │
│  │  partition_key: str ────────► entity_id (for ordering)              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  PAYLOAD                                                            │    │
│  │  ───────                                                            │    │
│  │  payload: dict ─────────────► Serialized EventEnvelope              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  PROCESSING STATE                                                   │    │
│  │  ────────────────                                                   │    │
│  │  status: enum ──────────────► pending│processing│published│failed   │    │
│  │  retry_count: int ──────────► 0, 1, 2, ... max_retries              │    │
│  │  max_retries: int ──────────► Default: 5                            │    │
│  │  last_error: str? ──────────► Error message if failed               │    │
│  │  last_error_at: datetime? ──► When last failure occurred            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  TIMESTAMPS                                                         │    │
│  │  ──────────                                                         │    │
│  │  created_at: datetime ──────► When record was created               │    │
│  │  processing_started_at ─────► When processing began                 │    │
│  │  published_at ──────────────► When successfully published           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  WORKER LOCKING                                                     │    │
│  │  ──────────────                                                     │    │
│  │  locked_by: str? ───────────► Worker ID holding lock                │    │
│  │  locked_until: datetime? ───► Lock expiry (stale lock recovery)     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Publisher Worker Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PUBLISHER WORKER FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                    MAIN LOOP                                      │     │
│   │                                                                   │     │
│   │   while running:                                                  │     │
│   │       │                                                           │     │
│   │       ▼                                                           │     │
│   │   ┌─────────────────────────────────────────────────────────┐     │     │
│   │   │  FETCH PENDING (atomic find + lock)                     │     │     │
│   │   │                                                         │     │     │
│   │   │  Query:                                                 │     │     │
│   │   │    status = pending                                     │     │     │
│   │   │    OR (status = failed AND retry_count < max_retries)   │     │     │
│   │   │    OR (status = processing AND locked_until < now)      │     │     │
│   │   │                                                         │     │     │
│   │   │  Update:                                                │     │     │
│   │   │    status = processing                                  │     │     │
│   │   │    locked_by = worker_id                                │     │     │
│   │   │    locked_until = now + 60s                             │     │     │
│   │   └─────────────────────────────────────────────────────────┘     │     │
│   │       │                                                           │     │
│   │       │ batch of records                                          │     │
│   │       ▼                                                           │     │
│   │   ┌─────────────────────────────────────────────────────────┐     │     │
│   │   │  FOR EACH RECORD                                        │     │     │
│   │   │                                                         │     │     │
│   │   │      ┌─────────────────────────────────────────────┐    │     │     │
│   │   │      │  PUBLISH TO KAFKA                           │    │     │     │
│   │   │      │  topic: record.topic                        │    │     │     │
│   │   │      │  key: record.partition_key                  │    │     │     │
│   │   │      │  value: record.payload                      │    │     │     │
│   │   │      └──────────────────┬──────────────────────────┘    │     │     │
│   │   │                         │                               │     │     │
│   │   │           ┌─────────────┴─────────────┐                 │     │     │
│   │   │           │                           │                 │     │     │
│   │   │           ▼                           ▼                 │     │     │
│   │   │      ┌─────────┐               ┌───────────┐            │     │     │
│   │   │      │ SUCCESS │               │  FAILURE  │            │     │     │
│   │   │      └────┬────┘               └─────┬─────┘            │     │     │
│   │   │           │                          │                  │     │     │
│   │   │           ▼                          ▼                  │     │     │
│   │   │   ┌──────────────┐          ┌──────────────────┐        │     │     │
│   │   │   │ Mark as      │          │ retry_count++    │        │     │     │
│   │   │   │ PUBLISHED    │          │ Mark as FAILED   │        │     │     │
│   │   │   │ Release lock │          │ Release lock     │        │     │     │
│   │   │   └──────────────┘          └────────┬─────────┘        │     │     │
│   │   │                                      │                  │     │     │
│   │   │                                      ▼                  │     │     │
│   │   │                         ┌────────────────────────┐      │     │     │
│   │   │                         │ retry_count >= max?    │      │     │     │
│   │   │                         └───────────┬────────────┘      │     │     │
│   │   │                                     │                   │     │     │
│   │   │                           ┌─────────┴─────────┐         │     │     │
│   │   │                           │                   │         │     │     │
│   │   │                           ▼                   ▼         │     │     │
│   │   │                     ┌──────────┐        ┌──────────┐    │     │     │
│   │   │                     │   NO     │        │   YES    │    │     │     │
│   │   │                     │ (retry)  │        │ (DLQ)    │    │     │     │
│   │   │                     └──────────┘        └──────────┘    │     │     │
│   │   │                                                         │     │     │
│   │   └─────────────────────────────────────────────────────────┘     │     │
│   │       │                                                           │     │
│   │       │ empty batch?                                              │     │
│   │       ▼                                                           │     │
│   │   ┌─────────────────────────────────────────────────────────┐     │     │
│   │   │  BACKOFF                                                │     │     │
│   │   │  If no records: wait with exponential backoff           │     │     │
│   │   │  Max wait: 10 seconds                                   │     │     │
│   │   └─────────────────────────────────────────────────────────┘     │     │
│   │                                                                   │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Idempotency Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      IDEMPOTENCY GUARANTEES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRODUCER SIDE (Outbox)                                                     │
│  ══════════════════════                                                     │
│                                                                             │
│  • event_id is unique (UUID)                                                │
│  • Check event_exists(event_id) before insert if needed                     │
│  • Duplicate outbox records are harmless (same event_id)                    │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  CONSUMER SIDE (Projections)                                                │
│  ═══════════════════════════                                                │
│                                                                             │
│  Consumers MUST track processed events:                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  processed_events collection                                        │    │
│  │                                                                     │    │
│  │  {                                                                  │    │
│  │    consumer_group: "sc-proj-user-cards",                            │    │
│  │    event_id: "uuid-...",                                            │    │
│  │    entity_id: "65a1b2c3...",                                        │    │
│  │    entity_version: 5,                                               │    │
│  │    processed_at: "2024-02-05T10:30:00Z"                             │    │
│  │  }                                                                  │    │
│  │                                                                     │    │
│  │  Index: (consumer_group, event_id) UNIQUE                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Processing flow:                                                           │
│                                                                             │
│  1. Receive event                                                           │
│  2. Check: is (group, event_id) in processed_events?                        │
│     • YES → Skip (already processed)                                        │
│     • NO → Continue                                                         │
│  3. Process event (update projection)                                       │
│  4. Insert processed marker                                                 │
│  5. Commit offset                                                           │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  ORDERING GUARANTEE                                                         │
│  ══════════════════                                                         │
│                                                                             │
│  Events for same entity_id:                                                 │
│  • Same partition (via partition_key = entity_id)                           │
│  • entity_version ensures order even with retries                           │
│  • Consumer can reject out-of-order events:                                 │
│    if event.version <= last_seen_version: skip                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Files Created

```
kafka/outbox/
├── __init__.py          # Package marker
├── model.py             # OutboxRecord document model
├── repository.py        # CRUD operations
└── publisher.py         # Background worker

kafka/producer/
├── __init__.py          # Package marker
└── kafka_producer.py    # Async Kafka producer wrapper
```

---

## 6. Indexes

| Index | Fields | Purpose |
|-------|--------|---------|
| Primary query | `(status, created_at)` | Fetch pending by age |
| Cleanup | `(status, published_at)` | Delete old published |
| Lock expiry | `(locked_until)` | Recover stale locks |
| Idempotency | `(event_id)` | Duplicate check |
| Entity ordering | `(entity_id, entity_version)` | Version checks |
