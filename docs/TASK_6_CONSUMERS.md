# Task 6: Consumer Implementation

## 1. Consumer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONSUMER ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     BaseConsumer (Abstract)                           │  │
│  │                                                                       │  │
│  │   ┌─────────────────────────────────────────────────────────────┐     │  │
│  │   │  PROCESSING FLOW                                            │     │  │
│  │   │                                                             │     │  │
│  │   │   Poll ──► Check ──► Handle ──► Mark ──► Commit             │     │  │
│  │   │   Kafka    Idempotency  Event   Processed  Offset           │     │  │
│  │   │                                                             │     │  │
│  │   └─────────────────────────────────────────────────────────────┘     │  │
│  │                                                                       │  │
│  │   Abstract methods:                                                   │  │
│  │   • get_topics() -> List[str]                                         │  │
│  │   • handle_event(event) -> None                                       │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                            │ extends                                        │
│                            ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                 Projection Consumers                                  │  │
│  │   UserCardsConsumer, FeedBuilderConsumer, OrderConsumer, etc.         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Idempotency Store

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      IDEMPOTENCY                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COLLECTION: processed_events                                               │
│                                                                             │
│  {                                                                          │
│    consumer_group: "sc-proj-user-cards",                                    │
│    event_id: "uuid-...",                                                    │
│    entity_id: "65a1b2c3...",                                                │
│    entity_version: 5,                                                       │
│    event_type: "user.verified",                                             │
│    processed_at: ISODate("...")                                             │
│  }                                                                          │
│                                                                             │
│  INDEX: (consumer_group, event_id) UNIQUE                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Files

```
kafka/consumer/
├── __init__.py
├── base.py              # BaseConsumer
└── idempotency.py       # IdempotencyStore
```
