# Task 10: Rollout + Backfill

## 1. Rollout Phases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROLLOUT PHASES                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1: Infrastructure                                                     │
│  ════════════════════════                                                    │
│  1. Deploy Kafka cluster (docker-compose up)                                 │
│  2. Verify topics created                                                    │
│  3. Initialize MongoDB collections and indexes                               │
│                                                                             │
│  PHASE 2: Producer Integration                                               │
│  ═════════════════════════════                                               │
│  1. Deploy outbox publisher worker                                           │
│  2. Add outbox inserts to service methods (behind feature flag)              │
│  3. Verify events appear in Kafka topics                                     │
│                                                                             │
│  PHASE 3: Consumer Deployment                                                │
│  ════════════════════════════                                                │
│  1. Deploy projection consumers                                              │
│  2. Deploy analytics consumers                                               │
│  3. Monitor consumer lag                                                     │
│                                                                             │
│  PHASE 4: Backfill                                                           │
│  ════════════════                                                            │
│  1. Run backfill script for existing entities                                │
│  2. Verify read models populated                                             │
│  3. Switch reads to projections                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backfill Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACKFILL STRATEGY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROACH: Direct projection write (skip Kafka for historical data)          │
│                                                                             │
│  1. Query existing entities from source collections                          │
│  2. Transform to read model format                                           │
│  3. Upsert into projection collections                                       │
│  4. Set entity_version = current source version                              │
│                                                                             │
│  WHY NOT REPLAY THROUGH KAFKA:                                               │
│  • No historical events exist yet                                            │
│  • Direct write is faster for bulk data                                      │
│  • Consumers handle new events going forward                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Monitoring Checklist

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MONITORING CHECKLIST                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  KAFKA:                                                                      │
│  □ Consumer lag per group                                                    │
│  □ Messages per second per topic                                             │
│  □ Broker health                                                             │
│                                                                             │
│  OUTBOX:                                                                     │
│  □ Pending count (should stay low)                                           │
│  □ Failed count (should be zero)                                             │
│  □ Processing latency                                                        │
│                                                                             │
│  PROJECTIONS:                                                                │
│  □ Document count growth                                                     │
│  □ Query latency on read models                                              │
│  □ Version staleness                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
