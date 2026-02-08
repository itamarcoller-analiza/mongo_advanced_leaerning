# Task 3: Schema Definitions

## 1. Schema Files Structure

```
kafka/events/schemas/
├── __init__.py          # Empty
├── base.py              # EventEnvelope, Actor, PrivacyTier, EntityType
├── user.py              # User domain event payloads
├── supplier.py          # Supplier domain event payloads
├── community.py         # Community domain event payloads
├── product.py           # Product domain event payloads
├── promotion.py         # Promotion domain event payloads
├── post.py              # Post domain event payloads
└── order.py             # Order domain event payloads
```

---

## 2. Event Schema Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT SCHEMA ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      EventEnvelope<T>                                 │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  IDENTIFICATION                                                 │  │  │
│  │  │  ───────────────                                                │  │  │
│  │  │  event_id: UUID ─────────────► Unique per event                 │  │  │
│  │  │  event_type: str ────────────► "user.created", "order.confirmed"│  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  ENTITY CONTEXT                                                 │  │  │
│  │  │  ──────────────                                                 │  │  │
│  │  │  entity_type: EntityType ────► user│supplier│community│...      │  │  │
│  │  │  entity_id: str ─────────────► MongoDB ObjectId                 │  │  │
│  │  │  entity_version: int ────────► Optimistic lock (ordering)       │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  TRACING                                                        │  │  │
│  │  │  ───────                                                        │  │  │
│  │  │  occurred_at: datetime ──────► When it happened (UTC)           │  │  │
│  │  │  trace_id: UUID? ────────────► Distributed trace                │  │  │
│  │  │  correlation_id: UUID? ──────► Links related events             │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  METADATA                                                       │  │  │
│  │  │  ────────                                                       │  │  │
│  │  │  producer: str ──────────────► "social-commerce-api"            │  │  │
│  │  │  actor: Actor ───────────────► Who/what triggered               │  │  │
│  │  │  schema_version: int ────────► For evolution                    │  │  │
│  │  │  privacy_tier: PrivacyTier ──► public│internal│restricted       │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PAYLOAD                                                        │  │  │
│  │  │  ───────                                                        │  │  │
│  │  │  data: T ────────────────────► Generic event-specific payload   │  │  │
│  │  └──────────────────────────────────────┬──────────────────────────┘  │  │
│  │                                         │                             │  │
│  └─────────────────────────────────────────┼─────────────────────────────┘  │
│                                            │                                │
│                                            │ T extends BaseEventPayload     │
│                                            ▼                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     DOMAIN PAYLOADS                                   │  │
│  │                                                                       │  │
│  │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │  │
│  │   │    USER     │ │  SUPPLIER   │ │  COMMUNITY  │ │   PRODUCT   │    │  │
│  │   │             │ │             │ │             │ │             │    │  │
│  │   │ Created     │ │ Created     │ │ Created     │ │ Created     │    │  │
│  │   │ Verified    │ │ Verified    │ │ Updated     │ │ Published   │    │  │
│  │   │ Updated     │ │ Rejected    │ │ MemberJoined│ │ PriceChanged│    │  │
│  │   │ Suspended   │ │ Suspended   │ │ MemberLeft  │ │ Inventory*  │    │  │
│  │   │ Deleted     │ │ StatsChanged│ │ Deleted     │ │ Deleted     │    │  │
│  │   │ RoleChanged │ │             │ │             │ │             │    │  │
│  │   │ StatsChanged│ │             │ │             │ │             │    │  │
│  │   │ Login*      │ │             │ │             │ │             │    │  │
│  │   │ Locked      │ │             │ │             │ │             │    │  │
│  │   └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │  │
│  │                                                                       │  │
│  │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                    │  │
│  │   │  PROMOTION  │ │    POST     │ │    ORDER    │                    │  │
│  │   │             │ │             │ │             │                    │  │
│  │   │ Created     │ │ Created     │ │ Created     │                    │  │
│  │   │ Submitted   │ │ Published   │ │ Payment*    │                    │  │
│  │   │ Approved*   │ │ Updated     │ │ Confirmed   │                    │  │
│  │   │ Rejected*   │ │ Global*     │ │ ItemShipped │                    │  │
│  │   │ Scheduled   │ │ Pinned      │ │ ItemDelivered│                   │  │
│  │   │ Activated   │ │ Hidden      │ │ StatusChanged│                   │  │
│  │   │ Paused      │ │ Deleted     │ │ Cancelled   │                    │  │
│  │   │ Ended       │ │ StatsChanged│ │ Attribution │                    │  │
│  │   │ Impression  │ │             │ │             │                    │  │
│  │   │ Clicked     │ │             │ │             │                    │  │
│  │   │ Converted   │ │             │ │             │                    │  │
│  │   └─────────────┘ └─────────────┘ └─────────────┘                    │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Actor Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ACTOR MODEL                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHO OR WHAT TRIGGERED THE EVENT?                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Actor                                                              │    │
│  │  ─────                                                              │    │
│  │  actor_type: ActorType                                              │    │
│  │  actor_id: str? ────────► null for system/scheduler                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────┬──────────────────────────────────────────────────────┐    │
│  │ ActorType   │  Usage                                               │    │
│  ├─────────────┼──────────────────────────────────────────────────────┤    │
│  │ USER        │  Consumer or Leader triggered action                 │    │
│  │ SUPPLIER    │  Supplier triggered action                           │    │
│  │ ADMIN       │  Admin/moderator triggered action                    │    │
│  │ SYSTEM      │  Automated system process                            │    │
│  │ SCHEDULER   │  Scheduled job (e.g., promotion activation)          │    │
│  └─────────────┴──────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Privacy Tiers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRIVACY TIERS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    ┌─────────────────────────────────┐                      │
│                    │           PUBLIC                │                      │
│                    │                                 │                      │
│                    │  • No PII whatsoever            │                      │
│                    │  • Aggregates, names, stats     │                      │
│                    │  • Safe for consumer APIs       │                      │
│                    │                                 │                      │
│                    │  Consumers:                     │                      │
│                    │  → Consumer projections         │                      │
│                    │  → Public APIs                  │                      │
│                    │  → CDN/cache                    │                      │
│                    └─────────────────────────────────┘                      │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌─────────────────────────────────┐                      │
│                    │          INTERNAL               │                      │
│                    │                                 │                      │
│                    │  • Internal IDs allowed         │                      │
│                    │  • Business metrics             │                      │
│                    │  • NO email/phone/IP            │                      │
│                    │                                 │                      │
│                    │  Consumers:                     │                      │
│                    │  → Admin projections            │                      │
│                    │  → Internal dashboards          │                      │
│                    │  → Audit systems                │                      │
│                    └─────────────────────────────────┘                      │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌─────────────────────────────────┐                      │
│                    │         RESTRICTED              │                      │
│                    │                                 │                      │
│                    │  • PII allowed                  │                      │
│                    │  • Security events              │                      │
│                    │  • Raw audit data               │                      │
│                    │                                 │                      │
│                    │  Consumers:                     │                      │
│                    │  → Compliance only              │                      │
│                    │  → Legal hold                   │                      │
│                    │  → Encrypted storage            │                      │
│                    └─────────────────────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Schema Evolution Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SCHEMA EVOLUTION                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ALLOWED (Backward Compatible)              DISALLOWED (Breaking)           │
│  ═════════════════════════════              ═════════════════════           │
│                                                                             │
│  ✓ Add optional field with default          ✗ Remove field                  │
│  ✓ Add new event type                       ✗ Rename field                  │
│  ✓ Add new enum value                       ✗ Change field type             │
│  ✓ Relax validation                         ✗ Make optional → required      │
│  ✓ Make required → optional                 ✗ Remove enum value             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  VERSION STRATEGY:                                                          │
│                                                                             │
│  schema_version: 1 ──► Initial schema                                       │
│  schema_version: 2 ──► Added optional fields                                │
│  schema_version: 3 ──► Added new event types                                │
│                                                                             │
│  Consumers MUST:                                                            │
│  • Handle unknown fields gracefully (ignore)                                │
│  • Handle unknown event_types (log + skip)                                  │
│  • Handle missing optional fields (use defaults)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Validation Rules

| Field Pattern | Validation |
|---------------|------------|
| `event_type` | Regex: `^[a-z]+\.[a-z_]+$` |
| `entity_version` | Integer `>= 1` |
| `schema_version` | Integer `>= 1` |
| `*_cents` | Integer `>= 0` |
| `*_count` | Integer `>= 0` |
| `*_at` | ISO 8601 UTC datetime |
