# Task 7: Projections (Read Models)

## 1. Projection Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PROJECTION ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         KAFKA TOPICS                                  │  │
│  │                                                                       │  │
│  │   sc.domain.user   sc.domain.post   sc.domain.order   sc.domain.*    │  │
│  │         │                │                │                │         │  │
│  └─────────┼────────────────┼────────────────┼────────────────┼─────────┘  │
│            │                │                │                │            │
│            ▼                ▼                ▼                ▼            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    PROJECTION CONSUMERS                               │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ UserCards       │  │ FeedBuilder     │  │ OrderSummary    │       │  │
│  │  │ Consumer        │  │ Consumer        │  │ Consumer        │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ group:          │  │ group:          │  │ group:          │       │  │
│  │  │ sc-proj-user-   │  │ sc-proj-feed-   │  │ sc-proj-order-  │       │  │
│  │  │ cards           │  │ builder         │  │ summaries       │       │  │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘       │  │
│  │           │                    │                    │                 │  │
│  └───────────┼────────────────────┼────────────────────┼─────────────────┘  │
│              │                    │                    │                    │
│              ▼                    ▼                    ▼                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      READ MODELS (MongoDB)                            │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │   user_cards    │  │   feed_items    │  │ order_summaries │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │  Optimized for  │  │  Unified feed   │  │  Customer order │       │  │
│  │  │  user card      │  │  posts +        │  │  history views  │       │  │
│  │  │  display        │  │  promotions     │  │                 │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Read Models

### user_cards

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER CARDS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Fast rendering of user profile cards                               │
│                                                                             │
│  FIELDS:                                                                     │
│  ├── user_id (unique)                                                       │
│  ├── display_name, avatar_url, bio                                          │
│  ├── role, status                                                           │
│  ├── follower_count, following_count                                        │
│  ├── total_orders, communities_joined                                       │
│  └── entity_version (idempotency)                                           │
│                                                                             │
│  INDEXES:                                                                    │
│  ├── (user_id) UNIQUE                                                       │
│  ├── (status, created_at DESC)                                              │
│  ├── (role)                                                                 │
│  └── (follower_count DESC)                                                  │
│                                                                             │
│  EVENTS CONSUMED:                                                            │
│  ├── user.created → Create card                                             │
│  ├── user.verified → Update status                                          │
│  ├── user.profile_updated → Update display fields                           │
│  ├── user.role_changed → Update role                                        │
│  ├── user.suspended/reactivated → Update status                             │
│  └── user.stats_changed → Update counters                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### feed_items

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FEED ITEMS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Unified feed for posts and promotions                              │
│                                                                             │
│  FIELDS:                                                                     │
│  ├── item_type (post | promotion)                                           │
│  ├── source_id (post or promotion ID)                                       │
│  ├── author_id, community_id                                                │
│  ├── content_type                                                           │
│  ├── is_global, is_pinned                                                   │
│  ├── status (draft | published | hidden | deleted)                          │
│  ├── view_count, like_count, comment_count                                  │
│  └── entity_version (idempotency)                                           │
│                                                                             │
│  INDEXES:                                                                    │
│  ├── (source_id, item_type) UNIQUE                                          │
│  ├── (is_global, status, published_at DESC) - Global feed                   │
│  ├── (community_id, status, published_at DESC) - Community feed             │
│  ├── (author_id, status, published_at DESC) - User feed                     │
│  └── (community_id, is_pinned) - Pinned items                               │
│                                                                             │
│  EVENTS CONSUMED:                                                            │
│  ├── post.created → Create item                                             │
│  ├── post.published → Update status                                         │
│  ├── post.global_approved → Set is_global                                   │
│  ├── post.pinned/unpinned → Update is_pinned                                │
│  ├── post.stats_changed → Update counters                                   │
│  ├── promotion.created → Create item                                        │
│  └── promotion.activated/ended → Update status                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### order_summaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORDER SUMMARIES                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Fast customer order history queries                                │
│                                                                             │
│  FIELDS:                                                                     │
│  ├── order_id (unique), order_number                                        │
│  ├── customer_id                                                            │
│  ├── item_count, total_cents, currency                                      │
│  ├── status, payment_status                                                 │
│  ├── items[] (embedded snapshots)                                           │
│  ├── promotion_id, community_id (attribution)                               │
│  ├── created_at, confirmed_at, shipped_at, delivered_at                     │
│  └── entity_version (idempotency)                                           │
│                                                                             │
│  INDEXES:                                                                    │
│  ├── (order_id) UNIQUE                                                      │
│  ├── (order_number)                                                         │
│  ├── (customer_id, created_at DESC) - Order history                         │
│  ├── (status, created_at DESC)                                              │
│  └── (items.supplier_id, items.status) - Supplier queue                     │
│                                                                             │
│  EVENTS CONSUMED:                                                            │
│  ├── order.created → Create summary                                         │
│  ├── order.payment_succeeded/failed → Update payment_status                 │
│  ├── order.confirmed → Set confirmed_at, store item snapshots               │
│  ├── order.status_changed → Update status                                   │
│  ├── order.item_shipped/delivered → Update item status                      │
│  ├── order.cancelled → Set cancelled_at                                     │
│  └── order.attribution_recorded → Set attribution fields                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Version-Based Idempotency

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     VERSION-BASED IDEMPOTENCY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Each read model tracks entity_version to handle:                            │
│  • Duplicate event delivery                                                  │
│  • Out-of-order events                                                       │
│  • Consumer restarts                                                         │
│                                                                             │
│  PROCESSING LOGIC:                                                           │
│                                                                             │
│    1. Fetch existing document                                                │
│    2. Compare incoming entity_version vs stored entity_version              │
│    3. Skip if incoming <= stored (already processed or stale)               │
│    4. Apply changes and update entity_version                               │
│                                                                             │
│                                                                             │
│  EXAMPLE:                                                                    │
│                                                                             │
│    Stored: { user_id: "123", entity_version: 5 }                            │
│                                                                             │
│    Event arrives: { entity_id: "123", entity_version: 4 }                   │
│    → Skip (4 <= 5, already processed newer version)                         │
│                                                                             │
│    Event arrives: { entity_id: "123", entity_version: 6 }                   │
│    → Process and update entity_version to 6                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Files

```
kafka/projections/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── user_card.py          # UserCard read model
│   ├── feed_item.py          # FeedItem read model
│   └── order_summary.py      # OrderSummary read model
└── consumers/
    ├── __init__.py
    ├── user_cards.py         # UserCardsConsumer
    ├── feed_builder.py       # FeedBuilderConsumer
    └── order_summary.py      # OrderSummaryConsumer
```
