# Task 8: Analytics Pipeline

## 1. Analytics Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ANALYTICS ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         KAFKA TOPICS                                  │  │
│  │                                                                       │  │
│  │         sc.domain.user                   sc.domain.order              │  │
│  │              │                                │                       │  │
│  └──────────────┼────────────────────────────────┼───────────────────────┘  │
│                 │                                │                          │
│                 ▼                                ▼                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    ANALYTICS CONSUMERS                                │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ UserLifecycle   │  │ OrderFunnel     │  │ Revenue         │       │  │
│  │  │ Consumer        │  │ Consumer        │  │ Consumer        │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ group:          │  │ group:          │  │ group:          │       │  │
│  │  │ sc-analytics-   │  │ sc-analytics-   │  │ sc-analytics-   │       │  │
│  │  │ user-lifecycle  │  │ order-funnel    │  │ revenue         │       │  │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘       │  │
│  │           │                    │                    │                 │  │
│  └───────────┼────────────────────┼────────────────────┼─────────────────┘  │
│              │                    │                    │                    │
│              ▼                    ▼                    ▼                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   ANALYTICS MODELS (MongoDB)                          │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ analytics_user_ │  │ analytics_order_│  │ analytics_      │       │  │
│  │  │ lifecycle       │  │ funnel          │  │ revenue         │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ Daily user      │  │ Daily order     │  │ Daily revenue   │       │  │
│  │  │ registration,   │  │ conversion      │  │ totals and      │       │  │
│  │  │ churn metrics   │  │ funnel metrics  │  │ attribution     │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Analytics Models

### analytics_user_lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      USER LIFECYCLE DAILY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Daily user registration and churn metrics                          │
│                                                                             │
│  FIELDS:                                                                     │
│  ├── date (unique)                                                          │
│  ├── registrations, verifications, verification_rate                        │
│  ├── leaders_promoted, leaders_demoted                                      │
│  ├── suspensions, reactivations, deletions                                  │
│  └── login_successes, login_failures, accounts_locked                       │
│                                                                             │
│  EVENTS CONSUMED:                                                            │
│  ├── user.created → registrations++                                         │
│  ├── user.verified → verifications++                                        │
│  ├── user.role_changed → leaders_promoted++ or leaders_demoted++            │
│  ├── user.suspended → suspensions++                                         │
│  ├── user.reactivated → reactivations++                                     │
│  ├── user.deleted → deletions++                                             │
│  ├── user.login_succeeded → login_successes++                               │
│  ├── user.login_failed → login_failures++                                   │
│  └── user.locked → accounts_locked++                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### analytics_order_funnel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ORDER FUNNEL DAILY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Daily order conversion funnel metrics                              │
│                                                                             │
│  FUNNEL STAGES:                                                              │
│                                                                             │
│    orders_created                                                            │
│         │                                                                    │
│         ▼                                                                    │
│    payments_initiated                                                        │
│         │                                                                    │
│         ├──► payments_succeeded ──► orders_confirmed                         │
│         │                               │                                    │
│         └──► payments_failed            ├──► orders_shipped                  │
│                                         │                                    │
│                                         ├──► orders_delivered                │
│                                         │                                    │
│                                         └──► orders_cancelled                │
│                                                                             │
│  CONVERSION RATES:                                                           │
│  ├── payment_success_rate = payments_succeeded / payments_initiated         │
│  ├── confirmation_rate = orders_confirmed / orders_created                  │
│  └── completion_rate = orders_delivered / orders_confirmed                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### analytics_revenue

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REVENUE DAILY                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PURPOSE: Daily revenue and attribution metrics                              │
│                                                                             │
│  FIELDS:                                                                     │
│  ├── date (unique)                                                          │
│  ├── gross_revenue_cents, refunded_cents, net_revenue_cents                 │
│  ├── paid_orders, refunded_orders                                           │
│  ├── average_order_value_cents                                              │
│  ├── revenue_by_community: { community_id: cents, ... }                     │
│  └── revenue_by_promotion: { promotion_id: cents, ... }                     │
│                                                                             │
│  EVENTS CONSUMED:                                                            │
│  ├── order.payment_succeeded → record_payment()                             │
│  ├── order.cancelled (with refund) → record_refund()                        │
│  └── order.attribution_recorded → cache attribution for payment             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Aggregation Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DAILY AGGREGATION PATTERN                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROACH: Increment-on-event (not batch aggregation)                        │
│                                                                             │
│  1. Extract date from event.occurred_at                                      │
│  2. Find or create document for that date                                    │
│  3. Increment relevant counter                                               │
│  4. Recalculate derived rates                                               │
│  5. Save                                                                     │
│                                                                             │
│  BENEFITS:                                                                   │
│  • Real-time dashboard updates                                               │
│  • No batch job scheduling                                                   │
│  • Natural time-series storage                                               │
│                                                                             │
│  TRADE-OFFS:                                                                 │
│  • Higher write load (acceptable for v1 scale)                               │
│  • Requires idempotent consumers                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Files

```
kafka/analytics/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── user_lifecycle.py     # UserLifecycleDaily
│   ├── order_funnel.py       # OrderFunnelDaily
│   └── revenue.py            # RevenueDaily
└── consumers/
    ├── __init__.py
    ├── user_lifecycle.py     # UserLifecycleConsumer
    ├── order_funnel.py       # OrderFunnelConsumer
    └── revenue.py            # RevenueConsumer
```
