# Task 2: Topic & Event Catalog

## 1. Topic Naming Convention

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TOPIC NAMING CONVENTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PATTERN: sc.<category>.<entity>[.<qualifier>]                              │
│                                                                             │
│  PREFIX: sc = social commerce                                               │
│                                                                             │
│  CATEGORIES:                                                                │
│  ───────────────────────────────────────────────────────────────────────    │
│  domain       │  Canonical events (source of truth)                         │
│  proj         │  Derived projection events                                  │
│  analytics    │  Analytics-optimized events                                 │
│  dlq          │  Dead letter queues                                         │
│  retry        │  Retry queues (v2)                                          │
│  internal     │  System/infrastructure events                               │
│                                                                             │
│  EXAMPLES:                                                                  │
│  ───────────────────────────────────────────────────────────────────────    │
│  sc.domain.user              │  User domain events                          │
│  sc.proj.consumer.feed       │  Consumer feed projections                   │
│  sc.analytics.admin.revenue  │  Admin revenue analytics                     │
│  sc.dlq.proj-feed-builder    │  DLQ for feed builder consumer               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Topic List

### 2.1 Domain Topics (Source of Truth)

| Topic | Partitions | Key | Retention | Description |
|-------|------------|-----|-----------|-------------|
| `sc.domain.user` | 3 | `user_id` | 14 days | All user lifecycle events |
| `sc.domain.supplier` | 3 | `supplier_id` | 14 days | All supplier lifecycle events |
| `sc.domain.community` | 3 | `community_id` | 14 days | Community and membership events |
| `sc.domain.product` | 3 | `product_id` | 14 days | Product catalog events |
| `sc.domain.promotion` | 3 | `promotion_id` | 14 days | Promotion lifecycle events |
| `sc.domain.post` | 3 | `post_id` | 14 days | Post content events |
| `sc.domain.order` | 6 | `order_id` | 30 days | Order transaction events |

### 2.2 Consumer Projection Topics

| Topic | Partitions | Key | Retention | Description |
|-------|------------|-----|-----------|-------------|
| `sc.proj.consumer.user-cards` | 3 | `user_id` | 7 days | Materialized user display cards |
| `sc.proj.consumer.supplier-cards` | 3 | `supplier_id` | 7 days | Materialized supplier store cards |
| `sc.proj.consumer.community-cards` | 3 | `community_id` | 7 days | Materialized community cards |
| `sc.proj.consumer.product-listings` | 3 | `product_id` | 7 days | Product listing cards |
| `sc.proj.consumer.promotion-cards` | 3 | `promotion_id` | 7 days | Promotion display cards |
| `sc.proj.consumer.feed-global` | 6 | `feed_item_id` | 7 days | Global feed items |
| `sc.proj.consumer.feed-community` | 6 | `community_id` | 7 days | Per-community feed items |
| `sc.proj.consumer.order-summaries` | 3 | `order_id` | 7 days | Order summary cards |

### 2.3 Admin Analytics Topics

| Topic | Partitions | Key | Retention | Description |
|-------|------------|-----|-----------|-------------|
| `sc.analytics.admin.user-lifecycle` | 6 | `user_id` | 30 days | User state transitions |
| `sc.analytics.admin.user-security` | 3 | `user_id` | 30 days | Security audit events |
| `sc.analytics.admin.supplier-verification` | 3 | `supplier_id` | 30 days | Verification audit trail |
| `sc.analytics.admin.supplier-fulfillment` | 6 | `supplier_id` | 30 days | Fulfillment SLA metrics |
| `sc.analytics.admin.community-growth` | 6 | `community_id` | 30 days | Community growth metrics |
| `sc.analytics.admin.community-moderation` | 3 | `community_id` | 30 days | Moderation actions |
| `sc.analytics.admin.product-catalog` | 6 | `product_id` | 30 days | Catalog health metrics |
| `sc.analytics.admin.promotion-lifecycle` | 6 | `promotion_id` | 30 days | Promotion audit trail |
| `sc.analytics.admin.promotion-performance` | 6 | `promotion_id` | 90 days | Performance attribution |
| `sc.analytics.admin.post-distribution` | 6 | `post_id` | 30 days | Distribution audit |
| `sc.analytics.admin.order-funnel` | 6 | `order_id` | 90 days | Order funnel metrics |
| `sc.analytics.admin.revenue` | 6 | `order_id` | 90 days | Revenue attribution |

### 2.4 Infrastructure Topics

| Topic | Partitions | Key | Retention | Description |
|-------|------------|-----|-----------|-------------|
| `sc.dlq.proj-user-cards` | 1 | `event_id` | 7 days | Failed user card projections |
| `sc.dlq.proj-feed-builder` | 1 | `event_id` | 7 days | Failed feed builds |
| `sc.dlq.proj-order-summaries` | 1 | `event_id` | 7 days | Failed order summaries |
| `sc.dlq.analytics-general` | 1 | `event_id` | 7 days | Failed analytics processing |
| `sc.internal.heartbeat` | 1 | - | 1 day | System health checks |

---

## 3. Event Types Catalog

### 3.1 User Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.user                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE              │  TRIGGER                │  KEY PAYLOAD FIELDS    │
│  ════════════════════════│═════════════════════════│════════════════════════│
│                          │                         │                        │
│  user.created            │  Registration complete  │  user_id               │
│                          │                         │  role                  │
│                          │                         │  status (pending)      │
│                          │                         │  created_at            │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.verified           │  Email verified         │  user_id               │
│                          │                         │  previous_status       │
│                          │                         │  new_status (active)   │
│                          │                         │  verified_at           │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.profile_updated    │  Profile fields changed │  user_id               │
│                          │                         │  changed_fields[]      │
│                          │                         │  display_name          │
│                          │                         │  avatar_url            │
│                          │                         │  bio                   │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.role_changed       │  Consumer ↔ Leader      │  user_id               │
│                          │                         │  previous_role         │
│                          │                         │  new_role              │
│                          │                         │  reason                │
│                          │                         │  actor_id              │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.suspended          │  Account suspended      │  user_id               │
│                          │                         │  reason                │
│                          │                         │  suspended_by          │
│                          │                         │  suspended_until       │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.reactivated        │  Suspension lifted      │  user_id               │
│                          │                         │  reactivated_by        │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.deleted            │  Soft delete            │  user_id               │
│                          │                         │  deleted_by            │
│                          │                         │  reason                │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.stats_changed      │  Counter updates        │  user_id               │
│                          │  (followers, orders)    │  stat_type             │
│                          │                         │  previous_value        │
│                          │                         │  new_value             │
│                          │                         │  delta                 │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.login_succeeded    │  Successful login       │  user_id               │
│                          │  (security audit)       │  login_method          │
│                          │                         │  # NO IP (privacy)     │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.login_failed       │  Failed login           │  user_id (if known)    │
│                          │  (security audit)       │  failure_reason        │
│                          │                         │  attempt_count         │
│                          │                         │                        │
│  ────────────────────────│─────────────────────────│────────────────────────│
│                          │                         │                        │
│  user.locked             │  Account locked         │  user_id               │
│                          │  (too many failures)    │  locked_until          │
│                          │                         │  trigger_reason        │
│                          │                         │                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Supplier Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.supplier                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  supplier.created            │  Registration         │  supplier_id         │
│                              │                       │  company_name        │
│                              │                       │  status              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.verification       │  Docs submitted       │  supplier_id         │
│  _submitted                  │                       │  documents_types[]   │
│                              │                       │  submitted_at        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.verified           │  Admin approved       │  supplier_id         │
│                              │                       │  verified_by         │
│                              │                       │  verification_tier   │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.verification       │  Admin rejected       │  supplier_id         │
│  _rejected                   │                       │  rejected_by         │
│                              │                       │  rejection_reasons[] │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.profile_updated    │  Profile changed      │  supplier_id         │
│                              │                       │  changed_fields[]    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.suspended          │  Account suspended    │  supplier_id         │
│                              │                       │  reason              │
│                              │                       │  suspended_by        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  supplier.stats_changed      │  Counter updates      │  supplier_id         │
│                              │                       │  stat_type           │
│                              │                       │  delta               │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Community Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.community                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  community.created           │  Leader creates       │  community_id        │
│                              │                       │  owner_id            │
│                              │                       │  name                │
│                              │                       │  visibility          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.updated           │  Settings changed     │  community_id        │
│                              │                       │  changed_fields[]    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.visibility        │  Public ↔ Private     │  community_id        │
│  _changed                    │                       │  previous_visibility │
│                              │                       │  new_visibility      │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.member_joined     │  User joins           │  community_id        │
│                              │                       │  user_id             │
│                              │                       │  join_method         │
│                              │                       │  member_count_after  │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.member_left       │  User leaves          │  community_id        │
│                              │                       │  user_id             │
│                              │                       │  member_count_after  │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.member_removed    │  Leader removes       │  community_id        │
│                              │                       │  user_id             │
│                              │                       │  removed_by          │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.deleted           │  Soft delete          │  community_id        │
│                              │                       │  deleted_by          │
│                              │                       │  member_count_at_del │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  community.stats_changed     │  Counter updates      │  community_id        │
│                              │                       │  stat_type           │
│                              │                       │  delta               │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Product Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.product                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  product.created             │  Supplier creates     │  product_id          │
│                              │                       │  supplier_id         │
│                              │                       │  name                │
│                              │                       │  category            │
│                              │                       │  status (draft)      │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.updated             │  Details changed      │  product_id          │
│                              │                       │  changed_fields[]    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.published           │  Made visible         │  product_id          │
│                              │                       │  published_at        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.unpublished         │  Hidden from listing  │  product_id          │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.price_changed       │  Price modified       │  product_id          │
│                              │                       │  variant_id (opt)    │
│                              │                       │  previous_price      │
│                              │                       │  new_price           │
│                              │                       │  currency            │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.inventory_adjusted  │  Stock changed        │  product_id          │
│                              │                       │  variant_id          │
│                              │                       │  location_id         │
│                              │                       │  previous_qty        │
│                              │                       │  new_qty             │
│                              │                       │  adjustment_type     │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.inventory_reserved  │  Stock reserved       │  product_id          │
│                              │  (for pending order)  │  variant_id          │
│                              │                       │  order_id            │
│                              │                       │  reserved_qty        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.inventory_released  │  Reserved released    │  product_id          │
│                              │  (order cancelled)    │  variant_id          │
│                              │                       │  order_id            │
│                              │                       │  released_qty        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.variant_added       │  New variant          │  product_id          │
│                              │                       │  variant_id          │
│                              │                       │  variant_name        │
│                              │                       │  attributes          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  product.deleted             │  Soft delete          │  product_id          │
│                              │                       │  reason              │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.5 Promotion Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.promotion                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  promotion.created           │  Supplier creates     │  promotion_id        │
│                              │                       │  supplier_id         │
│                              │                       │  promotion_type      │
│                              │                       │  title               │
│                              │                       │  visibility_type     │
│                              │                       │  community_ids[]     │
│                              │                       │  product_ids[]       │
│                              │                       │  status (draft)      │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.submitted         │  Submitted for        │  promotion_id        │
│                              │  approval             │  submitted_at        │
│                              │                       │  requires_admin      │
│                              │                       │  requires_leaders[]  │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.approved_admin    │  Admin approved       │  promotion_id        │
│                              │  global visibility    │  approved_by         │
│                              │                       │  notes               │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.approved_leader   │  Leader approved      │  promotion_id        │
│                              │  for their community  │  community_id        │
│                              │                       │  approved_by         │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.rejected_admin    │  Admin rejected       │  promotion_id        │
│                              │                       │  rejected_by         │
│                              │                       │  rejection_reason    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.rejected_leader   │  Leader rejected      │  promotion_id        │
│                              │                       │  community_id        │
│                              │                       │  rejected_by         │
│                              │                       │  rejection_reason    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.scheduled         │  Approved, future     │  promotion_id        │
│                              │  start date           │  scheduled_start     │
│                              │                       │  scheduled_end       │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.activated         │  Goes live            │  promotion_id        │
│                              │  (IMMUTABLE MARKER)   │  first_activated_at  │
│                              │                       │  visibility_scope    │
│                              │                       │  community_ids[]     │
│                              │                       │  products_snapshot   │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.paused            │  Supplier pauses      │  promotion_id        │
│                              │                       │  paused_by           │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.resumed           │  Supplier resumes     │  promotion_id        │
│                              │                       │  resumed_by          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.ended             │  End date reached     │  promotion_id        │
│                              │  or manually ended    │  end_reason          │
│                              │                       │  final_stats         │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.cancelled         │  Supplier cancels     │  promotion_id        │
│                              │                       │  cancelled_by        │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.impression        │  User viewed          │  promotion_id        │
│                              │  (high volume)        │  community_id (opt)  │
│                              │                       │  feed_type           │
│                              │                       │  # Batched/sampled   │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.clicked           │  User clicked         │  promotion_id        │
│                              │                       │  community_id (opt)  │
│                              │                       │  product_id          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  promotion.converted         │  Purchase attributed  │  promotion_id        │
│                              │                       │  order_id            │
│                              │                       │  community_id (opt)  │
│                              │                       │  revenue_cents       │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Post Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.post                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  post.created                │  Author creates       │  post_id             │
│                              │                       │  author_id           │
│                              │                       │  community_id        │
│                              │                       │  post_type           │
│                              │                       │  status              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.published              │  Made visible         │  post_id             │
│                              │                       │  published_at        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.updated                │  Content edited       │  post_id             │
│                              │                       │  changed_fields[]    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.global_requested       │  Author requests      │  post_id             │
│                              │  global distribution  │  requested_at        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.global_approved        │  Admin approved       │  post_id             │
│                              │                       │  approved_by         │
│                              │                       │  approved_at         │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.global_rejected        │  Admin rejected       │  post_id             │
│                              │                       │  rejected_by         │
│                              │                       │  rejection_reason    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.pinned                 │  Leader pins          │  post_id             │
│                              │                       │  pinned_by           │
│                              │                       │  community_id        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.unpinned               │  Leader unpins        │  post_id             │
│                              │                       │  unpinned_by         │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.hidden                 │  Moderation hide      │  post_id             │
│                              │                       │  hidden_by           │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.deleted                │  Soft delete          │  post_id             │
│                              │                       │  deleted_by          │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  post.stats_changed          │  Engagement updated   │  post_id             │
│                              │  (likes, comments)    │  stat_type           │
│                              │                       │  delta               │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.7 Order Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOPIC: sc.domain.order                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EVENT TYPE                  │  TRIGGER              │  KEY PAYLOAD FIELDS  │
│  ════════════════════════════│═══════════════════════│══════════════════════│
│                              │                       │                      │
│  order.created               │  Checkout initiated   │  order_id            │
│                              │                       │  order_number        │
│                              │                       │  customer_id         │
│                              │                       │  item_count          │
│                              │                       │  total_cents         │
│                              │                       │  currency            │
│                              │                       │  status (pending)    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.payment_initiated     │  Payment started      │  order_id            │
│                              │                       │  payment_method      │
│                              │                       │  amount_cents        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.payment_succeeded     │  Payment captured     │  order_id            │
│                              │                       │  transaction_id      │
│                              │                       │  amount_cents        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.payment_failed        │  Payment rejected     │  order_id            │
│                              │                       │  failure_reason      │
│                              │                       │  failure_code        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.confirmed             │  Payment complete,    │  order_id            │
│                              │  order locked         │  confirmed_at        │
│                              │                       │  item_snapshots[]    │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.item_processing       │  Supplier started     │  order_id            │
│                              │  fulfillment          │  item_id             │
│                              │                       │  supplier_id         │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.item_shipped          │  Item shipped         │  order_id            │
│                              │                       │  item_id             │
│                              │                       │  supplier_id         │
│                              │                       │  tracking_number     │
│                              │                       │  carrier             │
│                              │                       │  shipped_at          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.item_delivered        │  Item delivered       │  order_id            │
│                              │                       │  item_id             │
│                              │                       │  delivered_at        │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.status_changed        │  Aggregate status     │  order_id            │
│                              │  transition           │  previous_status     │
│                              │                       │  new_status          │
│                              │                       │  changed_at          │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.cancelled             │  Order cancelled      │  order_id            │
│                              │                       │  cancelled_by        │
│                              │                       │  reason              │
│                              │                       │  refund_amount       │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.refund_initiated      │  Refund started       │  order_id            │
│                              │  (future)             │  refund_amount       │
│                              │                       │  reason              │
│                              │                       │                      │
│  ──────────────────────────────────────────────────────────────────────────│
│                              │                       │                      │
│  order.attribution_recorded  │  Attribution          │  order_id            │
│                              │  snapshot captured    │  promotion_id        │
│                              │                       │  community_id        │
│                              │                       │  leader_id           │
│                              │                       │  supplier_id         │
│                              │                       │  utm_source          │
│                              │                       │  utm_campaign        │
│                              │                       │                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Partition Key Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PARTITION KEY STRATEGY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRINCIPLE: Events for the same entity must be in the same partition        │
│             to guarantee ordering.                                          │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  TOPIC CATEGORY        │  PARTITION KEY          │  RATIONALE              │
│  ══════════════════════│═════════════════════════│═════════════════════════│
│                        │                         │                         │
│  Domain topics         │  entity_id              │  Order per entity       │
│  (sc.domain.*)         │  (user_id, order_id,    │  guaranteed             │
│                        │   etc.)                 │                         │
│                        │                         │                         │
│  ──────────────────────│─────────────────────────│─────────────────────────│
│                        │                         │                         │
│  Consumer projections  │  Same as domain         │  Maintain ordering      │
│  (sc.proj.consumer.*)  │                         │  from source            │
│                        │                         │                         │
│  ──────────────────────│─────────────────────────│─────────────────────────│
│                        │                         │                         │
│  Analytics topics      │  Depends on query       │  Optimize for           │
│  (sc.analytics.*)      │  pattern:               │  aggregation pattern    │
│                        │                         │                         │
│                        │  Revenue by community:  │                         │
│                        │    key = community_id   │                         │
│                        │                         │                         │
│                        │  Order funnel:          │                         │
│                        │    key = order_id       │                         │
│                        │                         │                         │
│                        │  Promotion perf:        │                         │
│                        │    key = promotion_id   │                         │
│                        │                         │                         │
│  ──────────────────────│─────────────────────────│─────────────────────────│
│                        │                         │                         │
│  DLQ topics            │  event_id               │  Arbitrary, just need   │
│  (sc.dlq.*)            │                         │  persistence            │
│                        │                         │                         │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  HOT PARTITION MITIGATION (future):                                         │
│                                                                             │
│  If single entity gets very high volume (viral post, mega promotion):       │
│  1. High-volume events (impressions) can use compound key:                  │
│     key = f"{promotion_id}_{timestamp_bucket}"                              │
│  2. Accept out-of-order for impressions (they're sampled anyway)            │
│  3. Keep strict ordering only for state-change events                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Retention Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RETENTION CONFIGURATION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TOPIC CATEGORY        │  RETENTION    │  RATIONALE                         │
│  ══════════════════════│═══════════════│═════════════════════════════════════
│                        │               │                                    │
│  Domain topics         │  14 days      │  Long enough to replay for         │
│  (sc.domain.*)         │               │  debugging, rebuild projections    │
│                        │               │  on consumer failure               │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  Order domain          │  30 days      │  Longer for order issues,          │
│  (sc.domain.order)     │               │  payment disputes                  │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  Consumer projections  │  7 days       │  Rebuildable from domain           │
│  (sc.proj.consumer.*)  │               │  topics if needed                  │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  Analytics topics      │  30-90 days   │  Historical analysis needs,        │
│  (sc.analytics.*)      │               │  but prefer sink to OLAP           │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  Revenue/attribution   │  90 days      │  Financial reporting,              │
│                        │               │  dispute resolution                │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  DLQ topics            │  7 days       │  Investigation window              │
│  (sc.dlq.*)            │               │                                    │
│                        │               │                                    │
│  ──────────────────────│───────────────│────────────────────────────────────│
│                        │               │                                    │
│  Heartbeat             │  1 day        │  Only for liveness check           │
│  (sc.internal.*)       │               │                                    │
│                        │               │                                    │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  COMPACTION POLICY:                                                         │
│                                                                             │
│  All topics use: cleanup.policy = delete (time-based retention)             │
│                                                                             │
│  NOT using compaction because:                                              │
│  - Events are immutable facts, not state                                    │
│  - Need full history for replay/rebuild                                     │
│  - Analytics needs all events, not just latest per key                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Topic Creation Script Reference

```bash
# Domain topics
kafka-topics.sh --create --topic sc.domain.user --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.supplier --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.community --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.product --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.promotion --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.post --partitions 3 --replication-factor 1 --config retention.ms=1209600000
kafka-topics.sh --create --topic sc.domain.order --partitions 6 --replication-factor 1 --config retention.ms=2592000000

# Consumer projection topics
kafka-topics.sh --create --topic sc.proj.consumer.user-cards --partitions 3 --replication-factor 1 --config retention.ms=604800000
kafka-topics.sh --create --topic sc.proj.consumer.feed-global --partitions 6 --replication-factor 1 --config retention.ms=604800000
kafka-topics.sh --create --topic sc.proj.consumer.feed-community --partitions 6 --replication-factor 1 --config retention.ms=604800000

# Analytics topics
kafka-topics.sh --create --topic sc.analytics.admin.order-funnel --partitions 6 --replication-factor 1 --config retention.ms=7776000000
kafka-topics.sh --create --topic sc.analytics.admin.revenue --partitions 6 --replication-factor 1 --config retention.ms=7776000000
kafka-topics.sh --create --topic sc.analytics.admin.promotion-performance --partitions 6 --replication-factor 1 --config retention.ms=7776000000

# DLQ topics
kafka-topics.sh --create --topic sc.dlq.proj-feed-builder --partitions 1 --replication-factor 1 --config retention.ms=604800000
kafka-topics.sh --create --topic sc.dlq.analytics-general --partitions 1 --replication-factor 1 --config retention.ms=604800000
```

---

## Next: Task 3 — Schema Definitions

Task 3 will deliver:
- Pydantic models for event envelope
- Per-entity event payload schemas
- Validation rules and privacy tiers
- Example JSON events
