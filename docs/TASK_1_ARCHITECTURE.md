# Task 1: Architecture + Service Boundaries

## 1. Service Layout Decision

### Recommendation: Single Service with Internal Domain Boundaries (v1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SERVICE ARCHITECTURE (v1)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     SOCIAL COMMERCE MONOLITH                        │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                      API LAYER                              │    │    │
│  │  │  Routes → Schemas → Services                                │    │    │
│  │  └─────────────────────────┬───────────────────────────────────┘    │    │
│  │                            │                                        │    │
│  │                            │ writes                                 │    │
│  │                            ▼                                        │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    DOMAIN SERVICES                          │    │    │
│  │  │                                                             │    │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │    │    │
│  │  │  │  User   │ │Supplier │ │Community│ │ Product │           │    │    │
│  │  │  │ Domain  │ │ Domain  │ │ Domain  │ │ Domain  │           │    │    │
│  │  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │    │    │
│  │  │       │           │           │           │                 │    │    │
│  │  │  ┌────┴────┐ ┌────┴────┐ ┌────┴────┐ ┌────┴────┐           │    │    │
│  │  │  │Promotion│ │  Post   │ │  Order  │ │  Feed   │           │    │    │
│  │  │  │ Domain  │ │ Domain  │ │ Domain  │ │(derived)│           │    │    │
│  │  │  └────┬────┘ └────┬────┘ └────┬────┘ └─────────┘           │    │    │
│  │  │       │           │           │                             │    │    │
│  │  └───────┼───────────┼───────────┼─────────────────────────────┘    │    │
│  │          │           │           │                                  │    │
│  │          └───────────┼───────────┘                                  │    │
│  │                      │                                              │    │
│  │                      ▼                                              │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    PERSISTENCE LAYER                        │    │    │
│  │  │                                                             │    │    │
│  │  │   ┌─────────────┐              ┌─────────────┐              │    │    │
│  │  │   │   MongoDB   │              │   Outbox    │              │    │    │
│  │  │   │  (Entities) │              │ Collection  │              │    │    │
│  │  │   └─────────────┘              └──────┬──────┘              │    │    │
│  │  │                                       │                     │    │    │
│  │  └───────────────────────────────────────┼─────────────────────┘    │    │
│  │                                          │                          │    │
│  └──────────────────────────────────────────┼──────────────────────────┘    │
│                                             │                               │
│                                             │ polls                         │
│                                             ▼                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    BACKGROUND WORKERS                               │    │
│  │                                                                     │    │
│  │   ┌─────────────────┐                                               │    │
│  │   │ Outbox Publisher│─────────────────────────────────┐             │    │
│  │   │    Worker       │                                 │             │    │
│  │   └─────────────────┘                                 │             │    │
│  │                                                       │             │    │
│  │   ┌─────────────────┐   ┌─────────────────┐          │             │    │
│  │   │   Projection    │   │    Analytics    │          │             │    │
│  │   │   Consumers     │   │    Consumers    │          │             │    │
│  │   └────────┬────────┘   └────────┬────────┘          │             │    │
│  │            │                     │                    │             │    │
│  └────────────┼─────────────────────┼────────────────────┼─────────────┘    │
│               │                     │                    │                  │
│               ▼                     ▼                    ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         KAFKA CLUSTER                               │    │
│  │                                                                     │    │
│  │   Domain Topics    │   Projection Topics   │   Analytics Topics     │    │
│  │   sc.domain.*      │   sc.proj.consumer.*  │   sc.analytics.admin.* │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rationale for Single Service (v1)

| Factor | Single Service | Microservices |
|--------|----------------|---------------|
| **Complexity** | Low - one codebase, one deploy | High - network calls, distributed txns |
| **Consistency** | Easy - local transactions | Hard - saga patterns needed |
| **Development Speed** | Fast - no inter-service contracts | Slow - API versioning overhead |
| **Operational Cost** | Low - one process to monitor | High - many services to manage |
| **Team Size Fit** | Good for < 10 engineers | Better for 10+ with clear ownership |

**v1 Choice:** Single service with clear internal boundaries.

**Future Migration Path:** Domain boundaries are explicit. When scale demands, extract:
1. Order Service (highest write volume)
2. Feed/Projection Service (highest read volume)
3. Analytics Service (different scaling profile)

---

## 2. Event Ownership Matrix

### Principle: Each domain service owns its events

The service that mutates an entity is the **sole producer** of that entity's domain events.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT OWNERSHIP MATRIX                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DOMAIN SERVICE          │  OWNS EVENTS FOR        │  DOMAIN TOPIC          │
│  ════════════════════════│═════════════════════════│════════════════════════│
│                          │                         │                        │
│  AuthService             │  User                   │  sc.domain.user        │
│  (app/services/auth.py)  │  - user.created         │                        │
│                          │  - user.verified        │                        │
│                          │  - user.updated         │                        │
│                          │  - user.role_changed    │                        │
│                          │  - user.suspended       │                        │
│                          │  - user.deleted         │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  SupplierAuthService     │  Supplier               │  sc.domain.supplier    │
│  (app/services/          │  - supplier.created     │                        │
│   supplier_auth.py)      │  - supplier.submitted   │                        │
│                          │  - supplier.verified    │                        │
│                          │  - supplier.rejected    │                        │
│                          │  - supplier.suspended   │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  CommunityService        │  Community              │  sc.domain.community   │
│  (app/services/          │  - community.created    │                        │
│   community.py)          │  - community.updated    │                        │
│                          │  - community.member_*   │                        │
│                          │  - community.deleted    │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  ProductService          │  Product                │  sc.domain.product     │
│  (app/services/          │  - product.created      │                        │
│   product.py)            │  - product.updated      │                        │
│                          │  - product.published    │                        │
│                          │  - product.inventory_*  │                        │
│                          │  - product.deleted      │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  PromotionService        │  Promotion              │  sc.domain.promotion   │
│  (app/services/          │  - promotion.created    │                        │
│   promotion.py)          │  - promotion.submitted  │                        │
│                          │  - promotion.approved_* │                        │
│                          │  - promotion.activated  │                        │
│                          │  - promotion.ended      │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  PostService             │  Post                   │  sc.domain.post        │
│  (app/services/          │  - post.created         │                        │
│   post.py)               │  - post.updated         │                        │
│                          │  - post.global_*        │                        │
│                          │  - post.deleted         │                        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  OrderService            │  Order                  │  sc.domain.order       │
│  (app/services/          │  - order.created        │                        │
│   order.py)              │  - order.payment_*      │                        │
│                          │  - order.confirmed      │                        │
│                          │  - order.shipped        │                        │
│                          │  - order.delivered      │                        │
│                          │                         │                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Flow: Write Path

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WRITE PATH EVENT FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   API Request                                                               │
│       │                                                                     │
│       ▼                                                                     │
│   ┌───────────────┐                                                         │
│   │    Route      │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │   Service     │                                                         │
│   │               │                                                         │
│   │  1. Validate  │                                                         │
│   │  2. Execute   │                                                         │
│   │  3. Prepare   │                                                         │
│   │     Event     │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │              ATOMIC TRANSACTION (same MongoDB session)          │       │
│   │                                                                 │       │
│   │   ┌─────────────────────┐      ┌─────────────────────┐          │       │
│   │   │   Update Entity     │      │   Insert Outbox     │          │       │
│   │   │                     │      │                     │          │       │
│   │   │   user.status =     │      │   {                 │          │       │
│   │   │     "active"        │      │     event_type:     │          │       │
│   │   │   user.version += 1 │      │       "user.verified"│         │       │
│   │   │                     │      │     entity_id: ...  │          │       │
│   │   │                     │      │     payload: {...}  │          │       │
│   │   │                     │      │     status: "pending"│         │       │
│   │   │                     │      │   }                 │          │       │
│   │   └─────────────────────┘      └─────────────────────┘          │       │
│   │                                                                 │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                 │
│           │ Transaction committed                                           │
│           ▼                                                                 │
│   ┌───────────────┐                                                         │
│   │   Response    │                                                         │
│   │   to Client   │                                                         │
│   └───────────────┘                                                         │
│                                                                             │
│                                                                             │
│   ═══════════════════════════════════════════════════════════════════       │
│   ASYNCHRONOUS (Background Worker)                                          │
│   ═══════════════════════════════════════════════════════════════════       │
│                                                                             │
│   ┌───────────────────────┐                                                 │
│   │   Outbox Publisher    │                                                 │
│   │                       │                                                 │
│   │   1. Poll pending     │                                                 │
│   │   2. Publish to Kafka │                                                 │
│   │   3. Mark published   │                                                 │
│   └───────────┬───────────┘                                                 │
│               │                                                             │
│               ▼                                                             │
│   ┌───────────────────────┐                                                 │
│   │       KAFKA           │                                                 │
│   │   sc.domain.user      │                                                 │
│   └───────────────────────┘                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Consumer Groups

### Design Principle: One Consumer Group per Projection Concern

Each consumer group has a single responsibility and can scale independently.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONSUMER GROUPS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  GROUP NAME                    │  SUBSCRIBES TO          │  WRITES TO       │
│  ══════════════════════════════│═════════════════════════│══════════════════│
│                                │                         │                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CONSUMER PROJECTION GROUPS                       │   │
│  │               (Build read models for consumer-facing APIs)          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                │                         │                  │
│  sc-proj-user-cards            │  sc.domain.user         │  MongoDB:        │
│                                │                         │  user_cards      │
│                                │                         │  user_counters   │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-supplier-cards        │  sc.domain.supplier     │  MongoDB:        │
│                                │                         │  supplier_cards  │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-community-cards       │  sc.domain.community    │  MongoDB:        │
│                                │                         │  community_cards │
│                                │                         │  membership_index│
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-product-listings      │  sc.domain.product      │  MongoDB:        │
│                                │                         │  product_cards   │
│                                │                         │  product_search  │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-promotion-cards       │  sc.domain.promotion    │  MongoDB:        │
│                                │                         │  promotion_cards │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-feed-builder          │  sc.domain.post         │  MongoDB:        │
│                                │  sc.domain.promotion    │  feed_items_*    │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-proj-order-summaries       │  sc.domain.order        │  MongoDB:        │
│                                │                         │  order_summaries │
│                                │                         │  user_orders     │
│                                │                         │  supplier_queue  │
│                                │                         │                  │
│                                │                         │                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ADMIN ANALYTICS GROUPS                           │   │
│  │                (Build analytics models for admin dashboards)        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                │                         │                  │
│  sc-analytics-user-lifecycle   │  sc.domain.user         │  MongoDB:        │
│                                │                         │  analytics_user_*│
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-analytics-supplier-audit   │  sc.domain.supplier     │  MongoDB:        │
│                                │                         │  analytics_      │
│                                │                         │  supplier_*      │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-analytics-community-growth │  sc.domain.community    │  MongoDB:        │
│                                │                         │  analytics_      │
│                                │                         │  community_*     │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-analytics-promotion-perf   │  sc.domain.promotion    │  MongoDB:        │
│                                │  sc.domain.order        │  analytics_      │
│                                │                         │  promotion_*     │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-analytics-order-funnel     │  sc.domain.order        │  MongoDB:        │
│                                │                         │  analytics_      │
│                                │                         │  order_*         │
│                                │                         │                  │
│  ────────────────────────────────────────────────────────────────────────  │
│                                │                         │                  │
│  sc-analytics-revenue          │  sc.domain.order        │  MongoDB:        │
│                                │                         │  analytics_      │
│                                │                         │  revenue_*       │
│                                │                         │                  │
│                                │                         │                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INFRASTRUCTURE GROUPS                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                │                         │                  │
│  sc-dlq-handler                │  sc.dlq.*               │  MongoDB:        │
│                                │                         │  dlq_events      │
│                                │                         │  (for analysis)  │
│                                │                         │                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Consumer Group Scaling Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONSUMER GROUP SCALING                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  v1 (NOW)                                                                   │
│  ════════                                                                   │
│                                                                             │
│    Each consumer group: 1 instance                                          │
│    Topic partitions: 3 (domain), 3 (projection), 6 (analytics)              │
│                                                                             │
│    ┌────────────────────┐                                                   │
│    │   Consumer Group   │                                                   │
│    │   (1 instance)     │                                                   │
│    │                    │                                                   │
│    │   Consumes all 3   │                                                   │
│    │   partitions       │                                                   │
│    └────────────────────┘                                                   │
│                                                                             │
│                                                                             │
│  v2 (SCALE)                                                                 │
│  ═══════════                                                                │
│                                                                             │
│    High-volume groups: up to partition count instances                      │
│    Kafka auto-balances partition assignment                                 │
│                                                                             │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│    │  Instance 1  │  │  Instance 2  │  │  Instance 3  │                     │
│    │              │  │              │  │              │                     │
│    │  Partition 0 │  │  Partition 1 │  │  Partition 2 │                     │
│    └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                             │
│                                                                             │
│  SCALING TRIGGERS:                                                          │
│  • Consumer lag > 1000 messages sustained                                   │
│  • Processing latency p99 > 100ms                                           │
│  • CPU > 70% on consumer instances                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Integration Points with Existing Codebase

### Where Events Are Produced

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CODEBASE INTEGRATION POINTS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EXISTING LAYER          │  EVENTING INTEGRATION                            │
│  ════════════════════════│══════════════════════════════════════════════════│
│                          │                                                  │
│  app/services/auth.py    │  Import EventBuilder                             │
│                          │  After successful user mutation:                 │
│                          │    event = EventBuilder.user_verified(user)      │
│                          │    await outbox.insert(event, session=session)   │
│                          │                                                  │
│  ────────────────────────│──────────────────────────────────────────────────│
│                          │                                                  │
│  app/services/*.py       │  Same pattern for all domain services            │
│  (all services)          │                                                  │
│                          │                                                  │
│  ────────────────────────│──────────────────────────────────────────────────│
│                          │                                                  │
│  app/models/*.py         │  NO CHANGES                                      │
│                          │  Models remain pure domain objects               │
│                          │  Events are built from models, not embedded      │
│                          │                                                  │
│  ────────────────────────│──────────────────────────────────────────────────│
│                          │                                                  │
│  app/routes/*.py         │  NO CHANGES                                      │
│                          │  Routes remain HTTP handlers only                │
│                          │  No event awareness at route level               │
│                          │                                                  │
│  ────────────────────────│──────────────────────────────────────────────────│
│                          │                                                  │
│  db/mongo_db.py          │  Add outbox collection initialization            │
│                          │  Add projection collections initialization       │
│                          │                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Modules to Add

```
kafka/
├── config/
│   ├── __init__.py
│   ├── settings.py              # Kafka connection settings
│   └── topics.py                # Topic definitions
│
├── events/
│   ├── __init__.py
│   ├── envelope.py              # Base event envelope
│   ├── builders/                # Event builders per entity
│   │   ├── __init__.py
│   │   ├── user_events.py
│   │   ├── supplier_events.py
│   │   ├── community_events.py
│   │   ├── product_events.py
│   │   ├── promotion_events.py
│   │   ├── post_events.py
│   │   └── order_events.py
│   └── schemas/                 # Pydantic event schemas
│       ├── __init__.py
│       ├── base.py
│       └── domain/
│           ├── user.py
│           ├── supplier.py
│           └── ...
│
├── outbox/
│   ├── __init__.py
│   ├── model.py                 # Outbox document model
│   ├── repository.py            # Outbox CRUD operations
│   └── publisher.py             # Background publisher worker
│
├── producer/
│   ├── __init__.py
│   └── kafka_producer.py        # Async Kafka producer wrapper
│
├── consumer/
│   ├── __init__.py
│   ├── base.py                  # Base consumer class
│   ├── idempotency.py           # Idempotency store
│   └── dlq.py                   # Dead letter queue handler
│
├── projections/
│   ├── __init__.py
│   ├── consumer/                # Consumer-facing projections
│   │   ├── user_cards.py
│   │   ├── product_listings.py
│   │   ├── feed_builder.py
│   │   └── ...
│   └── analytics/               # Admin analytics projections
│       ├── user_lifecycle.py
│       ├── order_funnel.py
│       └── ...
│
├── workers/
│   ├── __init__.py
│   ├── outbox_worker.py         # Main outbox polling worker
│   ├── projection_worker.py     # Consumer projection workers
│   └── analytics_worker.py      # Analytics projection workers
│
└── docs/
    ├── TASK_1_ARCHITECTURE.md   # This document
    ├── TASK_2_TOPICS.md
    └── ...
```

---

## 5. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMPLETE DATA FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        WRITE PATH                                   │   │
│   │                                                                     │   │
│   │   Client ──► Route ──► Service ──► [Entity + Outbox] ──► Response   │   │
│   │                                         │                           │   │
│   └─────────────────────────────────────────┼───────────────────────────┘   │
│                                             │                               │
│                                             │ (async)                       │
│                                             ▼                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     OUTBOX PUBLISHER                                │   │
│   │                                                                     │   │
│   │   Poll Outbox ──► Publish to Kafka ──► Mark Published               │   │
│   │                          │                                          │   │
│   └──────────────────────────┼──────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         KAFKA                                       │   │
│   │                                                                     │   │
│   │   sc.domain.user    sc.domain.order    sc.domain.promotion   ...    │   │
│   │         │                  │                   │                    │   │
│   └─────────┼──────────────────┼───────────────────┼────────────────────┘   │
│             │                  │                   │                        │
│             ▼                  ▼                   ▼                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    CONSUMER GROUPS                                  │   │
│   │                                                                     │   │
│   │   ┌─────────────────────┐      ┌─────────────────────┐              │   │
│   │   │ Projection Consumers│      │ Analytics Consumers │              │   │
│   │   │                     │      │                     │              │   │
│   │   │ - Check idempotency │      │ - Check idempotency │              │   │
│   │   │ - Update read model │      │ - Aggregate metrics │              │   │
│   │   │ - Commit offset     │      │ - Commit offset     │              │   │
│   │   │                     │      │                     │              │   │
│   │   └──────────┬──────────┘      └──────────┬──────────┘              │   │
│   │              │                            │                         │   │
│   └──────────────┼────────────────────────────┼─────────────────────────┘   │
│                  │                            │                             │
│                  ▼                            ▼                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      READ STORES                                    │   │
│   │                                                                     │   │
│   │   ┌─────────────────────┐      ┌─────────────────────┐              │   │
│   │   │ Consumer Read Models│      │  Analytics Models   │              │   │
│   │   │                     │      │                     │              │   │
│   │   │ - user_cards        │      │ - user_lifecycle    │              │   │
│   │   │ - product_listings  │      │ - order_funnel      │              │   │
│   │   │ - feed_items        │      │ - revenue_daily     │              │   │
│   │   │ - order_summaries   │      │ - promotion_perf    │              │   │
│   │   │                     │      │                     │              │   │
│   │   └─────────────────────┘      └─────────────────────┘              │   │
│   │              │                            │                         │   │
│   └──────────────┼────────────────────────────┼─────────────────────────┘   │
│                  │                            │                             │
│                  ▼                            ▼                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        READ PATH                                    │   │
│   │                                                                     │   │
│   │   Consumer API ◄── user_cards, feed_items (single query, fast)      │   │
│   │   Admin API ◄── analytics models (pre-aggregated)                   │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Service topology | Single service (v1) | Simplicity, fast iteration, easy consistency |
| Event production | Transactional Outbox | Guaranteed delivery, no dual-write issues |
| Consumer scaling unit | Consumer group per concern | Independent scaling, clear ownership |
| Projection storage | MongoDB (same as source) | Operational simplicity, good enough for v1 |
| Analytics storage | MongoDB (v1) | Can migrate to OLAP later |
| Idempotency | Event ID + entity version | Handles replays, late arrivals |
| DLQ strategy | Dedicated topic per group | Easy debugging, retry flexibility |

---

## Next: Task 2 — Topic & Event Catalog

Task 2 will deliver:
- Final topic list with naming
- All event types per topic
- Partition keys and retention
- Event catalog documentation
