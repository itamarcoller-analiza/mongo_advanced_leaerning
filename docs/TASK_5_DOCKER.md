# Task 5: Kafka Docker Compose

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DOCKER COMPOSE SETUP                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    sc-network (bridge)                              │    │
│  │                                                                     │    │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │    │
│  │   │   kafka     │    │  kafka-ui   │    │ kafka-init  │            │    │
│  │   │             │    │             │    │             │            │    │
│  │   │ KRaft mode  │◄───│ Web UI      │    │ Topic       │            │    │
│  │   │ Port: 9092  │    │ Port: 8080  │    │ creation    │            │    │
│  │   │       9093  │    │             │    │ (one-shot)  │            │    │
│  │   └─────────────┘    └─────────────┘    └─────────────┘            │    │
│  │         │                                                           │    │
│  │         │ kafka_data volume                                         │    │
│  │         ▼                                                           │    │
│  │   ┌─────────────┐                                                   │    │
│  │   │   Volume    │                                                   │    │
│  │   │ (persistent)│                                                   │    │
│  │   └─────────────┘                                                   │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  HOST ACCESS:                                                               │
│  • Kafka: localhost:9092                                                    │
│  • UI: localhost:8080                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. KRaft Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WHY KRAFT (NO ZOOKEEPER)?                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRADITIONAL (Zookeeper)          KRAFT MODE                                │
│  ═══════════════════════          ══════════                                │
│                                                                             │
│  ┌───────────┐                    ┌───────────┐                             │
│  │ Zookeeper │                    │           │                             │
│  │           │◄───────┐           │  Kafka    │                             │
│  └───────────┘        │           │  (all in  │                             │
│       ▲               │           │   one)    │                             │
│       │               │           │           │                             │
│  ┌────┴────┐    ┌────┴────┐       └───────────┘                             │
│  │ Kafka 1 │    │ Kafka 2 │                                                 │
│  └─────────┘    └─────────┘       Benefits:                                 │
│                                   • Simpler setup                           │
│  Complexity:                      • Single process                          │
│  • 2 systems to manage            • Faster startup                          │
│  • Extra network hops             • Better for dev                          │
│  • More resources                 • Production-ready                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Topics Created

| Topic | Partitions | Retention | Purpose |
|-------|------------|-----------|---------|
| `sc.domain.user` | 3 | 14 days | User events |
| `sc.domain.supplier` | 3 | 14 days | Supplier events |
| `sc.domain.community` | 3 | 14 days | Community events |
| `sc.domain.product` | 3 | 14 days | Product events |
| `sc.domain.promotion` | 3 | 14 days | Promotion events |
| `sc.domain.post` | 3 | 14 days | Post events |
| `sc.domain.order` | 6 | 30 days | Order events |
| `sc.dlq.outbox-user` | 1 | 7 days | User DLQ |
| `sc.dlq.outbox-order` | 1 | 7 days | Order DLQ |
| `sc.dlq.analytics-general` | 1 | 7 days | Analytics DLQ |

---

## 4. Quick Start

```bash
# Start Kafka
cd kafka
make kafka-up

# Verify topics
make topics-list

# Open UI
make kafka-ui

# View logs
make kafka-logs

# Stop
make kafka-down

# Clean all data
make clean
```

---

## 5. Files Created

```
kafka/
├── docker/
│   ├── docker-compose.kafka.yml   # Main compose file
│   └── .env.kafka.example         # Environment template
└── Makefile                        # Development commands
```
