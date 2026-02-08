# TASK 07: Order Service - E-Commerce Transactions & Inventory Operations

## 1. MISSION BRIEFING

Orders are where the **entire platform converges**. Users browse products, discover promotions, and eventually place an order. An order captures a complete purchase - product snapshots frozen at purchase time, payment authorization, inventory reservation, shipping tracking, and a full audit trail. Every order touches **4 collections** (orders, users, products, promotions) and introduces **idempotency**, **price drift detection**, **inventory reservation with rollback**, and the **two-phase order flow** (create PENDING -> complete CONFIRMED).

This is the **most transactional service** you've built. While previous tasks focused on CRUD and lifecycle transitions, the Order service introduces patterns from real e-commerce: idempotency keys prevent duplicate charges, price drift thresholds protect customers from stealth price changes, and inventory reservations use a manual rollback pattern when partial failures occur.

### What You Will Build
The `OrderService` class - ~10 methods covering a two-phase order creation flow, order modification, cancellation with inventory release, cursor-based listing, and two different lookup strategies (by ID and by order number).

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Idempotency via `find_one`** | Check `idempotency_key` before creating - return existing order if duplicate |
| **Cross-collection validation chain** | User (exists + active) -> Products (active + stock) -> Promotion (active + applicable) |
| **Price drift detection** | Re-fetch products at completion, compare prices with threshold |
| **Inventory reservation with rollback** | Reserve stock on complete, release on failure or cancellation |
| **Compound `find_one` (anti-enumeration)** | `{_id, customer.user_id}` - orders scoped to owner |
| **`find_one` on unique field** | `{order_number: ..., customer.user_id: ...}` - lookup by human-readable ID |
| **Cursor-based pagination with `$lt`** | Descending order list with reverse cursor direction |
| **`$in` status filter** | Filter orders by multiple statuses |
| **Nested field queries** | `customer.user_id`, `items.product_snapshot.supplier_id`, `payment.status` |
| **Complex document construction** | 11 embedded types built from request data + cross-collection reads |
| **Model method delegation** | `order.cancel_order()`, `order.add_timeline_event()` for state transitions |
| **Two-phase flow** | Create (PENDING) -> Complete (CONFIRMED) - separates validation from commitment |
| **`Promotion.record_conversion()`** | Cross-collection write-back for analytics on order completion |

### How This Differs From Previous Tasks

| Aspect | Promotion (06) | Order (07) |
|--------|---------------|------------|
| Embedded doc types | 10 | **11** (most in the project) |
| Collections touched | 3 | **4** (orders + users + products + promotions) |
| Pagination | Skip + cursor | **Cursor only** (descending with `$lt`) |
| Idempotency | None | **Idempotency key** prevents duplicate orders |
| Price validation | Snapshot at creation | **Re-validate at completion** (drift detection) |
| Inventory | Not tracked | **Reserve on complete, release on cancel/fail** |
| Two-phase flow | None | **Create PENDING -> Complete CONFIRMED** |
| Rollback pattern | None | **Manual inventory rollback** on partial failure |
| Lookup methods | By ID only | **By ID AND by order number** |
| State machine | 7 statuses (service-driven) | **8 statuses** (model-driven via helpers) |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Orders require a customer (User)
- **TASK_04 (Product) must be complete** - Orders reference products with variant/inventory info
- **TASK_06 (Promotion) is optional** - Promotion validation is a soft dependency (returns None on failure)
- Have at least one active user and one active product with stock

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/order.py` | 572 lines - 11 embedded types, 4 enums, 9 indexes, model helpers |
| 2 | `apps/backend-service/src/schemas/order.py` | 257 lines - Request/response schemas |
| 3 | `apps/backend-service/src/routes/order.py` | 364 lines - 6 endpoints: create, list, get, get-by-number, complete, update, cancel |
| 4 | `apps/backend-service/src/utils/order_utils.py` | 151 lines - Response builders, header extraction |
| 5 | `shared/models/product.py` | Product model - you'll read inventory/variant data |
| 6 | `shared/models/user.py` | User model - you'll build `OrderCustomer` from User |

### The Data Flow

```
HTTP Request (User JWT + X-Idempotency-Key)
    |
    v
+-----------+   Extracts user_id from X-User-ID header
|  Route    |   Extracts idempotency_key from X-Idempotency-Key header
|           |   Extracts ip_address from X-Forwarded-For
|  Calls    |
|  your     |
|  service  |
    |
    v
+--------------------------------------------------------------+
|               OrderService (YOU WRITE THIS)                   |
|                                                               |
|  Reads from FOUR collections:                                 |
|    1. Order      (main CRUD + lifecycle)                      |
|    2. User       (customer info for denormalization)           |
|    3. Product    (validation, pricing, inventory, snapshots)   |
|    4. Promotion  (discount validation, conversion tracking)    |
|                                                               |
|  Key patterns:                                                |
|    - Idempotency check before create                          |
|    - Two-phase: create PENDING -> complete CONFIRMED          |
|    - Price drift detection at completion                      |
|    - Inventory reserve with manual rollback                   |
|                                                               |
|  Returns Order documents                                      |
+--------------------------------------------------------------+
    |
    v
+-----------+   Route transforms Order -> response schemas
|  Route    |   using utils/order_utils.py
+-----------+
```

### The Two-Phase Order Flow

```
Phase 1: CREATE ORDER (PENDING)
  - Validate user exists and is active
  - Validate all products (active, in stock)
  - Validate promotion (if provided) - soft validation
  - Calculate totals (subtotal, discount, tax, shipping)
  - Build all embedded documents (11 types!)
  - Insert with idempotency_key
  - NO inventory reserved yet, NO payment processed

Phase 2: COMPLETE ORDER (PENDING -> CONFIRMED)
  - Re-validate all product prices (drift detection)
  - Reserve inventory for each item
  - If ANY reservation fails -> rollback ALL previous reservations
  - Authorize payment (mock for MVP)
  - Transition to CONFIRMED
  - Record promotion conversion (if applicable)
```

**Why two phases?** In real e-commerce, the user's cart can take minutes to fill. Between adding items and clicking "Place Order", prices and inventory can change. Phase 1 captures intent. Phase 2 locks everything down atomically (as much as MongoDB allows without multi-document transactions).

### The 8-Status Order Lifecycle

```
                    complete_order()
    PENDING ─────────────────────────> CONFIRMED
       |                                    |
       |  cancel_order()                    |  start_processing()
       |                                    v
       +──────────> CANCELLED          PROCESSING
                       ^                    |
                       |                    |  mark_shipped()
                       |                    v
                       +───────────     SHIPPED
                       |                    |
                       |                    |  mark_delivered()
                       |                    v
                       |               DELIVERED
                       |
                       +── cancel_order() (if not shipped)

    Payment fails:
    PENDING ──────────────────────────> FAILED

    After delivery (or anytime after payment):
    ANY paid ─────────────────────────> REFUNDED
```

### The 4 Enums

```python
OrderStatus:    pending | confirmed | processing | shipped | delivered | cancelled | refunded | failed
PaymentStatus:  pending | authorized | captured | failed | refunded | partially_refunded
FulfillmentStatus: pending | processing | shipped | delivered | cancelled | returned
PaymentMethod:  credit_card | debit_card | paypal | apple_pay | google_pay | bank_transfer | cash_on_delivery
```

---

## 3. MODEL DEEP DIVE

### The Order Document (11 Embedded Types)

```python
class Order(Document):
    # Identification
    order_number: str                      # "ORD-20250203-A1B2" (human-readable, unique)

    # Customer (denormalized from User)
    customer: OrderCustomer                # {user_id, display_name, email, phone}

    # Items
    items: List[OrderItem]                 # [{item_id, product_snapshot, quantity, pricing, fulfillment}]

    # Financials
    totals: OrderTotals                    # {subtotal, discount, tax, shipping, total, currency}

    # Addresses
    shipping_address: ShippingAddress      # Full shipping address
    billing_address: Optional[BillingAddress]  # If different from shipping

    # Payment
    payment: PaymentInfo                   # {method, provider, status, transaction_id, card_last4, ...}

    # Refunds
    refunds: List[RefundInfo]              # History of refunds

    # Status
    status: OrderStatus                    # 8 possible values

    # Audit trail
    timeline: List[OrderTimeline]          # Status change history
    audit: OrderAudit                      # {ip_address, user_agent, risk_score, fraud_flags}

    # Marketing
    attribution: Optional[OrderAttribution]  # {promotion_id, community_id, utm_*, ...}

    # Notes
    notes: List[CustomerNote]              # Customer/support notes

    # Idempotency
    idempotency_key: str                   # Unique key to prevent duplicate orders

    # Delivery
    estimated_delivery_date: Optional[datetime]

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### Key Embedded Types

```python
# Frozen product at purchase time (richer than Promotion's snapshot)
class ProductSnapshot(BaseModel):
    product_id: PydanticObjectId
    supplier_id: PydanticObjectId         # NEW: tracks which supplier to pay
    product_name: str
    product_slug: str
    sku: str                              # NEW: SKU for fulfillment
    variant_name: Optional[str]
    variant_attributes: Dict[str, str]    # NEW: {"Color": "Red", "Size": "L"}
    image_url: str
    supplier_name: str                    # Denormalized supplier name

# Each item with pricing + fulfillment tracking
class OrderItem(BaseModel):
    item_id: str                          # "item_1", "item_2"
    product_snapshot: ProductSnapshot
    quantity: int
    unit_price_cents: int
    subtotal_cents: int                   # quantity * unit_price
    discount_cents: int                   # From promotion
    final_price_cents: int                # subtotal - discount
    fulfillment_status: FulfillmentStatus # Per-item tracking
    tracking_number: Optional[str]
    carrier: Optional[str]
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]

# Financial summary
class OrderTotals(BaseModel):
    subtotal_cents: int                   # Sum of all item subtotals
    discount_cents: int                   # Total promotion discount
    tax_cents: int                        # Calculated tax
    shipping_cents: int                   # Shipping cost (0 if over threshold)
    total_cents: int                      # Grand total
    currency: str                         # "USD"
```

### Index Inventory (9 indexes)

```python
indexes = [
    # 1. Unique order number
    [("order_number", 1)],                 # Unique human-readable ID

    # 2. Unique idempotency key (prevents duplicate orders)
    [("idempotency_key", 1)],              # Idempotency enforcement

    # 3. Customer's orders (list_user_orders query)
    [("customer.user_id", 1), ("created_at", -1)],

    # 4. Status filtering
    [("status", 1), ("created_at", -1)],

    # 5. Payment status
    [("payment.status", 1), ("created_at", -1)],

    # 6. Supplier's orders (fulfillment - nested in items array)
    [("items.product_snapshot.supplier_id", 1), ("status", 1)],

    # 7. Promotion attribution (analytics)
    [("attribution.promotion_id", 1), ("created_at", -1)],

    # 8. Fraud review queue
    [("audit.requires_review", 1), ("audit.reviewed_at", 1)],

    # 9. Date range queries
    [("created_at", -1)],
]
```

---

## 4. SERVICE CONTRACT

Here is every method you must implement:

### Constructor & Config
```python
class OrderService:
    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100
        self.price_drift_threshold = 0.05   # 5% - max allowed price change
        self.high_value_threshold_cents = 100000  # $1000
        self.velocity_window_hours = 24
        self.velocity_threshold = 5
        self.tax_rate = 0.08                # 8% flat tax
        self.shipping_cost_cents = 599      # $5.99 flat rate
        self.free_shipping_threshold_cents = 5000  # Free shipping over $50
```

### Helper Methods (5 methods)
```python
def _generate_order_number(self) -> str
async def _get_user_order(self, order_id: str, user_id: str) -> Order
async def _validate_product_for_order(self, product_id: str, variant_name: Optional[str], quantity: int) -> Tuple[Product, Optional[Dict]]
async def _validate_promotion(self, promotion_id: str, user_id: str, product_ids: List[str], community_id: Optional[str] = None) -> Optional[Promotion]
def _calculate_totals(self, items_data: List[Dict], promotion: Optional[Promotion] = None) -> Tuple[OrderTotals, List[Dict]]
def _build_product_snapshot(self, product: Product, variant: Optional[Dict]) -> ProductSnapshot
```

### Main Service Methods (6 methods)
```python
async def create_order(self, user_id: str, order_data: Dict[str, Any], idempotency_key: str, ip_address: str, user_agent: Optional[str] = None) -> Order
async def complete_order(self, order_id: str, user_id: str, idempotency_key: str) -> Order
async def cancel_order(self, order_id: str, user_id: str, reason: str) -> Order
async def modify_order(self, order_id: str, user_id: str, updates: Dict[str, Any]) -> Order
async def list_user_orders(self, user_id: str, page_size: int = 20, cursor: Optional[str] = None, status_filter: Optional[List[str]] = None) -> Dict[str, Any]
async def get_order(self, order_id: str, user_id: str) -> Order
async def get_order_by_number(self, order_number: str, user_id: str) -> Order
```

---

## 5. EXERCISES

---

### Exercise 1: Helper Methods - Order Foundations

**MongoDB Concepts**: `Model.get()`, compound `find_one` (anti-enumeration), Product variant/inventory reads, Promotion soft validation

#### Method 1: `_generate_order_number`
```python
def _generate_order_number(self) -> str:
```
**What it does**: Generate a human-readable order number like `ORD-20250203-A1B2`.

```python
date_part = utc_now().strftime("%Y%m%d")
random_part = secrets.token_hex(2).upper()  # 4 hex chars
return f"ORD-{date_part}-{random_part}"
```

> **Note**: This is NOT guaranteed unique (4 hex chars = 65,536 combinations per day). The `order_number` unique index (index #1) catches collisions, and you'd retry with a new random part in production. For this MVP, collisions are statistically unlikely.

#### Method 2: `_get_user_order` (Anti-Enumeration)
```python
async def _get_user_order(self, order_id: str, user_id: str) -> Order:
```
**What it does**: Fetch an order scoped to the requesting user. Same anti-enumeration pattern from Tasks 04-06.

**The query:**
```python
order = await Order.find_one({
    "_id": PydanticObjectId(order_id),
    "customer.user_id": PydanticObjectId(user_id)
})
```

**Steps**:
1. Wrap the `find_one` in try/except - catch `Exception` and raise `ValueError("Invalid order or user ID")` for malformed ObjectIds
2. If `order` is None, raise `ValueError("Order not found")`
3. Return the order

> **Index used**: `[("customer.user_id", 1), ("created_at", -1)]` - index #3 partially covers this query.

#### Method 3: `_validate_product_for_order`
```python
async def _validate_product_for_order(
    self, product_id: str, variant_name: Optional[str], quantity: int
) -> Tuple[Product, Optional[Dict]]:
```
**What it does**: Validate a product is purchasable with sufficient stock.

**Steps**:
1. Fetch product: `await Product.get(PydanticObjectId(product_id))` (wrap in try/except for invalid IDs)
2. Check `product` exists, is not soft-deleted (`deleted_at`), and is `ACTIVE` status
3. **If variant specified**:
   - Call `product.get_variant_by_name(variant_name)` to find the variant
   - Check variant exists and `variant.is_active`
   - Check `variant.available >= quantity` (stock check)
4. **If no variant**: Check `product.get_total_available() >= quantity`
5. Return `(product, variant)` tuple

> **Important**: This method validates at CREATE time. Prices/stock are NOT locked yet - that happens in `complete_order`.

#### Method 4: `_validate_promotion` (Soft Validation)
```python
async def _validate_promotion(
    self, promotion_id: str, user_id: str, product_ids: List[str],
    community_id: Optional[str] = None
) -> Optional[Promotion]:
```
**What it does**: Validate a promotion is applicable. Returns `None` on ANY failure (never raises).

**This is "soft validation"** - a failed promotion shouldn't block the order. The user still gets their products, just without the discount.

**Steps** (return `None` at each failure point, never raise):
1. Fetch promotion: `await Promotion.get(PydanticObjectId(promotion_id))` - return `None` on exception
2. Check not None and not soft-deleted
3. Check status is `ACTIVE` or `SCHEDULED`
4. Check schedule window: `start_date <= now <= end_date`
5. Check visibility: if `COMMUNITIES`, require `community_id` and check it's in `community_ids`
6. Check product overlap: at least one `product_id` must be in the promotion's products
7. Return the promotion (or `None` at any failure)

> **Why soft validation?** In a real e-commerce system, promotion issues should degrade gracefully. A promotional expired 1 second ago? Don't fail the $500 order - just skip the discount. The customer sees the price without discount and can decide.

#### Method 5: `_calculate_totals`
```python
def _calculate_totals(
    self, items_data: List[Dict], promotion: Optional[Promotion] = None
) -> Tuple[OrderTotals, List[Dict]]:
```
**What it does**: Calculate all financial totals and apply per-item discounts.

**Steps**:
1. Loop through items, calculate `subtotal = unit_price_cents * quantity` for each
2. **If promotion applies**: For each item, check if its `product_id` matches any `promotion.products[].product_snapshot.product_id`. If so, calculate `item_discount = int(subtotal * promo_product.discount_percent / 100)`
3. Set `item["discount_cents"]` and `item["final_price_cents"]` on each item dict
4. Calculate tax: `int(taxable_amount * self.tax_rate)` where `taxable_amount = subtotal - total_discount`
5. Calculate shipping: `0` if `taxable_amount >= self.free_shipping_threshold_cents`, else `self.shipping_cost_cents`
6. Build and return `(OrderTotals, updated_items_data)`

#### Method 6: `_build_product_snapshot`
```python
def _build_product_snapshot(self, product: Product, variant: Optional[Dict]) -> ProductSnapshot:
```
**What it does**: Build a `ProductSnapshot` from a Product document and optional variant.

**Steps**:
1. Start with base product data: `product.name`, `product.slug`, `product.metadata.base_sku`, primary image
2. **If variant exists**: Override with variant-specific data (`variant_name`, `variant_attributes` from attributes list, `variant.sku`, `variant.image_url`)
3. Include `supplier_name` from `product.supplier_info.get("name", "Unknown Supplier")`
4. Return `ProductSnapshot`

<details>
<summary>Hints for Exercise 1</summary>

**Hint 1 - _get_user_order**: Note the try/except wrapping the entire `find_one`. If either `order_id` or `user_id` is not a valid ObjectId string, `PydanticObjectId()` will throw. The outer except catches this and raises a clean ValueError.

**Hint 2 - _validate_product_for_order**: `product.get_variant_by_name()` and `product.get_total_available()` are helper methods on the Product model. You don't need to write raw MongoDB queries - just call these model methods.

**Hint 3 - _validate_promotion**: Every check returns `None` instead of raising. This pattern is called "fail-safe defaults" - the system continues without the promotion rather than failing the entire operation.

**Hint 4 - _calculate_totals**: The promotion discount matching uses string comparison: `str(promo_product.product_snapshot.product_id) == item["product_id"]`. Both sides must be strings for the comparison to work.

</details>

---

### Exercise 2: Create Order - The 11-Type Document Build

**MongoDB Concepts**: Idempotency via `find_one`, `User.get()` cross-collection, complex document construction (11 embedded types), `insert()`

#### Method: `create_order`
```python
async def create_order(
    self, user_id: str, order_data: Dict[str, Any],
    idempotency_key: str, ip_address: str, user_agent: Optional[str] = None
) -> Order:
```

**This is the largest single method in the entire project.** It builds an Order with 11 embedded document types from scratch.

**Algorithm** (6 major steps):

#### Step 1: Idempotency Check
```python
existing = await Order.find_one({"idempotency_key": idempotency_key})
if existing:
    return existing  # Return the already-created order
```

> **Why idempotency?** If a network error occurs after the server creates the order but before the client receives the response, the client retries with the same idempotency key. Without this check, the user would be charged twice. With it, the second request just returns the existing order.

> **Index used**: `[("idempotency_key", 1)]` - index #2 (unique).

#### Step 2: Validate User
```python
user = await User.get(PydanticObjectId(user_id))
```
- Check user exists, is not soft-deleted (`user.deleted_at`)
- The user provides the data for `OrderCustomer` (denormalized)

#### Step 3: Validate Products
Loop through `order_data["items"]` and for each:
- Call `self._validate_product_for_order(product_id, variant_name, quantity)`
- Determine `unit_price`: `variant.price_cents` if variant exists, else `product.base_price_cents`
- Collect into `items_data` list

#### Step 4: Validate Promotion (Optional)
```python
attribution_data = order_data.get("attribution", {}) or {}
promotion = None
if attribution_data.get("promotion_id"):
    promotion = await self._validate_promotion(
        attribution_data["promotion_id"], user_id,
        product_ids, attribution_data.get("community_id")
    )
```

#### Step 5: Calculate Totals
```python
totals, items_data = self._calculate_totals(items_data, promotion)
```

#### Step 6: Build Everything and Insert

Build these 11 embedded types:
1. **`OrderItem[]`** - From items_data + `_build_product_snapshot()`
2. **`ProductSnapshot`** (inside each OrderItem) - From Product + variant
3. **`OrderCustomer`** - From User
4. **`ShippingAddress`** - From request
5. **`BillingAddress`** (optional) - From request
6. **`PaymentInfo`** - From request (status = PENDING)
7. **`OrderAudit`** - ip_address, user_agent, risk_score=0.0
8. **`OrderAttribution`** (optional) - From promotion + attribution data
9. **`OrderTotals`** - Calculated above
10. **`OrderTimeline[]`** - Initial entry: `{status: "pending", note: "Order created"}`
11. **`CustomerNote[]`** - Empty initially

```python
order = Order(
    order_number=self._generate_order_number(),
    customer=customer,
    items=order_items,
    totals=totals,
    shipping_address=shipping_address,
    billing_address=billing_address,
    payment=payment,
    status=OrderStatus.PENDING,
    audit=audit,
    attribution=order_attribution,
    idempotency_key=idempotency_key,
    timeline=[OrderTimeline(status="pending", timestamp=utc_now(), note="Order created")]
)

await order.insert()
```

Emit Kafka event: `order.created`

<details>
<summary>Hints for Exercise 2</summary>

**Hint 1 - OrderCustomer**: Built from user data:
```python
customer = OrderCustomer(
    user_id=user.id,
    display_name=user.profile.display_name if user.profile else "Customer",
    email=user.contact_info.primary_email,
    phone=user.contact_info.phone if user.contact_info else None
)
```

**Hint 2 - PaymentMethod enum**: The request sends a string like `"credit_card"`. Wrap in try/except when converting to enum: `PaymentMethod(payment_data["payment_method"])`, default to `PaymentMethod.CREDIT_CARD` on invalid values.

**Hint 3 - item_id**: Each OrderItem gets a sequential `item_id`: `f"item_{i+1}"`. This is used later for per-item tracking and refunds.

**Hint 4 - Order of operations**: Build items_data first (with product validation), then calculate totals (applies discounts), then build OrderItem objects (with the discount info from totals calculation). The order matters because `_calculate_totals` mutates the items_data dicts to add `discount_cents` and `final_price_cents`.

</details>

---

### Exercise 3: Complete Order - Price Drift + Inventory Reservation

**MongoDB Concepts**: Product re-fetch, percentage-based comparison, inventory model methods, manual rollback pattern, payment mock, Promotion cross-collection write-back

This is the **most complex method** in the service. It transforms a PENDING order into a CONFIRMED one by re-validating prices, reserving inventory, and authorizing payment.

#### Method: `complete_order`
```python
async def complete_order(
    self, order_id: str, user_id: str, idempotency_key: str
) -> Order:
```

**Algorithm** (6 steps):

#### Step 1: Fetch and Validate State
```python
order = await self._get_user_order(order_id, user_id)
```
- If `order.status == OrderStatus.CONFIRMED`: **return order** (idempotent - already completed)
- If `order.status != OrderStatus.PENDING`: raise error
- If `order.payment.status != PaymentStatus.PENDING`: raise error

#### Step 2: Re-Validate Pricing (PRICE DRIFT DETECTION)

For each item in `order.items`:
```python
product = await Product.get(item.product_snapshot.product_id)
```
- Check product still exists and is ACTIVE
- Get current price (check variant if applicable)
- **Calculate drift**:
  ```python
  drift = abs(current_price - original_price) / original_price
  if drift > self.price_drift_threshold:  # 0.05 = 5%
      raise ValueError(f"Price for '{name}' has changed significantly. "
                       f"Original: ${original/100:.2f}, Current: ${current/100:.2f}")
  ```

> **Why 5% threshold?** Small price fluctuations (rounding, tax adjustments) shouldn't block orders. But a significant change (price doubled, sale ended) means the customer should re-review their cart. The threshold is configurable via `self.price_drift_threshold`.

#### Step 3: Reserve Inventory (WITH ROLLBACK)

This is the most complex part - a manual transaction pattern:

```python
reserved_items = []  # Track what we've reserved for rollback
try:
    for item in order.items:
        product = await Product.get(item.product_snapshot.product_id)

        if item.product_snapshot.variant_name:
            success = await product.reserve_variant_inventory(
                item.product_snapshot.variant_name, item.quantity
            )
        else:
            # Reserve from first location with enough stock
            for location in product.stock_locations:
                if location.available >= item.quantity:
                    success = await product.reserve_location_inventory(
                        location.location_id, item.quantity
                    )
                    if success:
                        break

        if not success:
            raise ValueError(f"Insufficient stock for '{item.product_snapshot.product_name}'")

        reserved_items.append((product, item))

except ValueError:
    # ROLLBACK: Release all previously reserved items
    for product, item in reserved_items:
        try:
            if item.product_snapshot.variant_name:
                await product.release_variant_inventory(
                    item.product_snapshot.variant_name, item.quantity
                )
            else:
                for location in product.stock_locations:
                    await product.release_location_inventory(
                        location.location_id, item.quantity
                    )
                    break
        except Exception:
            pass  # Best-effort rollback
    raise  # Re-raise the original error
```

> **Why manual rollback?** MongoDB doesn't have cross-document transactions in the traditional RDBMS sense. Each `reserve_variant_inventory()` call updates a separate Product document. If item 3 fails, we must manually undo items 1 and 2. The `reserved_items` list tracks what needs to be undone.

#### Step 4: Authorize Payment (Mock)
```python
order.payment.status = PaymentStatus.AUTHORIZED
order.payment.authorized_at = utc_now()
order.payment.transaction_id = f"mock_txn_{order.order_number}"
order.payment.authorization_code = f"AUTH_{secrets.token_hex(4).upper()}"
```

#### Step 5: Update Order Status
```python
order.status = OrderStatus.CONFIRMED
order.timeline.append(OrderTimeline(
    status="confirmed",
    timestamp=utc_now(),
    note="Payment authorized and inventory reserved"
))
await order.save()
```

#### Step 6: Record Promotion Conversion
```python
if order.attribution and order.attribution.promotion_id:
    try:
        promotion = await Promotion.get(order.attribution.promotion_id)
        if promotion:
            await promotion.record_conversion(
                order.totals.total_cents,
                str(order.attribution.community_id) if order.attribution.community_id else None
            )
    except Exception:
        pass  # Don't fail order completion on analytics error
```

> **Cross-collection write-back**: After confirming the order, we update the Promotion's stats. This is a best-effort operation wrapped in try/except - if it fails, the order is still valid. The analytics are eventually consistent.

<details>
<summary>Hints for Exercise 3</summary>

**Hint 1 - Idempotent confirm**: If the order is already CONFIRMED, return it immediately. This handles retries where the first complete_order succeeded but the client didn't receive the response.

**Hint 2 - Price drift formula**: `drift = abs(current - original) / original`. This catches BOTH increases and decreases. A product going from $100 to $94 has drift = 0.06 (6%), which exceeds the 5% threshold.

**Hint 3 - Location-based reservation**: When no variant is specified, you need to find a stock location with enough inventory. Loop through `product.stock_locations` and try the first one where `location.available >= item.quantity`.

**Hint 4 - Best-effort rollback**: The `except Exception: pass` in rollback is intentional. If a release fails (network error, product deleted, etc.), there's nothing more we can do. A background reconciliation job would handle orphaned reservations in production.

**Hint 5 - Promotion conversion**: `promotion.record_conversion()` is a model method that increments `stats.conversions`, adds `revenue_cents`, and updates community breakdown. You don't write the MongoDB query - just call the model method.

</details>

---

### Exercise 4: Cancel Order - Inventory Release

**MongoDB Concepts**: Model helper delegation (`can_be_cancelled()`, `cancel_order()`), conditional inventory release, payment voiding

#### Method: `cancel_order`
```python
async def cancel_order(self, order_id: str, user_id: str, reason: str) -> Order:
```

**Algorithm**:

1. **Fetch with ownership**: `await self._get_user_order(order_id, user_id)`

2. **Check cancellability**: `if not order.can_be_cancelled():` raise error
   - Model's `can_be_cancelled()` returns True only for PENDING or CONFIRMED AND not shipped

3. **Release inventory** (only if CONFIRMED - PENDING had no reservations):
   ```python
   if order.status == OrderStatus.CONFIRMED:
       for item in order.items:
           product = await Product.get(item.product_snapshot.product_id)
           if product:
               # Release variant or location inventory (best effort)
   ```

4. **Void payment** (if authorized):
   ```python
   if order.payment.status == PaymentStatus.AUTHORIZED:
       order.payment.status = PaymentStatus.PENDING  # Voided
   ```

5. **Delegate to model**: `await order.cancel_order(reason, user_id)`
   - Sets status to CANCELLED, cancels all item fulfillment statuses, adds timeline event

6. **Emit Kafka event**: `order.cancelled`

<details>
<summary>Hints for Exercise 4</summary>

**Hint 1 - PENDING vs CONFIRMED cancel**: A PENDING order has no inventory reserved and no payment authorized. It's just a cart. Cancelling it is simple - just update the status. A CONFIRMED order needs inventory released and payment voided before cancelling.

**Hint 2 - Best-effort release**: Same pattern as the rollback in `complete_order`. Each product release is wrapped in try/except. If one fails, continue releasing the others.

**Hint 3 - Payment void**: In the MVP, "voiding" just resets `payment.status` to PENDING. In a real system, you'd call the payment provider's void API.

</details>

---

### Exercise 5: Modify Order - Pending-Only Updates

**MongoDB Concepts**: Status guard, conditional product re-validation, totals recalculation, embedded document replacement

#### Method: `modify_order`
```python
async def modify_order(self, order_id: str, user_id: str, updates: Dict[str, Any]) -> Order:
```

**Key constraint**: Only PENDING orders with PENDING payment can be modified.

**Algorithm**:

1. **Fetch and guard**:
   ```python
   order = await self._get_user_order(order_id, user_id)
   if order.status != OrderStatus.PENDING:
       raise ValueError("Only pending orders can be modified")
   if order.payment.status != PaymentStatus.PENDING:
       raise ValueError("Cannot modify order with processed payment")
   ```

2. **Update shipping address** (if provided): Build new `ShippingAddress` from dict

3. **Update billing address** (if provided): Build new `BillingAddress` or set to `None`

4. **Update items** (if provided) - this requires full recalculation:
   - Re-validate each product (using `_validate_product_for_order`)
   - Re-fetch promotion (if order had attribution)
   - Recalculate totals (using `_calculate_totals`)
   - Rebuild all `OrderItem` objects

5. **Add timeline event**: `{status: "modified", note: "Order modified by customer"}`

6. **Save**: `await order.save()`

<details>
<summary>Hints for Exercise 5</summary>

**Hint 1 - Item replacement**: When items change, you rebuild the ENTIRE `order.items` list and recalculate `order.totals`. There's no partial item update - it's all-or-nothing for the items array.

**Hint 2 - Promotion re-fetch**: If the order has `order.attribution.promotion_id`, re-fetch the promotion with `Promotion.get()` for discount recalculation. The promotion might have expired since creation, which is fine - `_calculate_totals` handles a `None` promotion gracefully (no discounts applied).

</details>

---

### Exercise 6: List & Get Orders - Cursor Pagination + Dual Lookup

**MongoDB Concepts**: Cursor pagination with `$lt` (descending!), `$in` status filter, compound `find_one` on unique field + ownership

#### Method 1: `list_user_orders` (DESCENDING CURSOR)
```python
async def list_user_orders(
    self, user_id: str, page_size: int = 20,
    cursor: Optional[str] = None, status_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
```

**This cursor goes BACKWARDS (newest first):**
```python
query = {"customer.user_id": PydanticObjectId(user_id)}

if status_filter:
    query["status"] = {"$in": status_filter}

if cursor:
    query["_id"] = {"$lt": PydanticObjectId(cursor)}  # $lt, not $gt!

orders = await Order.find(query).sort("-created_at").limit(page_size + 1).to_list()
```

**Why `$lt` instead of `$gt`?** The sort is `-created_at` (descending - newest first). ObjectIds are monotonically increasing, so the "next page" has SMALLER (older) IDs. The cursor points to the last item on the current page, and we want items with IDs LESS THAN that.

> **Contrast with TASK_05**: Post feeds used `$gt` with ascending sort (oldest published first). Order lists use `$lt` with descending sort (newest first). The cursor direction must match the sort direction.

**Pagination pattern** (same limit+1 trick):
```python
has_more = len(orders) > page_size
if has_more:
    orders = orders[:-1]
next_cursor = str(orders[-1].id) if has_more and orders else None
```

Return:
```python
{
    "orders": orders,
    "pagination": {
        "next_cursor": next_cursor,
        "has_more": has_more,
        "page_size": page_size
    }
}
```

#### Method 2: `get_order`
```python
async def get_order(self, order_id: str, user_id: str) -> Order:
```
Just delegates to `_get_user_order`. One line.

#### Method 3: `get_order_by_number` (UNIQUE FIELD LOOKUP)
```python
async def get_order_by_number(self, order_number: str, user_id: str) -> Order:
```

**The query:**
```python
order = await Order.find_one({
    "order_number": order_number.upper(),
    "customer.user_id": PydanticObjectId(user_id)
})
```

**Why `.upper()`?** The model's `@field_validator` uppercases order numbers on save. The query must match: `"ord-20250203-a1b2"` -> `"ORD-20250203-A1B2"`.

> **Two lookup strategies**: `get_order` uses the internal `_id` (machine-friendly, in URLs). `get_order_by_number` uses the human-readable `order_number` (shown on receipts, in customer emails). Both include `customer.user_id` for anti-enumeration.

> **Index used**: `[("order_number", 1)]` - index #1 (unique). Combined with `customer.user_id`, this is an efficient query.

<details>
<summary>Hints for Exercise 6</summary>

**Hint 1 - Cursor direction table**:
| Sort | Cursor operator | Example |
|------|----------------|---------|
| Ascending (`_id`) | `$gt` | "Give me items AFTER this cursor" |
| Descending (`-created_at`) | `$lt` | "Give me items BEFORE this cursor" |

**Hint 2 - Invalid cursor handling**: Wrap the cursor conversion in try/except. If the cursor string isn't a valid ObjectId, just ignore it (don't add `$lt` to the query).

**Hint 3 - get_order**: This is intentionally trivial - `return await self._get_user_order(order_id, user_id)`. The route uses this method name for clarity, but it's just a pass-through.

</details>

---

## 6. VERIFICATION CHECKLIST

### Exercise 1: Helpers
```bash
# _generate_order_number produces format ORD-YYYYMMDD-XXXX
# _get_user_order with wrong user_id -> ValueError
# _validate_product_for_order with deleted product -> ValueError
# _validate_product_for_order with insufficient stock -> ValueError
# _validate_promotion with expired promotion -> returns None (no error!)
# _calculate_totals with promotion -> discounts applied per item
# _calculate_totals without promotion -> no discounts
```

### Exercise 2: Create Order
```bash
POST /orders
Headers: X-User-ID: <your_user_id>, X-Idempotency-Key: <unique_key>
{
  "items": [{"product_id": "<id>", "quantity": 2}],
  "shipping_address": {
    "recipient_name": "John Doe",
    "street_address_1": "123 Main St",
    "city": "New York", "state": "NY",
    "zip_code": "10001", "country": "US"
  },
  "payment_info": {"payment_method": "credit_card", "card_last4": "4242", "card_brand": "Visa"}
}
# Expect: 201, status="pending", totals calculated, order_number generated

# IDEMPOTENCY TEST: Send same request with same X-Idempotency-Key
# Expect: 201, SAME order returned (not a new one!)
```

### Exercise 3: Complete Order
```bash
POST /orders/complete
Headers: X-User-ID: <your_user_id>, X-Idempotency-Key: <key>
{"order_id": "<id>"}
# Expect: status="confirmed", payment.status="authorized", timeline has "confirmed" entry

# IDEMPOTENCY TEST: Call complete again
# Expect: Same confirmed order returned (idempotent)

# PRICE DRIFT TEST: Change product price > 5%, then complete
# Expect: 409 PRICE_DRIFT error
```

### Exercise 4: Cancel Order
```bash
POST /orders/cancel
{"order_id": "<id>", "reason": "Changed my mind"}
# For PENDING order: Expect cancelled, no inventory changes
# For CONFIRMED order: Expect cancelled, inventory released, payment voided
# For SHIPPED order: Expect error (cannot cancel)
```

### Exercise 5: Modify Order
```bash
POST /orders/update
{"order_id": "<id>", "shipping_address": {...new address...}}
# Expect: address updated, timeline has "modified" entry
# Try on CONFIRMED order -> error (only pending can be modified)
```

### Exercise 6: List & Get
```bash
# List orders
GET /orders/list?limit=10
# Expect: Newest first, cursor pagination

# Get by ID
POST /orders/get  {"order_id": "<id>"}
# Expect: Full order detail

# Get by order number
POST /orders/get-by-number  {"order_number": "ORD-20250203-A1B2"}
# Expect: Same order, looked up by human-readable number

# Try another user's order -> 404 (anti-enumeration)
```

---

## 7. ADVANCED CHALLENGES

### Challenge 1: The Inventory Reservation Race Condition

Two users attempt to buy the last item simultaneously:

```
Inventory: Widget - 1 available

T1: User A's create_order validates stock  -> 1 available -> OK
T2: User B's create_order validates stock  -> 1 available -> OK
T3: User A's complete_order reserves 1     -> 0 available -> OK
T4: User B's complete_order reserves 1     -> -1 available -> ???
```

**Questions**:
1. Does `reserve_variant_inventory()` use atomic operations (`$inc` with conditions)? Check the Product model. What happens at T4?
2. If it doesn't check atomically, design a MongoDB `findOneAndUpdate` query with a `$gte` condition that would prevent negative inventory:
   ```javascript
   db.products.findOneAndUpdate(
     { _id: productId, "stock_locations.available": { $gte: quantity } },
     { $inc: { "stock_locations.$.available": -quantity, "stock_locations.$.reserved": quantity } }
   )
   ```
3. How would MongoDB's **multi-document transactions** (available in replica sets) solve this more completely? What would the transaction span?

### Challenge 2: Idempotency Key Uniqueness

The `idempotency_key` index is unique. What if two concurrent requests arrive with the same key?

```
T1: Request A does find_one(idempotency_key) -> None
T2: Request B does find_one(idempotency_key) -> None
T3: Request A inserts order with key          -> Success
T4: Request B inserts order with key          -> DuplicateKeyError!
```

**Questions**:
1. The current code doesn't handle `DuplicateKeyError`. What does the user see?
2. Design a retry loop that catches `DuplicateKeyError`, re-fetches the existing order by idempotency key, and returns it:
   ```python
   try:
       await order.insert()
   except DuplicateKeyError:
       existing = await Order.find_one({"idempotency_key": idempotency_key})
       return existing
   ```
3. Should the idempotency key have a TTL? What problems arise if a user accidentally reuses a key from 6 months ago?

### Challenge 3: Cross-Collection Consistency

The order creation reads from 4 collections (User, Product, Promotion, Order) and the completion writes to 3 (Order, Product inventory, Promotion stats). None of this is in a transaction.

**Questions**:
1. List all the possible inconsistent states if the server crashes between steps in `complete_order`:
   - After reserving item 1 but before reserving item 2?
   - After reserving all items but before saving the order status?
   - After saving the order but before recording the promotion conversion?
2. Which inconsistencies are acceptable (eventually consistent) and which are dangerous (money/inventory loss)?
3. Design a **saga pattern** with compensating actions for each step. What "undo" operation corresponds to each forward step?

---

## 8. WHAT'S NEXT?

You've built the final transactional service! The Order service ties together every entity in the platform.

**What you've mastered in this task**:
- Idempotency via `find_one` on a unique key
- Two-phase order flow (create PENDING -> complete CONFIRMED)
- Price drift detection with configurable thresholds
- Inventory reservation with manual rollback
- Cross-collection reads from 4 different collections
- Complex document construction with 11 embedded types
- Cursor pagination with descending direction (`$lt`)
- Dual lookup strategies (by `_id` and by unique field)
- Soft validation (return None, never raise)
- Cross-collection write-back for analytics

**Your next task**: `TASK_08_ANALYTICS.md` - Aggregation Pipeline Exercises. You'll move beyond `find()` queries and build MongoDB **aggregation pipelines** using `$group`, `$match`, `$project`, `$unwind`, `$lookup`, and `$facet` to generate platform analytics across all the data you've created.
