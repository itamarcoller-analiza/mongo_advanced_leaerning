# TASK 09: Kafka Producer & Consumer - Event-Driven Architecture

## 1. MISSION BRIEFING

Every mutation in the Social Commerce Platform emits a **domain event** through Kafka. When a user registers, an order completes, or a promotion is approved - the backend service **produces** an event, and downstream consumers **react** to it. This is the backbone of the platform's event-driven architecture: the backend writes to MongoDB and emits events, while separate consumer services subscribe to topics and build **read-optimized projections** in MySQL for analytics.

You already have a fully working **producer** on the backend side (every service already calls `kafka_producer.emit()`). You also have a working **consumer infrastructure** (`KafkaConsumer` class with handler registration) and one complete **reference consumer** (`AuthConsumer` handling 6 user events). Your job is to understand how these pieces work together, then build the remaining consumers for the other 6 domains.

### What You Will Build
Consumer classes for **6 domains** - Order, Product, Promotion, Post, Community, and Supplier. Each consumer flattens nested MongoDB document data into relational MySQL tables, following the same pattern established by the `AuthConsumer` reference implementation.

### What You Will Learn

| Kafka/Architecture Concept | Where You'll Use It |
|---------------------------|-------------------|
| **Event envelope pattern** | Every event has `event_type`, `event_id`, `timestamp`, `entity_id`, `data` |
| **Producer: `emit()` vs `send()`** | `emit()` wraps data in envelope, `send()` is raw - understand the difference |
| **Consumer: handler registration** | `register_handler(event_type, handler)` routes events to the right function |
| **Consumer group + partition key** | `entity_id` as partition key guarantees ordering per entity |
| **Document-to-relational flattening** | Nested MongoDB documents -> flat MySQL columns |
| **Full model dump vs selective payload** | `created` events send full `model_dump()`, lifecycle events send minimal data |
| **Idempotency via `event_id`** | Each event has a UUID - consumers can use it to prevent duplicate processing |
| **Graceful shutdown** | SIGINT/SIGTERM handlers stop the consumer loop cleanly |
| **Topic subscription** | Subscribe to specific topics, not all - each consumer group has focus |
| **Auto-commit with interval** | `enable.auto.commit: True` with 5000ms interval - understand the tradeoffs |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND SERVICE (Producer)                   │
│                                                                 │
│  AuthService ──┐                                                │
│  OrderService ─┤                                                │
│  PostService ──┤──► KafkaProducer.emit() ──► Kafka Broker       │
│  ProductService┤         │                       │              │
│  PromotionSvc ─┤    event envelope:         7 topics:           │
│  CommunitySvc ─┤    {event_type,            user, order,        │
│  SupplierAuth ─┘     event_id,              post, product,      │
│                      timestamp,             promotion,          │
│                      entity_id,             community,          │
│                      data: {...}}           supplier             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MYSQL SERVICE (Consumer)                     │
│                                                                 │
│  KafkaConsumer                                                  │
│    ├── register_handler(event_type, handler)                    │
│    ├── subscribe([topics])                                      │
│    └── start() ──► poll loop ──► _process_message()             │
│                                       │                         │
│                          ┌────────────┴────────────┐            │
│                          │  Route by event_type    │            │
│                          └────────────┬────────────┘            │
│                                       │                         │
│    ┌──────────────┬──────────┬────────┴───┬──────────┐          │
│    ▼              ▼          ▼            ▼          ▼          │
│  AuthConsumer  OrderConsumer  PostConsumer  ...  SupplierConsumer│
│  (COMPLETE)    (YOU BUILD)   (YOU BUILD)       (YOU BUILD)      │
│                                                                 │
│  Each consumer:                                                 │
│    1. Extracts data from event envelope                         │
│    2. Flattens nested MongoDB docs to flat columns              │
│    3. Calls DAL methods to INSERT/UPDATE MySQL                  │
└─────────────────────────────────────────────────────────────────┘
```

### How This Differs From Previous Tasks

| Aspect | MongoDB Tasks (01-08) | Kafka Task (09) |
|--------|----------------------|-----------------|
| Data flow | Request → Service → MongoDB | Kafka → Consumer → MySQL |
| Programming model | Async (Beanie ODM) | Synchronous (confluent_kafka) |
| Data shape | Nested documents | Flat relational rows |
| Trigger | HTTP request | Event message on topic |
| Error handling | Raise HTTPException | Log + continue (don't block queue) |
| Idempotency | Via `find_one` on unique key | Via `event_id` deduplication |
| Service location | `apps/backend-service/` | `apps/mysql-service/` |

---

## 2. BEFORE YOU START

### Prerequisites
- **Docker with Kafka running** - The platform uses KRaft mode Kafka (no Zookeeper)
- **MySQL running** - The analytics database where consumers write
- **TASK_01 (User) should be complete** - So events are actually being produced
- Familiarity with the event envelope pattern from the architecture docs

### Files You MUST Read Before Coding

Read these files in this exact order:

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/kafka/config.py` | 36 lines - KafkaConfig with `to_producer_config()` and `to_consumer_config()` |
| 2 | `shared/kafka/topics.py` | 78 lines - 7 Topic constants + 28 EventType constants |
| 3 | `apps/backend-service/src/kafka/producer.py` | 109 lines - KafkaProducer with `send()` and `emit()` |
| 4 | `apps/mysql-service/src/kafka/consumer.py` | 105 lines - KafkaConsumer with handler registration and poll loop |
| 5 | `apps/mysql-service/src/consumers/auth_consumer.py` | 135 lines - **REFERENCE IMPLEMENTATION** - AuthConsumer with 6 handlers |
| 6 | `apps/mysql-service/src/dal/user_dal.py` | 107 lines - UserDAL with SQL operations |
| 7 | `apps/mysql-service/src/db/connection.py` | 131 lines - Database with connection pool and `init_tables()` |
| 8 | `apps/mysql-service/main.py` | 41 lines - Entry point: init DB, register handlers, subscribe, start |
| 9 | `docs/TASK_1_ARCHITECTURE.md` | Architecture overview with event ownership and consumer groups |
| 10 | `docs/TASK_2_TOPIC_CATALOG.md` | Topic naming, event types, partition strategy, retention |

### The Event Envelope

Every event produced by `KafkaProducer.emit()` has this structure:

```python
# From producer.py line 89-96
event = {
    "event_type": f"{topic}.{action}",    # e.g., "user.registered", "order.completed"
    "event_id": str(uuid.uuid4()),         # unique ID for idempotency
    "timestamp": utc_now().isoformat(),    # ISO format timestamp
    "entity_id": entity_id,               # e.g., user_id, order_id (also partition key)
    "data": data,                          # the actual payload (varies per event)
}
```

### Two Types of Event Payloads

Understanding this distinction is critical:

| Pattern | When Used | Payload Size | Example |
|---------|-----------|-------------|---------|
| **Full model dump** | `*.created` events | Large - entire document | `user.model_dump(mode="json")` |
| **Selective fields** | Lifecycle events | Small - just what changed | `{"title": ..., "supplier_id": ..., "reason": ...}` |

```python
# PATTERN 1: Full dump on creation (large payload)
self._kafka.emit(
    topic=Topic.ORDER,
    action="created",
    entity_id=oid_to_str(order.id),
    data=order.model_dump(mode="json"),        # <-- entire order document
)

# PATTERN 2: Selective fields on lifecycle (small payload)
self._kafka.emit(
    topic=Topic.ORDER,
    action="cancelled",
    entity_id=oid_to_str(order.id),
    data={                                     # <-- just the relevant fields
        "order_number": order.order_number,
        "customer_id": oid_to_str(order.customer.user_id),
        "total_cents": order.totals.total_cents,
        "reason": reason,
    },
)
```

---

## 3. THE REFERENCE IMPLEMENTATION

Before building anything, study the `AuthConsumer` - it's your template for every consumer you'll build.

### Study: `AuthConsumer` (apps/mysql-service/src/consumers/auth_consumer.py)

```
AuthConsumer Pattern:
━━━━━━━━━━━━━━━━━━━━

class AuthConsumer:
    def __init__(self):
        self._dal = UserDAL()                    # ① DAL handles all SQL

    def _parse_timestamp(self, ts: str):         # ② Shared timestamp parser
        ...

    def handle_user_registered(self, event):     # ③ One handler per event type
        data = event.get("data", {})             #    Extract data from envelope
        contact = data.get("contact_info", {})   #    Navigate nested MongoDB doc
        profile = data.get("profile", {})        #    Flatten to individual fields
        self._dal.insert_user(                   #    Call DAL to write to MySQL
            user_id=event.get("entity_id"),
            email=contact.get("primary_email"),
            display_name=profile.get("display_name"),
            ...
        )

    def get_handlers(self) -> dict:              # ④ Map event types to handlers
        return {
            EventType.USER_REGISTERED: self.handle_user_registered,
            EventType.USER_LOGIN: self.handle_user_login,
            ...
        }
```

### Key Patterns to Copy:

1. **One DAL per consumer** - Consumer owns a DAL instance for its domain
2. **`_parse_timestamp()` helper** - Reuse in every consumer for ISO timestamp parsing
3. **`event.get("data", {})` first** - Always extract the data payload from the envelope
4. **Navigate nested docs with `.get()`** - Never assume fields exist (MongoDB docs can vary)
5. **`get_handlers()` dict** - Returns `{EventType.X: self.handle_x}` mapping for registration
6. **Handlers are synchronous** - The consumer poll loop is blocking, handlers run inline

---

## 4. EXERCISES

### Exercise 1: Understand the Producer Side (Read-Only)

**Goal:** Trace exactly what happens when a backend service emits an event.

**What to study:** `apps/backend-service/src/kafka/producer.py`

#### 1a. Trace `emit()` vs `send()`

Read the `KafkaProducer` class and answer these questions (write answers as comments in your code):

```python
# Q1: What does emit() add that send() doesn't?
# (Hint: Look at the event dict built in emit() at line 89-96)

# Q2: What is the partition key for events? Why does this matter for ordering?
# (Hint: Look at the key= parameter in send() called from emit())

# Q3: What happens if Kafka is unreachable when emit() is called?
# (Hint: Look at _delivery_callback and the poll(0) call)

# Q4: Why is there a singleton pattern (get_kafka_producer)?
# (Hint: Think about connection pooling and config consistency)
```

#### 1b. Map All 35 Emit Calls

The backend services produce **35 events** across 7 domains. Find them all:

| Service File | Topic | Events (action) | Payload Type |
|-------------|-------|-----------------|-------------|
| `auth.py` | USER | registered (x2), account_locked, login, email_verified, password_reset_requested, password_reset | Full dump (registered), Selective (rest) |
| `order.py` | ORDER | ? | ? |
| `post.py` | POST | ? | ? |
| `product.py` | PRODUCT | ? | ? |
| `promotion.py` | PROMOTION | ? | ? |
| `community.py` | COMMUNITY | ? | ? |
| `supplier_auth.py` | SUPPLIER | ? | ? |

> **Hint:** Search for `self._kafka.emit(` across all service files. Count should be 35 total.

#### Verification
```bash
# Count all emit calls across services
grep -r "self._kafka.emit(" apps/backend-service/src/services/ | wc -l
# Expected: 35
```

---

### Exercise 2: Understand the Consumer Side (Read-Only)

**Goal:** Trace the full consumer lifecycle from startup to message processing.

**What to study:** `apps/mysql-service/main.py` + `src/kafka/consumer.py`

#### 2a. Trace the Startup Sequence

Read `main.py` and trace the initialization:

```python
# Step 1: Database initialization
db = get_database()
db.connect()         # Creates MySQL connection pool (5 connections)
db.init_tables()     # Creates users, user_logins, user_events tables

# Step 2: Consumer creation
consumer = KafkaConsumer(group_id="mysql-analytics-service")
# Q: What config does this create? (Look at KafkaConfig.to_consumer_config)
# Q: What does auto.offset.reset = "earliest" mean for a new consumer group?

# Step 3: Handler registration
auth_consumer = AuthConsumer()
for event_type, handler in auth_consumer.get_handlers().items():
    consumer.register_handler(event_type, handler)
# Q: How many handlers are registered? What event types?

# Step 4: Topic subscription
consumer.subscribe([Topic.USER])
# Q: Why subscribe to only Topic.USER and not Topic.all()?

# Step 5: Start consuming
consumer.start()
# Q: What happens in the poll loop when a message has no registered handler?
```

#### 2b. Trace Message Processing

Follow a single event through the consumer:

```
Kafka message arrives (JSON bytes)
    │
    ▼
consumer.poll(timeout=1.0)              # Blocks up to 1 second
    │
    ▼
msg.error() check                       # Handle partition EOF, unknown topic
    │
    ▼
_process_message(msg)
    │
    ├── json.loads(msg.value().decode())  # Deserialize JSON
    │
    ├── value.get("event_type")           # Extract event_type from envelope
    │
    ├── self._handlers.get(event_type)    # Lookup registered handler
    │
    └── handler(value)                    # Call handler with full event dict
```

> **Key insight:** The consumer doesn't know about MongoDB models. It receives a plain dict and extracts what it needs. The "flattening" happens in the handler, not the consumer infrastructure.

---

### Exercise 3: Build the Order Consumer

**File to create:** `apps/mysql-service/src/consumers/order_consumer.py`
**DAL to create:** `apps/mysql-service/src/dal/order_dal.py`

The Order topic has **3 events**: `order.created`, `order.completed`, `order.cancelled`.

#### 3a. Design the MySQL Tables

First, add tables to `connection.py`'s `init_tables()` method:

```
Think about what analytics questions these tables should answer:
- How many orders per day/week/month?
- What's the average order value?
- Which products sell most?
- What's the cancellation rate and why?
- Which customers order most frequently?
```

You need these tables:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `orders` | Core order data (from `order.created`) | order_id, order_number, customer_id, total_cents, currency, item_count, status, ... |
| `order_items` | Individual line items (from `order.created`) | order_id, product_id, product_name, variant_name, quantity, unit_price_cents, ... |
| `order_events` | Lifecycle events (from all 3 events) | order_id, event_type, event_id, event_data, ... |

#### 3b. Build the OrderDAL

**File:** `apps/mysql-service/src/dal/order_dal.py`

Follow the `UserDAL` pattern:

```python
class OrderDAL:
    """Data Access Layer for order analytics tables."""

    def __init__(self):
        self._db = get_database()

    def insert_order(self, order_id, order_number, customer_id, ...):
        """Insert order from order.created event."""
        # TODO: INSERT INTO orders (...)

    def insert_order_item(self, order_id, product_id, product_name, ...):
        """Insert individual order line item."""
        # TODO: INSERT INTO order_items (...)

    def update_order_status(self, order_id, status):
        """Update order status (completed/cancelled)."""
        # TODO: UPDATE orders SET status = ... WHERE order_id = ...

    def insert_event(self, order_id, event_type, event_id, event_data, event_timestamp):
        """Insert generic order event."""
        # TODO: INSERT INTO order_events (...)
```

#### 3c. Build the OrderConsumer

**File:** `apps/mysql-service/src/consumers/order_consumer.py`

```python
class OrderConsumer:
    """Consumer for order events from order topic."""

    def __init__(self):
        self._dal = OrderDAL()

    def handle_order_created(self, event: dict) -> None:
        """
        Handle order.created - flatten full order document to MySQL.

        The data payload is a full model_dump() of the Order document.
        You need to:
        1. Extract customer info from data["customer"]
        2. Extract totals from data["totals"]
        3. Insert the order row
        4. Loop through data["items"] and insert each as an order_item
        """
        # TODO: Implement

    def handle_order_completed(self, event: dict) -> None:
        """
        Handle order.completed - update status and log event.

        The data payload is selective:
        {
            "order_number": "...",
            "customer_id": "...",
            "total_cents": 5000,
            "currency": "USD",
            "item_count": 2,
            "status": "confirmed"
        }
        """
        # TODO: Implement

    def handle_order_cancelled(self, event: dict) -> None:
        """
        Handle order.cancelled - update status and log event.

        The data payload is selective:
        {
            "order_number": "...",
            "customer_id": "...",
            "total_cents": 5000,
            "reason": "customer_requested"
        }
        """
        # TODO: Implement

    def get_handlers(self) -> dict:
        return {
            EventType.ORDER_CREATED: self.handle_order_created,
            EventType.ORDER_COMPLETED: self.handle_order_completed,
            EventType.ORDER_CANCELLED: self.handle_order_cancelled,
        }
```

**Key flattening challenge:** The `order.created` event contains a full Order model dump. You need to navigate:

```
data (full Order model_dump)
├── customer
│   ├── user_id          → orders.customer_id
│   ├── display_name     → orders.customer_name
│   └── email            → orders.customer_email
├── totals
│   ├── subtotal_cents   → orders.subtotal_cents
│   ├── discount_cents   → orders.discount_cents
│   ├── total_cents      → orders.total_cents
│   └── currency         → orders.currency
├── items[]
│   ├── product_snapshot
│   │   ├── product_id   → order_items.product_id
│   │   ├── name         → order_items.product_name
│   │   └── supplier_id  → order_items.supplier_id
│   ├── variant_snapshot
│   │   └── name         → order_items.variant_name
│   ├── quantity         → order_items.quantity
│   └── unit_price_cents → order_items.unit_price_cents
├── order_number         → orders.order_number
└── status               → orders.status
```

> **Hint:** Study how `AuthConsumer.handle_user_registered()` navigates `data["contact_info"]["primary_email"]` and `data["profile"]["display_name"]` - your order handler does the same thing but deeper.

#### Verification
```bash
# After building and registering your consumer, produce a test event:
# 1. Create an order via the API
# 2. Check MySQL for the flattened data:
mysql -u analytics -panalytics123 analytics -e "SELECT * FROM orders LIMIT 5;"
mysql -u analytics -panalytics123 analytics -e "SELECT * FROM order_items LIMIT 10;"
```

---

### Exercise 4: Build the Product Consumer

**File to create:** `apps/mysql-service/src/consumers/product_consumer.py`
**DAL to create:** `apps/mysql-service/src/dal/product_dal.py`

The Product topic has **5 events**: `product.created`, `product.published`, `product.discontinued`, `product.out_of_stock`, `product.deleted`.

#### 4a. Design the MySQL Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `products` | Core product data (from `product.created`) | product_id, supplier_id, name, category, base_price_cents, status, ... |
| `product_events` | Lifecycle events (from all 5 events) | product_id, event_type, event_id, event_data, ... |

#### 4b. Build the ProductConsumer

```python
class ProductConsumer:
    """Consumer for product events from product topic."""

    def handle_product_created(self, event: dict) -> None:
        """
        Handle product.created - full model dump.

        Navigate: data["name"], data["category"], data["base_price_cents"],
                  data["supplier_id"], data["status"]
        """
        # TODO

    def handle_product_published(self, event: dict) -> None:
        """
        Handle product.published - selective payload.

        Data: {"name", "supplier_id", "category", "base_price_cents"}
        Action: Update product status to "active"
        """
        # TODO

    def handle_product_discontinued(self, event: dict) -> None:
        """
        Handle product.discontinued - selective payload.

        Data: {"name", "supplier_id"}
        Action: Update product status to "discontinued"
        """
        # TODO

    def handle_product_out_of_stock(self, event: dict) -> None:
        """
        Handle product.out_of_stock - selective payload.

        Data: {"name", "supplier_id"}
        Action: Update product status to "out_of_stock" (or flag)
        """
        # TODO

    def handle_product_deleted(self, event: dict) -> None:
        """
        Handle product.deleted - selective payload.

        Data: {"name", "supplier_id"}
        Action: Update product status to "deleted" (soft delete in MySQL too)
        """
        # TODO

    def get_handlers(self) -> dict:
        return {
            EventType.PRODUCT_CREATED: self.handle_product_created,
            EventType.PRODUCT_PUBLISHED: self.handle_product_published,
            EventType.PRODUCT_DISCONTINUED: self.handle_product_discontinued,
            EventType.PRODUCT_OUT_OF_STOCK: self.handle_product_out_of_stock,
            EventType.PRODUCT_DELETED: self.handle_product_deleted,
        }
```

> **Pattern:** `product.created` → INSERT full row. All other events → UPDATE status + INSERT into `product_events` log.

---

### Exercise 5: Build the Remaining Consumers

Now build consumers for the 4 remaining domains. Each follows the same pattern: Consumer class + DAL class + MySQL tables.

#### 5a. Promotion Consumer (8 events - the most complex)

**Events:** `promotion.created`, `promotion.submitted`, `promotion.approved`, `promotion.rejected`, `promotion.paused`, `promotion.resumed`, `promotion.cancelled`, `promotion.ended`

| Table | Key Columns |
|-------|-------------|
| `promotions` | promotion_id, supplier_id, title, promotion_type, status, ... |
| `promotion_events` | promotion_id, event_type, reviewer_id, scope, reason, ... |

**Key challenge:** The `promotion.approved` and `promotion.rejected` events include `reviewer_id`, `scope`, and optionally `reason`. Your events table should capture these moderation-specific fields.

```python
# Promotion lifecycle events have rich metadata:
# approved: {"title", "supplier_id", "reviewer_id", "scope", "status"}
# rejected: {"title", "supplier_id", "reviewer_id", "scope", "reason", "status"}
# paused:   {"title", "supplier_id", "reason"}
# cancelled: {"title", "supplier_id", "reason"}
```

#### 5b. Post Consumer (4 events)

**Events:** `post.created`, `post.deleted`, `post.hidden`, `post.global_distribution_approved`

| Table | Key Columns |
|-------|-------------|
| `posts` | post_id, author_id, community_id, post_type, status, ... |
| `post_events` | post_id, event_type, actor_id, reason, ... |

**Key challenge:** The `post.created` event sends a full model dump with deeply nested author info (`data["author"]["user_id"]`, `data["author"]["display_name"]`). The moderation events (`hidden`, `deleted`) include who performed the action.

#### 5c. Community Consumer (5 events)

**Events:** `community.created`, `community.member_joined`, `community.member_left`, `community.suspended`, `community.verified`

| Table | Key Columns |
|-------|-------------|
| `communities` | community_id, name, owner_id, member_count, status, ... |
| `community_membership_events` | community_id, user_id, event_type, member_count, ... |
| `community_events` | community_id, event_type, admin_id, reason, ... |

**Key challenge:** `member_joined` and `member_left` include `member_count` - you should UPDATE the community's member_count AND insert a membership event row.

#### 5d. Supplier Consumer (3 events)

**Events:** `supplier.registered`, `supplier.login`, `supplier.documents_submitted`

| Table | Key Columns |
|-------|-------------|
| `suppliers` | supplier_id, email, company_name, status, ... |
| `supplier_logins` | supplier_id, email, company_name, ip_address, ... |
| `supplier_events` | supplier_id, event_type, event_id, event_data, ... |

**Key challenge:** The `supplier.registered` event sends a full model dump. Navigate nested company info: `data["company_info"]["legal_name"]`, `data["contact_info"]["primary_email"]`.

---

### Exercise 6: Wire Everything Together in `main.py`

**File to modify:** `apps/mysql-service/main.py`

Currently `main.py` only registers the `AuthConsumer` and subscribes to `Topic.USER`. You need to register ALL consumers and subscribe to ALL topics.

#### 6a. Update main.py

```python
"""MySQL Analytics Service - Kafka Consumer Entry Point."""

import logging

from src.db.connection import get_database
from src.kafka.consumer import KafkaConsumer
from src.consumers.auth_consumer import AuthConsumer
# TODO: Import your new consumers
# from src.consumers.order_consumer import OrderConsumer
# from src.consumers.product_consumer import ProductConsumer
# from src.consumers.promotion_consumer import PromotionConsumer
# from src.consumers.post_consumer import PostConsumer
# from src.consumers.community_consumer import CommunityConsumer
# from src.consumers.supplier_consumer import SupplierConsumer
from shared.kafka.topics import Topic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Start the MySQL analytics consumer."""
    logger.info("MySQL Analytics Service starting...")

    # Initialize database
    db = get_database()
    db.connect()
    db.init_tables()

    # Create consumer
    consumer = KafkaConsumer(group_id="mysql-analytics-service")

    # Register ALL consumer handlers
    consumers = [
        AuthConsumer(),
        # TODO: Add your consumers here
        # OrderConsumer(),
        # ProductConsumer(),
        # PromotionConsumer(),
        # PostConsumer(),
        # CommunityConsumer(),
        # SupplierConsumer(),
    ]

    for c in consumers:
        for event_type, handler in c.get_handlers().items():
            consumer.register_handler(event_type, handler)

    # Subscribe to ALL topics (not just USER anymore)
    consumer.subscribe(Topic.all())

    logger.info(f"Registered {len(consumer._handlers)} event handlers")
    consumer.start()


if __name__ == "__main__":
    main()
```

#### 6b. Update init_tables()

Add your new table definitions to `connection.py`'s `init_tables()` method so they're created on startup.

> **Think about it:** Why does the consumer service create its own tables instead of using a migration tool? In an event-driven system, the consumer owns its read model schema. If you need to change the schema, you drop and recreate the table, then replay events from Kafka to rebuild.

#### Verification
```bash
# Start the consumer and check that all handlers are registered:
python -m apps.mysql-service.main

# Expected log output:
# Registered handler for: user.registered
# Registered handler for: user.login
# Registered handler for: order.created
# Registered handler for: order.completed
# ... (should see 28+ handlers)
# Registered 28 event handlers
# Subscribed to topics: ['user', 'order', 'post', 'product', 'promotion', 'community', 'supplier']
# Consumer started, waiting for messages...
```

---

## 5. HOW THE PIECES FIT: COMPLETE EVENT LIFECYCLE

Trace one complete event from API call to MySQL row:

```
1. USER CALLS API
   POST /api/orders  (with auth token + idempotency key)

2. ROUTE LAYER
   routes/order.py → calls OrderService.create_order()

3. SERVICE LAYER (apps/backend-service/src/services/order.py)
   ├── Validates user, products, promotion
   ├── Builds Order document (11 embedded types)
   ├── order.insert()  →  MongoDB
   └── self._kafka.emit(                          ← PRODUCES EVENT
           topic=Topic.ORDER,
           action="created",
           entity_id=oid_to_str(order.id),
           data=order.model_dump(mode="json"),
       )

4. KAFKA PRODUCER (apps/backend-service/src/kafka/producer.py)
   emit() builds envelope:
   {
       "event_type": "order.created",
       "event_id": "uuid-...",
       "timestamp": "2024-...",
       "entity_id": "order-id-...",
       "data": { ...full order document... }
   }
   → producer.send(topic="order", key="order-id-...", value=envelope)
   → confluent_kafka.Producer.produce() → Kafka broker

5. KAFKA BROKER
   Message stored in "order" topic, partition determined by hash(key)

6. KAFKA CONSUMER (apps/mysql-service/src/kafka/consumer.py)
   consumer.poll(timeout=1.0) → receives message
   → _process_message(msg)
   → json.loads(msg.value())
   → handlers["order.created"](event)

7. ORDER CONSUMER (apps/mysql-service/src/consumers/order_consumer.py)
   handle_order_created(event):
   ├── data = event["data"]
   ├── customer = data["customer"]
   ├── totals = data["totals"]
   ├── dal.insert_order(order_id, customer["user_id"], totals["total_cents"], ...)
   └── for item in data["items"]:
           dal.insert_order_item(order_id, item["product_snapshot"]["product_id"], ...)

8. ORDER DAL → MySQL
   INSERT INTO orders (order_id, customer_id, total_cents, ...) VALUES (...)
   INSERT INTO order_items (order_id, product_id, quantity, ...) VALUES (...)
```

---

## 6. COMPLETE EVENT REFERENCE

### All 35 Events by Domain

#### User Topic (7 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `user.registered` | registered | Full model dump | INSERT into `users` |
| `user.registered` | registered (business) | Full model dump | INSERT into `users` |
| `user.login` | login | `{email, role, ip_address}` | INSERT into `user_logins` |
| `user.email_verified` | email_verified | `{email, status}` | UPDATE `users` email_verified |
| `user.account_locked` | account_locked | `{email, failed_attempts, lock_duration_minutes}` | UPDATE `users` status + INSERT event |
| `user.password_reset_requested` | password_reset_requested | `{email}` | INSERT event |
| `user.password_reset` | password_reset | `{}` (empty) | INSERT event |

#### Order Topic (3 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `order.created` | created | Full model dump | INSERT `orders` + INSERT `order_items[]` |
| `order.completed` | completed | `{order_number, customer_id, total_cents, currency, item_count, status}` | UPDATE status + INSERT event |
| `order.cancelled` | cancelled | `{order_number, customer_id, total_cents, reason}` | UPDATE status + INSERT event |

#### Product Topic (5 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `product.created` | created | Full model dump | INSERT `products` |
| `product.published` | published | `{name, supplier_id, category, base_price_cents}` | UPDATE status + INSERT event |
| `product.discontinued` | discontinued | `{name, supplier_id}` | UPDATE status + INSERT event |
| `product.out_of_stock` | out_of_stock | `{name, supplier_id}` | UPDATE status + INSERT event |
| `product.deleted` | deleted | `{name, supplier_id}` | UPDATE status + INSERT event |

#### Promotion Topic (8 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `promotion.created` | created | Full model dump | INSERT `promotions` |
| `promotion.submitted` | submitted | `{title, supplier_id, promotion_type, status}` | UPDATE status + INSERT event |
| `promotion.approved` | approved | `{title, supplier_id, reviewer_id, scope, status}` | UPDATE status + INSERT event |
| `promotion.rejected` | rejected | `{title, supplier_id, reviewer_id, scope, reason, status}` | UPDATE status + INSERT event |
| `promotion.paused` | paused | `{title, supplier_id, reason}` | UPDATE status + INSERT event |
| `promotion.resumed` | resumed | `{title, supplier_id}` | UPDATE status + INSERT event |
| `promotion.cancelled` | cancelled | `{title, supplier_id, reason}` | UPDATE status + INSERT event |
| `promotion.ended` | ended | `{title, supplier_id}` | UPDATE status + INSERT event |

#### Post Topic (4 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `post.created` | created | Full model dump | INSERT `posts` |
| `post.deleted` | deleted | `{author_id, community_id, deleted_by}` | UPDATE status + INSERT event |
| `post.hidden` | hidden | `{author_id, community_id, hidden_by, reason}` | UPDATE status + INSERT event |
| `post.global_distribution_approved` | global_distribution_approved | `{author_id, community_id, admin_id}` | INSERT event |

#### Community Topic (5 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `community.created` | created | Full model dump | INSERT `communities` |
| `community.member_joined` | member_joined | `{user_id, community_name, member_count}` | UPDATE member_count + INSERT membership event |
| `community.member_left` | member_left | `{user_id, community_name, member_count}` | UPDATE member_count + INSERT membership event |
| `community.suspended` | suspended | `{community_name, admin_id, reason}` | UPDATE status + INSERT event |
| `community.verified` | verified | `{community_name, admin_id}` | UPDATE status + INSERT event |

#### Supplier Topic (3 events)
| Event Type | Action | Payload | Handler Action |
|-----------|--------|---------|---------------|
| `supplier.registered` | registered | Full model dump | INSERT `suppliers` |
| `supplier.login` | login | `{email, company_name, ip_address}` | INSERT `supplier_logins` |
| `supplier.documents_submitted` | documents_submitted | `{company_name, document_count, verification_status}` | INSERT event |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Idempotent Event Processing

**Problem:** If the consumer crashes after processing but before committing the Kafka offset, the event will be redelivered. Your handler will try to INSERT a duplicate row.

**Task:** Add idempotency to your consumers using the `event_id` field.

```
Approach 1: event_id column with UNIQUE constraint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALTER TABLE orders ADD COLUMN event_id VARCHAR(50) UNIQUE;

On INSERT, use INSERT IGNORE or ON DUPLICATE KEY UPDATE:
  INSERT INTO orders (..., event_id) VALUES (..., %s)
  ON DUPLICATE KEY UPDATE event_id = event_id;
  -- No-op if already processed


Approach 2: Separate processed_events table
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE processed_events (
    event_id VARCHAR(50) PRIMARY KEY,
    event_type VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

Before processing, check:
  SELECT 1 FROM processed_events WHERE event_id = %s
If exists → skip. Otherwise → process + INSERT into processed_events.
```

**Think about:** Which approach is better? What are the tradeoffs between checking before processing vs using database constraints?

### Challenge 2: Dead Letter Queue (DLQ)

**Problem:** What happens when a handler throws an exception? Currently, the consumer logs the error and moves on - the event is lost (auto-commit means the offset advances).

**Task:** Implement a DLQ pattern:

```python
def _process_message(self, msg) -> None:
    try:
        value = json.loads(msg.value().decode("utf-8"))
        event_type = value.get("event_type")
        handler = self._handlers.get(event_type)

        if handler:
            handler(value)
        else:
            logger.debug(f"No handler for: {event_type}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # TODO: Instead of just logging, send to a DLQ topic
        # self._dlq_producer.send(
        #     topic=f"dlq.{msg.topic()}",
        #     value={
        #         "original_topic": msg.topic(),
        #         "original_event": value,
        #         "error": str(e),
        #         "failed_at": utc_now().isoformat(),
        #         "retry_count": 0,
        #     }
        # )
```

**Think about:** The DLQ requires a KafkaProducer inside the consumer service. How would you initialize it? Should it share the same `KafkaConfig`?

### Challenge 3: Consumer Lag Monitoring

**Problem:** How do you know if your consumer is falling behind? If events are produced faster than consumed, a "lag" builds up.

**Task:** Research and implement basic lag monitoring:

```bash
# Using kafka-consumer-groups CLI tool:
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
    --group mysql-analytics-service \
    --describe

# This shows: TOPIC, PARTITION, CURRENT-OFFSET, LOG-END-OFFSET, LAG
```

**Think about:**
- What lag is acceptable? (Hint: depends on use case - analytics can tolerate minutes, projections should be near-real-time)
- What should happen when lag exceeds a threshold?
- How would you expose lag as a health check endpoint?

---

## 8. KEY CONCEPTS SUMMARY

### Producer Side (Already Built)

| Component | File | Purpose |
|-----------|------|---------|
| `KafkaConfig` | `shared/kafka/config.py` | Connection settings from env vars |
| `Topic` | `shared/kafka/topics.py` | 7 topic constants |
| `EventType` | `shared/kafka/topics.py` | 28 event type constants |
| `KafkaProducer` | `apps/backend-service/src/kafka/producer.py` | `send()` for raw, `emit()` for enveloped |
| `get_kafka_producer()` | Same file | Singleton access pattern |

### Consumer Side (You Build)

| Component | File | Purpose |
|-----------|------|---------|
| `KafkaConsumer` | `apps/mysql-service/src/kafka/consumer.py` | Poll loop + handler routing (already built) |
| `AuthConsumer` | `apps/mysql-service/src/consumers/auth_consumer.py` | Reference implementation (already built) |
| `OrderConsumer` | `apps/mysql-service/src/consumers/order_consumer.py` | **You build** |
| `ProductConsumer` | `apps/mysql-service/src/consumers/product_consumer.py` | **You build** |
| `PromotionConsumer` | `apps/mysql-service/src/consumers/promotion_consumer.py` | **You build** |
| `PostConsumer` | `apps/mysql-service/src/consumers/post_consumer.py` | **You build** |
| `CommunityConsumer` | `apps/mysql-service/src/consumers/community_consumer.py` | **You build** |
| `SupplierConsumer` | `apps/mysql-service/src/consumers/supplier_consumer.py` | **You build** |
| `main.py` | `apps/mysql-service/main.py` | Wire all consumers + subscribe to all topics |

### Flattening Pattern

```
MongoDB Document (Nested)          MySQL Table (Flat)
━━━━━━━━━━━━━━━━━━━━━━━━          ━━━━━━━━━━━━━━━━━━

{                                  ┌────────────────┐
  "customer": {                    │ customer_id    │ ← data["customer"]["user_id"]
    "user_id": "abc",              │ customer_name  │ ← data["customer"]["display_name"]
    "display_name": "John"         │ customer_email │ ← data["customer"]["email"]
  },                               │ total_cents    │ ← data["totals"]["total_cents"]
  "totals": {                      │ currency       │ ← data["totals"]["currency"]
    "total_cents": 5000,           │ status         │ ← data["status"]
    "currency": "USD"              └────────────────┘
  },
  "status": "pending"
}

Rule: Navigate with .get() chains, never assume fields exist.
      data.get("customer", {}).get("user_id")  ✓
      data["customer"]["user_id"]               ✗ (KeyError risk)
```

---

## 9. CHECKLIST

Before moving on, verify:

- [ ] You understand the event envelope: `{event_type, event_id, timestamp, entity_id, data}`
- [ ] You can explain `emit()` vs `send()` and when each is used
- [ ] You traced the full lifecycle: API → Service → Producer → Kafka → Consumer → MySQL
- [ ] You understand `auto.commit.interval.ms = 5000` and its implications for at-least-once delivery
- [ ] `OrderConsumer` handles 3 events with proper flattening
- [ ] `ProductConsumer` handles 5 events with status updates
- [ ] `PromotionConsumer` handles 8 events with moderation metadata
- [ ] `PostConsumer` handles 4 events with actor tracking
- [ ] `CommunityConsumer` handles 5 events with member count updates
- [ ] `SupplierConsumer` handles 3 events with company info flattening
- [ ] `main.py` registers all consumers and subscribes to `Topic.all()`
- [ ] All MySQL tables are created in `init_tables()`
- [ ] Consumer logs show all 28+ handlers registered on startup
- [ ] You can explain why events use `entity_id` as the partition key (ordering guarantee)
