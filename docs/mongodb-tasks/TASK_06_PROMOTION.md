# TASK 06: Promotion Service - Marketing Campaigns & Approval Workflows

## 1. MISSION BRIEFING

Promotions are the **monetization engine** of the platform. Suppliers create marketing campaigns (single-product discounts or multi-product bundles) that appear on community feeds and the global timeline. Every promotion goes through a **7-status lifecycle** with a **multi-scope approval system** - global admins approve for the main feed, community leaders approve for their communities, and the system auto-transitions between scheduled/active states based on dates.

This is the **most operationally complex service** you've built. The Promotion model has 10 embedded document types, a 7-status state machine, a dual-scope approval workflow (global + per-community), cross-collection validation against both Suppliers and Products, and two completely different pagination strategies - **skip-based** for management endpoints and **cursor-based** for feed endpoints.

### What You Will Build
The `PromotionService` class - ~20 methods covering helpers, CRUD, a 7-status lifecycle, multi-scope approval/rejection, 4 lifecycle transitions (pause/resume/cancel/end), public feed queries with date ranges and dynamic key lookups, and admin operations.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Skip-based pagination** | `list_promotions` and `list_pending_approvals` - `skip()`, `limit()`, `.count()`, page math |
| **Cursor-based pagination** | Feed endpoints - `limit + 1` pattern with `_id` cursor |
| **`$in` on nested fields** | `products.product_snapshot.product_id` - querying inside array of embedded docs |
| **`$ne` for exclusion** | Excluding current promotion when checking active conflicts |
| **Nested field queries** | `supplier.supplier_id`, `visibility.type`, `schedule.start_date`, `approval.global_approval.status` |
| **Dynamic key queries** | `approval.community_approvals.{community_id}.status` - computed field path! |
| **`$lte` / `$gte` date ranges** | Schedule filtering: promotions active between start and end dates |
| **Multi-condition compound queries** | Feed: status + deleted_at + visibility + schedule dates + approval status |
| **Cross-collection validation** | Supplier (existence + status + verification) AND Products (ownership + status) |
| **Denormalized snapshots** | `SupplierInfo` from Supplier, `ProductSnapshot` from Product (frozen at creation) |
| **Hard delete vs soft delete** | `promotion.delete()` for unsent drafts vs `cancel_promotion()` for sent ones |
| **`can_delete()` tuple pattern** | Model method returns `(bool, error_code)` - 3 distinct failure modes |
| **Optimistic locking** | Version check on every mutation (update, delete, all lifecycle transitions) |
| **Status-based edit permissions** | Draft: full edit. Paused: limited fields only. Others: blocked |
| **Anti-enumeration** | `supplier.supplier_id` in query prevents discovering other suppliers' promotions |

### How This Differs From Previous Tasks

| Aspect | Product (04) | Post (05) | Promotion (06) |
|--------|-------------|-----------|----------------|
| Embedded doc types | 8 | 7 | **10** |
| State machine states | 5 | 4 + 5 (distribution) | **7** (single but most complex) |
| Pagination | Cursor only | Cursor only | **Both skip AND cursor** |
| Approval workflow | None | Change requests | **Multi-scope**: global + per-community |
| Collections touched | 2 | 4 | **3** (promotions + suppliers + products) |
| Delete strategy | Soft only | Soft only | **Hard delete OR soft delete** based on `is_sent` |
| Edit restrictions | No restrictions | Author/leader/admin | **Status-based**: different fields per status |
| Feed queries | Public catalog | Home feed `$or`+`$and` | **Date ranges + dynamic keys + nested approval** |
| Lifecycle ops | 4 transitions | 2 state machines | **7 transitions** (submit/approve/reject/pause/resume/cancel/end) |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_02 (Supplier) must be complete** - Promotions require a verified supplier
- **TASK_04 (Product) must be complete** - Promotions reference products with snapshots
- Have at least one verified supplier with 2-3 active products from previous tasks

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/promotion.py` | 804 lines - 10 embedded types, 7-status lifecycle, multi-scope approval, 12 indexes |
| 2 | `apps/backend-service/src/schemas/promotion.py` | 381 lines - Request/response schemas for CRUD, lifecycle, admin, and feeds |
| 3 | `apps/backend-service/src/routes/promotion.py` | 462 lines - CRUD + 6 lifecycle + 2 public feed endpoints |
| 4 | `shared/models/supplier.py` | Cross-collection reference - supplier validation |
| 5 | `shared/models/product.py` | Cross-collection reference - product ownership and snapshots |

### The Data Flow

```
HTTP Request (Supplier JWT)
    |
    v
+-----------+   Extracts supplier_id from
|  Route    |   X-Supplier-ID header
|           |
|  Calls    |
|  your     |
|  service  |
    |
    v
+--------------------------------------------------------------+
|              PromotionService (YOU WRITE THIS)                |
|                                                               |
|  Reads from THREE collections:                                |
|    1. Promotion  (main CRUD + lifecycle)                      |
|    2. Supplier   (validation: exists, active, verified)       |
|    3. Product    (ownership validation + snapshot data)       |
|                                                               |
|  TWO pagination strategies:                                   |
|    - Skip-based:  list_promotions, list_pending_approvals     |
|    - Cursor-based: get_global_feed, get_community_feed        |
|                                                               |
|  Returns Promotion documents                                  |
+--------------------------------------------------------------+
    |
    v
+-----------+   Route transforms Promotion -> response schemas
|  Route    |   using utils/promotion_utils.py
+-----------+
```

### The 7-Status Lifecycle

```
                          submit_for_approval()
    DRAFT ──────────────────────────────> PENDING_APPROVAL
      ^                                        |
      |  reject()                              | approve() (all scopes)
      |  (returns to draft)                    |
      +────────────────────────────────────────+
                                               |
                              ┌─────────── is start_date <= now?
                              |                |
                              | YES            | NO
                              v                v
                           ACTIVE         SCHEDULED
                           |    ^              |
              pause()      |    |  resume()    | (background job activates)
                           v    |              |
                          PAUSED               +
                                               |
              end()                            v
           ACTIVE ──────────────────────> ENDED

              cancel()
           ANY* ────────────────────────> CANCELLED
                                          (sets deleted_at)

  * Cannot cancel ENDED promotions
  * Cannot cancel auto-generated promotions
```

### The Approval System

```
Visibility: GLOBAL           ->  Needs: global_approval only
Visibility: COMMUNITIES      ->  Needs: community_approvals[each_id] only
Visibility: BOTH             ->  Needs: global_approval AND community_approvals[each_id]

When ALL required approvals are APPROVED:
  - If now >= start_date  ->  status = ACTIVE  (+ set first_activated_at)
  - If now < start_date   ->  status = SCHEDULED

When ANY approval is REJECTED:
  - status = DRAFT  (supplier can edit and resubmit)
  - rejection recorded in rejection_history[]
```

---

## 3. MODEL DEEP DIVE

### The Promotion Document (10 Embedded Types)

```python
class Promotion(Document):
    # Type
    promotion_type: PromotionType          # campaign | single | default

    # Supplier (denormalized)
    supplier: SupplierInfo                 # {supplier_id, business_name, logo}

    # Content
    title: str
    description: str
    banner_image: str

    # Products (1 for single/default, 2-3 for campaign)
    products: List[PromotionProduct]       # [{product_snapshot, discount_percent, ...}]

    # Targeting
    visibility: PromotionVisibility        # {type, community_ids, is_global, ...}
    schedule: PromotionSchedule            # {start_date, end_date, timezone}

    # Status & lifecycle
    status: PromotionStatus                # 7 possible values
    status_reasons: List[str]              # Audit trail of transitions
    terms: Optional[PromotionTerms]        # {terms_text, restrictions, ...}
    stats: PromotionStats                  # {impressions, clicks, conversions, ...}
    is_auto_generated: bool                # System-created promotions are protected

    # Approval
    approval: ApprovalInfo                 # {global_approval, community_approvals: Dict}
    rejection_history: List[RejectionRecord]

    # Lifecycle tracking
    first_activated_at: Optional[datetime] # Immutable! Defines "is_sent"
    paused_at: Optional[datetime]
    cancellation_reason: Optional[str]

    # Infrastructure
    deleted_at: Optional[datetime]         # Soft delete (cancellation)
    version: int                           # Optimistic locking
    created_at: datetime
    updated_at: datetime
```

### Key Embedded Types to Know

```python
# Frozen product data at creation time
class ProductSnapshot(BaseModel):
    product_id: PydanticObjectId
    product_name: str
    product_slug: str
    product_image: str
    original_price_cents: int
    currency: str
    snapshot_at: datetime

# Product in promotion with discount
class PromotionProduct(BaseModel):
    product_snapshot: ProductSnapshot       # Immutable snapshot
    discount_percent: int                   # 0-100
    discounted_price_cents: int             # Calculated at creation
    current_status: str                     # Updated by background job
    current_price_cents: Optional[int]

# Multi-scope approval tracking
class ApprovalInfo(BaseModel):
    global_approval: Optional[ApprovalRecord]
    community_approvals: Dict[str, ApprovalRecord]  # key = community_id string

    def is_fully_approved(visibility) -> bool  # Checks all required scopes
    def get_pending_approvals(visibility) -> List[str]  # Lists pending scopes
```

### Index Inventory (12 indexes - study these!)

```python
indexes = [
    # 1. Supplier's promotions (list_promotions query)
    [("supplier.supplier_id", 1), ("status", 1), ("created_at", -1)],

    # 2-3. Active promotions by schedule dates (feed date range queries)
    [("status", 1), ("schedule.start_date", 1)],
    [("status", 1), ("schedule.end_date", 1)],

    # 4. Type filtering
    [("promotion_type", 1), ("status", 1)],

    # 5. Community promotions (multikey on community_ids array)
    [("visibility.community_ids", 1), ("status", 1)],

    # 6. Auto-generated flag
    [("is_auto_generated", 1), ("status", 1)],

    # 7. Product conflict check ($in on nested product_id)
    [("products.product_snapshot.product_id", 1), ("status", 1)],

    # 8. Soft delete filter
    [("deleted_at", 1)],

    # 9. Performance sorting
    [("stats.conversions", -1), ("status", 1)],

    # 10. Approval queue
    [("status", 1), ("visibility.type", 1), ("created_at", 1)],

    # 11. Sent tracking
    [("first_activated_at", 1)],

    # 12. Feed compound (global feed query)
    [("status", 1), ("visibility.type", 1), ("schedule.start_date", 1),
     ("schedule.end_date", 1), ("deleted_at", 1)],
]
```

---

## 4. SERVICE CONTRACT

Here is every method you must implement, grouped by category:

### Helper Methods (6 methods)
```python
async def _get_supplier(self, supplier_id: str) -> Supplier
async def _check_supplier_can_create(self, supplier: Supplier) -> None
async def _validate_product_ownership(self, supplier_id: str, product_ids: List[str]) -> List[Product]
async def _check_product_active_promotion(self, product_ids: List[str], exclude_promotion_id: Optional[str] = None) -> None
def _build_product_snapshot(self, product: Product) -> ProductSnapshot
def _calculate_discounted_price(self, original_cents: int, discount_percent: int) -> int
```

### CRUD (6 methods)
```python
async def create_promotion(self, supplier_id: str, promotion_data: Dict[str, Any]) -> Promotion
async def get_promotion(self, promotion_id: str, supplier_id: str) -> Promotion
async def get_promotion_by_id(self, promotion_id: str) -> Promotion
async def list_promotions(self, supplier_id: str, page=1, limit=20, status_filter=None, type_filter=None, include_deleted=False) -> Dict[str, Any]
async def update_promotion(self, promotion_id: str, supplier_id: str, version: int, updates: Dict[str, Any]) -> Promotion
async def delete_promotion(self, promotion_id: str, supplier_id: str, version: int) -> None
```

### Approval Workflow (3 methods)
```python
async def submit_for_approval(self, promotion_id: str, supplier_id: str, version: int) -> Promotion
async def approve_promotion(self, promotion_id: str, reviewer_id: str, reviewer_type: str, scope: str, version: int, community_id=None, notes=None) -> Promotion
async def reject_promotion(self, promotion_id: str, reviewer_id: str, reviewer_type: str, scope: str, reason: str, version: int, community_id=None) -> Promotion
```

### Lifecycle Operations (4 methods)
```python
async def pause_promotion(self, promotion_id: str, supplier_id: str, version: int, reason: str) -> Promotion
async def resume_promotion(self, promotion_id: str, supplier_id: str, version: int) -> Promotion
async def cancel_promotion(self, promotion_id: str, supplier_id: str, version: int, reason: str) -> Promotion
async def end_promotion(self, promotion_id: str, supplier_id: str, version: int) -> Promotion
```

### Feed & Admin (3 methods)
```python
async def get_global_feed_promotions(self, limit: int = 20, cursor: Optional[str] = None) -> Dict[str, Any]
async def get_community_feed_promotions(self, community_id: str, limit: int = 20, cursor: Optional[str] = None) -> Dict[str, Any]
async def list_pending_approvals(self, page=1, limit=20, visibility_filter=None, community_id_filter=None) -> Dict[str, Any]
```

---

## 5. EXERCISES

---

### Exercise 1: Helper Methods - The Foundation Layer

**MongoDB Concepts**: `Supplier.get()`, compound `find_one` in a loop, `$in` on nested field, `$ne` exclusion

These 6 helpers are called by almost every method in the service. Build them first.

#### Method 1: `_get_supplier`
```python
async def _get_supplier(self, supplier_id: str) -> Supplier:
```
**What it does**: Fetch a supplier by ID, raise ValueError if not found.

**Steps**:
1. Use `Supplier.get(PydanticObjectId(supplier_id))` to fetch
2. If not found, raise `ValueError("Supplier not found")`
3. Return the supplier

> **Beanie Tip**: `Model.get(id)` is shorthand for `find_one({"_id": id})`. It returns `None` if not found, never raises.

#### Method 2: `_check_supplier_can_create`
```python
async def _check_supplier_can_create(self, supplier: Supplier) -> None:
```
**What it does**: Validate supplier is allowed to create promotions.

**Steps**:
1. Check `supplier.status.value != "active"` -> raise ValueError("Supplier account is not active")
2. Check `supplier.verification.verification_status.value != "verified"` -> raise ValueError("Supplier must be verified to create promotions")

#### Method 3: `_validate_product_ownership`
```python
async def _validate_product_ownership(self, supplier_id: str, product_ids: List[str]) -> List[Product]:
```
**What it does**: Verify all products exist and belong to this supplier.

**Steps**:
1. Loop through each `pid` in `product_ids`
2. For each, run a **compound `find_one`**:
   ```python
   product = await Product.find_one({
       "_id": PydanticObjectId(pid),
       "supplier_id": PydanticObjectId(supplier_id)
   })
   ```
3. If not found, raise `ValueError(f"Product {pid} not found or not owned by supplier")`
4. If `product.status == ProductStatus.DELETED`, raise `ValueError(f"Product {pid} has been deleted")`
5. Collect and return the list of products

> **Why compound find_one?** A single query with both `_id` AND `supplier_id` prevents a supplier from referencing another supplier's product. If we only checked `_id`, a malicious supplier could include any product.

#### Method 4: `_check_product_active_promotion` (THE `$in` ON NESTED FIELD)
```python
async def _check_product_active_promotion(self, product_ids: List[str], exclude_promotion_id: Optional[str] = None) -> None:
```
**What it does**: Check that none of the products already have an ACTIVE promotion.

**This is the key MongoDB technique here:**
```python
query = {
    "products.product_snapshot.product_id": {
        "$in": [PydanticObjectId(pid) for pid in product_ids]
    },
    "status": PromotionStatus.ACTIVE
}
```

**Why this query is interesting:**
- `products` is a **List** of `PromotionProduct` objects
- Each `PromotionProduct` contains a `product_snapshot` object
- Each `product_snapshot` has a `product_id` field
- MongoDB's dot notation reaches into `array[*].nested_object.field`
- `$in` then checks if ANY element in the products array has a matching product_id

**Steps**:
1. Build the query above
2. If `exclude_promotion_id` is provided, add `"_id": {"$ne": PydanticObjectId(exclude_promotion_id)}` to the query
3. Run `Promotion.find_one(query)` - we only need to know IF a conflict exists
4. If a match is found, extract the conflicting product IDs and raise with details

> **Index used**: `[("products.product_snapshot.product_id", 1), ("status", 1)]` - index #7

#### Method 5: `_build_product_snapshot`
```python
def _build_product_snapshot(self, product: Product) -> ProductSnapshot:
```
**What it does**: Create an immutable snapshot of product data. This is a **sync** method (no `await`).

Build and return a `ProductSnapshot` with:
- `product_id=product.id`
- `product_name=product.name`
- `product_slug=product.slug`
- `product_image=str(product.images.primary_image) if product.images else ""`
- `original_price_cents=product.base_price_cents`
- `currency=product.currency`
- `snapshot_at=utc_now()`

#### Method 6: `_calculate_discounted_price`
```python
def _calculate_discounted_price(self, original_cents: int, discount_percent: int) -> int:
```
**What it does**: Pure math - calculate the price after discount (in cents).

If discount is 0, return original. Otherwise: `original - int(original * discount / 100)`.

**Verification**:
```bash
# After implementing, these should pass:
# _calculate_discounted_price(10000, 20) == 8000  (20% off $100.00)
# _calculate_discounted_price(10000, 0) == 10000  (no discount)
# _calculate_discounted_price(999, 10) == 900     (truncated, not rounded)
```

<details>
<summary>Hints for Exercise 1</summary>

**Hint 1 - _validate_product_ownership**: The loop-based approach is intentional. We need to validate EACH product individually (clear error per product) and return them in order for snapshot building.

**Hint 2 - _check_product_active_promotion**: The `$ne` exclusion is critical for the UPDATE path. When updating a promotion's products, you need to check for conflicts EXCLUDING the promotion being updated, otherwise it would always conflict with itself.

**Hint 3 - _build_product_snapshot**: The snapshot is immutable by design. Even if the product's price changes later, the promotion remembers the original price at creation time. The `current_price_cents` field on `PromotionProduct` is updated by a background job, not by you.

</details>

---

### Exercise 2: Create Promotion - The Big Build

**MongoDB Concepts**: Cross-collection validation chain, complex document construction with 10 embedded types, `insert()`

#### Method: `create_promotion`
```python
async def create_promotion(self, supplier_id: str, promotion_data: Dict[str, Any]) -> Promotion:
```

**Algorithm** (15 steps):

1. **Get and validate supplier** (uses helpers 1 + 2):
   ```python
   supplier = await self._get_supplier(supplier_id)
   await self._check_supplier_can_create(supplier)
   ```

2. **Validate promotion type**:
   ```python
   promo_type = PromotionType(promotion_data["type"])
   ```

3. **Guard: suppliers cannot create DEFAULT promotions** (system-only):
   ```python
   if promo_type == PromotionType.DEFAULT:
       raise ValueError("Default promotions can only be created by the system")
   ```

4. **Validate product count by type**:
   - `CAMPAIGN`: must have 2-3 products
   - `SINGLE`: must have exactly 1 product

5. **Validate product ownership** (uses helper 3):
   ```python
   product_ids = [p["product_id"] for p in products_data]
   products = await self._validate_product_ownership(supplier_id, product_ids)
   ```

6. **Build product snapshots with discounts** (uses helpers 5 + 6):
   - Loop through products, build `ProductSnapshot` for each
   - Calculate `discounted_price_cents` from `discount_percent`
   - Wrap in `PromotionProduct` with `current_status` and `current_price_cents`

7. **Build `PromotionVisibility`** from `promotion_data["visibility"]`:
   - Convert `type` to `VisibilityType` enum
   - Convert `community_ids` strings to `PydanticObjectId` list

8. **Build `PromotionSchedule`** from `promotion_data["schedule"]`:
   - `start_date`, `end_date`, `timezone` (default "UTC")

9. **Build `PromotionTerms`** (optional) from `promotion_data.get("terms")`

10. **Build `SupplierInfo`** (denormalized from supplier):
    ```python
    supplier_info = SupplierInfo(
        supplier_id=supplier.id,
        business_name=supplier.company_info.legal_name,
        logo=supplier.business_info.logo
    )
    ```

11. **Construct the Promotion document**:
    ```python
    promotion = Promotion(
        promotion_type=promo_type,
        supplier=supplier_info,
        title=promotion_data["title"],
        description=promotion_data["description"],
        banner_image=promotion_data["banner_image"],
        products=promotion_products,
        visibility=visibility,
        schedule=schedule,
        terms=terms,
        status=PromotionStatus.DRAFT,
        is_auto_generated=False
    )
    ```

12. **Insert**: `await promotion.insert()`

13. **Emit Kafka event**: `promotion.created`

14. **Return** the promotion

15. **Error handling**: Catch `ValueError` (re-raise) and generic `Exception` (wrap with context)

<details>
<summary>Hints for Exercise 2</summary>

**Hint 1 - SupplierInfo**: The denormalization reads from `supplier.company_info.legal_name` and `supplier.business_info.logo`. These are nested embedded documents on the Supplier model. Make sure you've read the Supplier model structure.

**Hint 2 - products loop**: The loop must maintain order correspondence between `products_data` (from request) and `products` (from validation). You use index `i` to pair `products[i]` with `products_data[i].get("discount_percent", 0)`.

**Hint 3 - Status**: Always starts as `DRAFT`. The supplier must explicitly call `submit_for_approval` to move it forward. This is different from Product which also starts as draft but has simpler transitions.

</details>

---

### Exercise 3: Get & List Promotions - Anti-Enumeration + Skip-Based Pagination

**MongoDB Concepts**: Ownership-scoped `find_one`, `Model.get()`, **skip-based pagination** (`skip()`, `limit()`, `.count()`), `$in` status filter

This exercise introduces **skip-based pagination** - a completely different approach from the cursor-based pagination you used in Tasks 03-05.

#### Method 1: `get_promotion` (Anti-Enumeration)
```python
async def get_promotion(self, promotion_id: str, supplier_id: str) -> Promotion:
```

**The key query:**
```python
promotion = await Promotion.find_one({
    "_id": PydanticObjectId(promotion_id),
    "supplier.supplier_id": PydanticObjectId(supplier_id)
})
```

**Why both conditions in one query?** This is the **anti-enumeration pattern** from TASK_04. If a supplier guesses another supplier's promotion_id, they get "not found" (same as if it doesn't exist at all). The query silently fails rather than returning "access denied" which would confirm the ID exists.

> **Note**: This queries a **nested field** inside the `SupplierInfo` embedded doc: `supplier.supplier_id`

#### Method 2: `get_promotion_by_id` (Admin)
```python
async def get_promotion_by_id(self, promotion_id: str) -> Promotion:
```
Simple admin-only fetch. Uses `Promotion.get(PydanticObjectId(promotion_id))`, no ownership check.

#### Method 3: `list_promotions` (SKIP-BASED PAGINATION)
```python
async def list_promotions(
    self, supplier_id: str, page: int = 1, limit: int = 20,
    status_filter: Optional[List[str]] = None, type_filter: Optional[str] = None,
    include_deleted: bool = False
) -> Dict[str, Any]:
```

**This is the big teaching moment - skip vs cursor pagination!**

In Tasks 03-05 you used **cursor-based pagination**:
```python
# Cursor pattern (what you've been doing):
query = {"_id": {"$gt": cursor_id}}  # Seek to position
items = await Model.find(query).sort("_id").limit(limit + 1).to_list()
has_more = len(items) > limit
```

Here you'll use **skip-based pagination**:
```python
# Skip pattern (this exercise):
skip = (page - 1) * limit
total = await Model.find(query).count()
items = await Model.find(query).sort("-created_at").skip(skip).limit(limit).to_list()
```

**Steps**:
1. Build query with `supplier.supplier_id` scoped to this supplier
2. Add optional filters:
   - `status_filter` -> `{"status": {"$in": status_filter}}`
   - `type_filter` -> `{"promotion_type": type_filter}`
   - `include_deleted` is False -> `{"deleted_at": None}`
3. Cap the limit: `limit = min(limit, self.max_page_size)`
4. Calculate skip: `skip = (page - 1) * limit`
5. Get total count: `await Promotion.find(query).count()`
6. Fetch items: `await Promotion.find(query).sort("-created_at").skip(skip).limit(limit).to_list()`
7. Return structured response:
   ```python
   {
       "items": promotions,
       "pagination": {
           "page": page,
           "limit": limit,
           "total": total,
           "total_pages": (total + limit - 1) // limit,  # Ceiling division!
           "has_more": skip + len(promotions) < total
       }
   }
   ```

> **Skip vs Cursor - When to Use Each**:
> | | Skip-Based | Cursor-Based |
> |---|---|---|
> | **Page numbers** | Yes ("page 3 of 7") | No (only next/prev) |
> | **Jump to page** | Yes | No |
> | **Performance** | Degrades on deep pages | Constant regardless of page |
> | **Consistency** | Can skip/duplicate items on concurrent writes | Always consistent |
> | **Use case** | Admin dashboards, management UIs | Infinite scroll, public feeds |

<details>
<summary>Hints for Exercise 3</summary>

**Hint 1 - Skip pagination math**: `total_pages = (total + limit - 1) // limit` is **ceiling division**. For 55 items with limit 20: `(55 + 19) // 20 = 3` (pages of 20, 20, 15).

**Hint 2 - has_more**: `skip + len(promotions) < total` correctly handles the last page. If you fetched 15 items starting from skip=40 and total=55, then `40 + 15 < 55` is false = no more pages.

**Hint 3 - deleted_at filter**: `{"deleted_at": None}` in MongoDB matches documents where `deleted_at` is either `null` or the field doesn't exist. This is exactly what we want for soft-deleted documents.

**Hint 4 - Index**: The query `{supplier.supplier_id, status, sort by created_at}` is covered by index #1: `[("supplier.supplier_id", 1), ("status", 1), ("created_at", -1)]`.

</details>

---

### Exercise 4: Update Promotion - Status-Based Edit Permissions

**MongoDB Concepts**: Optimistic locking (version check), conditional field updates, re-validation with cross-collection queries

#### Method: `update_promotion`
```python
async def update_promotion(
    self, promotion_id: str, supplier_id: str, version: int, updates: Dict[str, Any]
) -> Promotion:
```

**This method introduces status-based edit permissions** - different fields are editable depending on the promotion's current status.

**Algorithm**:

1. **Fetch with ownership**: `await self.get_promotion(promotion_id, supplier_id)`

2. **Version check** (optimistic locking):
   ```python
   if promotion.version != version:
       raise ValueError("Version conflict: promotion was modified by another request",
                        {"expected_version": version, "current_version": promotion.version})
   ```

3. **Auto-generated guard**: `if promotion.is_auto_generated:` -> raise

4. **Status-based edit permissions** (the key logic):
   ```python
   if promotion.status == PromotionStatus.DRAFT:
       pass  # Full edit allowed
   elif promotion.status == PromotionStatus.PAUSED:
       allowed_fields = {"title", "description", "schedule"}
       if not set(updates.keys()).issubset(allowed_fields):
           raise ValueError(...)
   else:
       raise ValueError(f"Cannot update promotion in {promotion.status.value} status")
   ```

5. **Apply simple field updates**: title, description, banner_image

6. **Products update (draft only)**: Re-validate ownership, rebuild snapshots with discounts

7. **Visibility update (draft only)**: Rebuild `PromotionVisibility`

8. **Schedule update** (both draft and paused):
   - If paused, can only **extend** end_date (not shorten):
     ```python
     if promotion.status == PromotionStatus.PAUSED:
         if new_end_date < promotion.schedule.end_date:
             raise ValueError("Can only extend end_date when paused")
     ```

9. **Terms update**: Build `PromotionTerms` or set to `None`

10. **Bump version and save**:
    ```python
    promotion.version += 1
    await promotion.save()
    ```

<details>
<summary>Hints for Exercise 4</summary>

**Hint 1 - Why status-based?** A DRAFT promotion hasn't been reviewed by anyone, so full editing is safe. A PAUSED promotion was previously approved and may have been seen by users - changing products or visibility would invalidate the approval. Only cosmetic changes (title, description) and schedule extensions are safe.

**Hint 2 - Product re-validation**: When changing products in draft, you must re-validate ownership AND rebuild snapshots (prices may have changed since creation). This reuses your helpers from Exercise 1.

**Hint 3 - Version bump**: You manually increment `promotion.version += 1` and call `await promotion.save()`. The model's `save()` override auto-updates `updated_at`. This is NOT the model helper method pattern - the service handles the version bump for updates.

</details>

---

### Exercise 5: Delete Promotion - Hard Delete + Tuple Guard

**MongoDB Concepts**: `promotion.delete()` (hard delete), tuple unpacking from model helper, version-based optimistic locking

#### Method: `delete_promotion`
```python
async def delete_promotion(self, promotion_id: str, supplier_id: str, version: int) -> None:
```

**This is the only hard delete in the entire platform.** All other services use soft delete (`deleted_at = now`). Here, if a promotion was never sent to users, it's truly removed from the database.

**Algorithm**:

1. **Fetch with ownership**: `await self.get_promotion(promotion_id, supplier_id)`

2. **Version check**: Same optimistic locking as update

3. **Check deletion rules using the model's tuple pattern**:
   ```python
   can_delete, error_code = promotion.can_delete()
   if not can_delete:
       if error_code == "AUTO_GENERATED_PROMO_PROTECTED":
           raise ValueError("Cannot delete auto-generated promotions")
       elif error_code == "STATUS_PREVENTS_DELETE":
           raise ValueError(f"Cannot delete promotion in {promotion.status.value} status",
                           {"current_status": promotion.status.value})
       elif error_code == "CANNOT_DELETE_SENT_PROMOTION":
           raise ValueError("Promotion has been sent to users and cannot be deleted. Use cancel instead.",
                           {"first_activated_at": ...})
   ```

4. **Hard delete**: `await promotion.delete()`

**Understanding `can_delete()` (defined in the model)**:
```python
def can_delete(self) -> tuple:
    if self.is_auto_generated:     return False, "AUTO_GENERATED_PROMO_PROTECTED"
    if status in [ACTIVE, PENDING]: return False, "STATUS_PREVENTS_DELETE"
    if self.is_sent:               return False, "CANNOT_DELETE_SENT_PROMOTION"
    return True, None
```

The `is_sent` property checks `self.first_activated_at is not None`. Once a promotion has been active (seen by users), it can never be hard deleted - the supplier must use "cancel" (soft delete) instead for audit trail.

> **Hard delete vs Soft delete decision tree**:
> ```
> Was it ever active (is_sent)?
>   YES -> Can NEVER hard delete. Use cancel_promotion() (soft delete)
>   NO  -> Is status ACTIVE or PENDING_APPROVAL?
>            YES -> Can't delete right now (status prevents it)
>            NO  -> Is it auto-generated?
>                     YES -> Protected, can't delete
>                     NO  -> HARD DELETE (promotion.delete())
> ```

<details>
<summary>Hints for Exercise 5</summary>

**Hint 1 - Tuple unpacking**: Python's `can_delete, error_code = promotion.can_delete()` destructures the returned tuple. The `error_code` is `None` when deletion is allowed.

**Hint 2 - Hard delete in Beanie**: `await promotion.delete()` permanently removes the document from MongoDB. This calls `db.promotions.deleteOne({_id: promotion.id})` under the hood. There is no undo.

**Hint 3 - No Kafka event**: Notice there's no Kafka event emitted for delete. This is intentional - only lifecycle transitions emit events. Hard deletion of unsent drafts is silent.

</details>

---

### Exercise 6: Submit for Approval - The Validation Chain

**MongoDB Concepts**: Version-based locking, required field validation, `$in` on nested field (re-check via helper), model method delegation

#### Method: `submit_for_approval`
```python
async def submit_for_approval(self, promotion_id: str, supplier_id: str, version: int) -> Promotion:
```

**This transitions DRAFT -> PENDING_APPROVAL and initializes the approval records.**

**Algorithm**:

1. **Fetch with ownership**: `await self.get_promotion(promotion_id, supplier_id)`
2. **Version check**
3. **Validate required fields are complete**:
   - `promotion.title` and `promotion.description` must be non-empty
   - `promotion.products` must be non-empty
   - `promotion.banner_image` must be non-empty
4. **Re-check product conflicts** (products may have gained active promotions since creation):
   ```python
   product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
   await self._check_product_active_promotion(product_ids, promotion_id)
   ```
5. **Delegate to model method**: `await promotion.submit_for_approval()`
   - This initializes `ApprovalRecord` entries based on visibility type
   - Sets status to `PENDING_APPROVAL`
   - Bumps version and saves
6. **Emit Kafka event**: `promotion.submitted`
7. **Return** the promotion

> **Why re-check products?** Between creation (DRAFT) and submission, another supplier may have created and activated a promotion for the same product. The `$in` query on `products.product_snapshot.product_id` with `$ne` exclusion catches this.

<details>
<summary>Hints for Exercise 6</summary>

**Hint 1 - Model method**: `promotion.submit_for_approval()` is an async method on the Promotion model that handles the state transition. The service validates business rules, the model handles state. Read the model code to see how it initializes approval records based on visibility type.

**Hint 2 - product_ids extraction**: You extract `product_id` from the existing `product_snapshot` (not from request data). By this point the products are already stored as snapshots in the promotion.

</details>

---

### Exercise 7: Approve & Reject - Multi-Scope Approval Workflow

**MongoDB Concepts**: Admin get (no ownership scope), version locking, model method delegation, `$in` re-check on approve

These two methods are called by admins/leaders, NOT by the supplier. They use `get_promotion_by_id` (no ownership check).

#### Method 1: `approve_promotion`
```python
async def approve_promotion(
    self, promotion_id: str, reviewer_id: str, reviewer_type: str,
    scope: str, version: int, community_id: Optional[str] = None,
    notes: Optional[str] = None
) -> Promotion:
```

**Algorithm**:
1. **Admin fetch**: `await self.get_promotion_by_id(promotion_id)` (no supplier_id check!)
2. **Version check**
3. **Re-check product conflicts**: Products may have gained active promotions while pending
4. **Delegate to model**: `await promotion.approve(scope=scope, reviewer_id=..., ...)`
5. **Emit Kafka event**: `promotion.approved` with scope info
6. **Return** the promotion

**What the model's `approve()` does** (important to understand):
- If `scope == "global"`: sets `approval.global_approval = ApprovalRecord(APPROVED, ...)`
- If `scope == "community"`: sets `approval.community_approvals[community_id] = ApprovalRecord(APPROVED, ...)`
- Then checks `is_fully_approved(visibility)`:
  - If ALL required scopes are approved AND `now >= start_date` -> status = `ACTIVE` (+ set `first_activated_at`)
  - If ALL approved AND `now < start_date` -> status = `SCHEDULED`
  - If some still pending -> stays `PENDING_APPROVAL`

#### Method 2: `reject_promotion`
```python
async def reject_promotion(
    self, promotion_id: str, reviewer_id: str, reviewer_type: str,
    scope: str, reason: str, version: int, community_id: Optional[str] = None
) -> Promotion:
```

**Algorithm**:
1. **Admin fetch**: `await self.get_promotion_by_id(promotion_id)`
2. **Version check**
3. **Delegate to model**: `await promotion.reject(scope=scope, ..., reason=reason, ...)`
4. **Emit Kafka event**: `promotion.rejected` with scope and reason
5. **Return** the promotion

**What the model's `reject()` does**:
- Records a `RejectionRecord` in `rejection_history[]`
- Updates the specific approval record status to `REJECTED`
- **Returns status to DRAFT** - the supplier can fix and resubmit

<details>
<summary>Hints for Exercise 7</summary>

**Hint 1 - Admin vs supplier**: Notice `approve_promotion` uses `get_promotion_by_id` (admin, no ownership) while lifecycle methods like `pause_promotion` use `get_promotion` (supplier, with ownership). Admins can approve any promotion; suppliers can only manage their own.

**Hint 2 - Re-check on approve**: The `_check_product_active_promotion` re-check on approve is a safety net. While a promotion was pending approval, another promotion for the same product could have been approved and activated. This prevents two active promotions for the same product.

**Hint 3 - reject returns to DRAFT**: This is a deliberate design choice. The supplier doesn't need to create a new promotion - they edit the rejected one and resubmit. The `rejection_history` provides an audit trail.

</details>

---

### Exercise 8: Lifecycle Operations - Pause, Resume, Cancel, End

**MongoDB Concepts**: Status guards (model methods), version-based locking, active promotion re-check on resume, auto-generated guard

All 4 methods follow the same pattern: fetch with ownership -> version check -> guard -> delegate to model -> emit event -> return.

#### Method 1: `pause_promotion`
```python
async def pause_promotion(self, promotion_id: str, supplier_id: str, version: int, reason: str) -> Promotion:
```
- Fetch with ownership, version check
- Delegate: `await promotion.pause_promotion(reason)`
- Model validates: only ACTIVE can be paused
- Emit: `promotion.paused`

#### Method 2: `resume_promotion`
```python
async def resume_promotion(self, promotion_id: str, supplier_id: str, version: int) -> Promotion:
```
- Fetch with ownership, version check
- **Re-check product conflicts**: While paused, another promotion may have gone active for the same products
  ```python
  product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
  await self._check_product_active_promotion(product_ids, promotion_id)
  ```
- Delegate: `await promotion.resume_promotion()`
- Model validates: only PAUSED can be resumed, also checks if end_date has passed
- Emit: `promotion.resumed`

#### Method 3: `cancel_promotion`
```python
async def cancel_promotion(self, promotion_id: str, supplier_id: str, version: int, reason: str) -> Promotion:
```
- Fetch with ownership, version check
- **Auto-generated guard**: `if promotion.is_auto_generated:` -> raise
- Delegate: `await promotion.cancel_promotion(reason)`
- Model validates: cannot cancel ENDED, sets `deleted_at`, status = CANCELLED
- Emit: `promotion.cancelled`

#### Method 4: `end_promotion`
```python
async def end_promotion(self, promotion_id: str, supplier_id: str, version: int) -> Promotion:
```
- Fetch with ownership, version check
- **Manual status check**: `if promotion.status != PromotionStatus.ACTIVE:` raise ValueError("Only active promotions can be ended")
- Delegate: `await promotion.end_promotion()`
- Emit: `promotion.ended`

<details>
<summary>Hints for Exercise 8</summary>

**Hint 1 - resume_promotion re-check**: This is the third place we call `_check_product_active_promotion`. The pattern is: check at submit, check at approve, check at resume. Any time a promotion might become ACTIVE, we verify no conflicts exist.

**Hint 2 - cancel vs end**: Cancel is for stopping a promotion you don't want anymore (soft deletes it). End is for gracefully finishing an active promotion (e.g., ending a sale early). Cancel sets `deleted_at` and `cancellation_reason`; end just changes status to ENDED.

**Hint 3 - end_promotion status check**: Unlike other lifecycle methods where the model validates the source status, `end_promotion` has the service do the status check. The model's `end_promotion()` just sets status = ENDED without validating. This is a design inconsistency in the codebase - but match it exactly!

</details>

---

### Exercise 9: Feed Queries & Admin - Dynamic Keys + Date Ranges

**MongoDB Concepts**: Multi-condition compound queries, `$lte`/`$gte` date ranges, `$in` on enum values, **dynamic key queries** (computed field paths!), nested approval field queries, cursor-based pagination, skip-based admin pagination

This is the **grand finale** - the most complex queries in the entire course.

#### Method 1: `get_global_feed_promotions` (6-CONDITION QUERY)
```python
async def get_global_feed_promotions(self, limit: int = 20, cursor: Optional[str] = None) -> Dict[str, Any]:
```

**The query:**
```python
now = utc_now()

query = {
    "status": PromotionStatus.ACTIVE,
    "deleted_at": None,
    "visibility.type": {"$in": [VisibilityType.GLOBAL.value, VisibilityType.BOTH.value]},
    "schedule.start_date": {"$lte": now},
    "schedule.end_date": {"$gte": now},
    "approval.global_approval.status": ApprovalStatus.APPROVED.value
}
```

**Breaking down each condition**:
1. `status: ACTIVE` - Only active promotions
2. `deleted_at: None` - Not soft-deleted
3. `visibility.type: $in [GLOBAL, BOTH]` - Visible on global feed (includes "both" type)
4. `schedule.start_date: $lte now` - Has already started
5. `schedule.end_date: $gte now` - Hasn't ended yet
6. `approval.global_approval.status: APPROVED` - Global approval is complete

**Conditions 4+5 create a date range**: The promotion's schedule must **bracket** the current time. This is a common MongoDB pattern for "currently active" queries.

**Cursor pagination** (simpler than TASK_05):
```python
if cursor:
    query["_id"] = {"$gt": PydanticObjectId(cursor)}

limit = min(limit, 50)
promotions = await Promotion.find(query).sort("-stats.impressions").limit(limit + 1).to_list()

has_more = len(promotions) > limit
if has_more:
    promotions = promotions[:-1]

next_cursor = str(promotions[-1].id) if has_more and promotions else None
```

Return: `{"items": promotions, "cursor": next_cursor, "has_more": has_more}`

#### Method 2: `get_community_feed_promotions` (THE DYNAMIC KEY QUERY)
```python
async def get_community_feed_promotions(self, community_id: str, limit: int = 20, cursor: Optional[str] = None) -> Dict[str, Any]:
```

**Identical to global feed EXCEPT**:

1. Visibility filter changes: `{"$in": [COMMUNITIES.value, BOTH.value]}` (not GLOBAL)
2. **Additional community match**: `"visibility.community_ids": PydanticObjectId(community_id)`
3. **THE DYNAMIC KEY** - the field path contains a variable:
   ```python
   f"approval.community_approvals.{community_id}.status": ApprovalStatus.APPROVED.value
   ```

**Why is the dynamic key special?**

`approval.community_approvals` is a `Dict[str, ApprovalRecord]`. The keys are community ID strings. To check if THIS community's approval is approved, you build the field path dynamically:

```
If community_id = "507f1f77bcf86cd799439011"
Then field path = "approval.community_approvals.507f1f77bcf86cd799439011.status"
```

MongoDB traverses: `approval` (embedded doc) -> `community_approvals` (dict/map) -> `{community_id}` (dict key) -> `status` (field on ApprovalRecord)

> **This is one of MongoDB's most powerful features**: dot notation works through nested dicts/maps using the actual key as a path segment. No special operators needed!

#### Method 3: `list_pending_approvals` (Admin, Skip-Based)
```python
async def list_pending_approvals(
    self, page: int = 1, limit: int = 20,
    visibility_filter: Optional[str] = None,
    community_id_filter: Optional[str] = None
) -> Dict[str, Any]:
```

**Another skip-based pagination** (like `list_promotions`):

1. Base query: `{"status": PromotionStatus.PENDING_APPROVAL}`
2. Optional filters:
   - `visibility_filter` -> `{"visibility.type": visibility_filter}`
   - `community_id_filter` -> `{"visibility.community_ids": PydanticObjectId(community_id_filter)}`
3. Pagination: same skip/limit/count pattern as Exercise 3
4. Sort: `"created_at"` ascending (oldest pending first - FIFO queue)

> **Note the sort direction**: `list_promotions` sorts by `-created_at` (newest first for management). `list_pending_approvals` sorts by `created_at` (oldest first for approval queue). This is intentional - pending items should be reviewed in order.

<details>
<summary>Hints for Exercise 9</summary>

**Hint 1 - Date range**: `$lte` and `$gte` create a "between" condition. `start_date <= now` means "has started", `end_date >= now` means "hasn't ended". Together: "is currently within its scheduled window".

**Hint 2 - VisibilityType.GLOBAL.value**: Note the `.value` - you're comparing against the string enum value, not the enum object. MongoDB stores the string value, so the query must use strings too.

**Hint 3 - Dynamic key indexing**: MongoDB CANNOT efficiently index dynamic key paths in Dict fields. The `community_approvals.{community_id}.status` path doesn't benefit from any index. The other conditions (status, visibility, schedule) narrow the result set first using index #12, then MongoDB scans the remaining docs for the approval status. This is an acceptable trade-off for the flexibility of Dict-based approvals.

**Hint 4 - Feed pagination**: The feeds use simple `_id`-based cursor pagination (not the complex `published_at` + `_id` tiebreaker from TASK_05). The sort is by `stats.impressions` descending (most popular first), but the cursor uses `_id` for consistency. This means the ordering may shift between pages as impressions change - acceptable for a feed.

</details>

---

## 6. VERIFICATION CHECKLIST

After implementing all methods, verify each exercise works:

### Exercise 1: Helpers
```bash
# Test _get_supplier with valid supplier_id
# Test _get_supplier with invalid id -> ValueError
# Test _check_supplier_can_create with inactive supplier -> ValueError
# Test _validate_product_ownership with another supplier's product -> ValueError
# Test _check_product_active_promotion with no conflicts -> passes
```

### Exercise 2: Create Promotion
```bash
POST /promotions
{
  "type": "single",
  "title": "Summer Sale on Widget",
  "description": "Amazing summer discount on our best widget!",
  "banner_image": "https://example.com/banner.jpg",
  "products": [{"product_id": "<your_product_id>", "discount_percent": 20}],
  "visibility": {"type": "global"},
  "schedule": {"start_date": "2025-07-01T00:00:00Z", "end_date": "2025-07-31T23:59:59Z"},
  "terms": {"terms_text": "While supplies last. No rain checks."}
}
# Expect: 201, status="draft", discount calculated, supplier info denormalized
```

### Exercise 3: Get & List
```bash
# Get single promotion
POST /promotions/get  {"promotion_id": "<id>"}
# Expect: Full promotion response

# List with filters
GET /promotions/list?page=1&limit=10&status=draft
# Expect: Skip-based pagination with total, total_pages, has_more

# Try another supplier's promotion_id -> 404 (anti-enumeration)
```

### Exercise 4: Update
```bash
POST /promotions/update
{
  "promotion_id": "<id>",
  "version": 1,
  "title": "Updated Summer Sale!"
}
# Expect: version=2, title changed
# Try updating in wrong status -> error
```

### Exercise 5: Delete
```bash
POST /promotions/delete  {"promotion_id": "<id>", "version": 2}
# Expect: 204 No Content (hard deleted!)
# Verify: GET the same ID -> 404
```

### Exercise 6: Submit
```bash
# Create a fresh promotion, then:
POST /promotions/submit  {"promotion_id": "<id>", "version": 1}
# Expect: status="pending_approval", approval records initialized
```

### Exercise 7: Approve & Reject
```bash
# As admin, approve the pending promotion (scope=global):
# Expect: If fully approved + start_date <= now -> status="active"
#         If fully approved + start_date > now -> status="scheduled"
#         If partially approved -> stays "pending_approval"

# Test reject -> status returns to "draft", rejection_history has entry
```

### Exercise 8: Lifecycle
```bash
# Pause an active promotion -> status="paused"
# Resume a paused promotion -> status="active"
# Cancel any non-ended promotion -> status="cancelled", deleted_at set
# End an active promotion -> status="ended"
```

### Exercise 9: Feed Queries
```bash
# Global feed (need an active, approved, currently-scheduled promotion):
POST /promotions/global  {"cursor": null}
# Expect: Active promotions sorted by impressions

# Community feed:
POST /promotions/community  {"community_id": "<id>", "cursor": null}
# Expect: Promotions approved for this community

# Admin pending approvals:
GET /admin/promotions/pending?page=1&limit=10
# Expect: Skip-based pagination of pending promotions
```

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Skip Pagination's O(n) Problem

Run this thought experiment:

You have 100,000 promotions for a supplier. The admin requests page 5000 (`page=5000, limit=20`).

```python
skip = (5000 - 1) * 20  # = 99,980
# MongoDB must scan and skip 99,980 documents before returning 20
```

**Questions**:
1. What is the time complexity of this operation? Why does skip degrade on deep pages?
2. The feeds use cursor pagination instead. Could `list_promotions` also use cursors? What would you lose?
3. Design a **hybrid approach**: cursor-based for the query engine but still expose page numbers to the UI. (Hint: think about caching cursor positions.)

### Challenge 2: The Dynamic Key Index Problem

The community feed query includes:
```python
f"approval.community_approvals.{community_id}.status": ApprovalStatus.APPROVED.value
```

MongoDB cannot create a traditional index on dynamic keys in a Dict field.

**Questions**:
1. If you had 50,000 promotions, what would the query performance look like? Which conditions filter first?
2. Could you restructure `community_approvals` from a Dict to a List to make it indexable? What would the trade-offs be?
3. The current design uses Dict for O(1) lookup by community_id. A List would require `$elemMatch`. Which is better for writes vs reads?

### Challenge 3: The Active Promotion Race Condition

`_check_product_active_promotion` is called in 3 places: submit, approve, and resume. But between the check and the subsequent state transition, another promotion could be approved.

```
Timeline:
  T1: Promotion A checks no conflict for Product X    -> OK
  T2: Promotion B checks no conflict for Product X    -> OK (A not yet active)
  T3: Promotion A is approved -> ACTIVE for Product X
  T4: Promotion B is approved -> ACTIVE for Product X  (CONFLICT! Two active!)
```

**Questions**:
1. This is a classic **TOCTOU** (Time Of Check, Time Of Use) race. How would you solve it with a MongoDB **unique partial index**?
2. Write the index definition that would enforce "at most one ACTIVE promotion per product_id".
3. What happens to the `approve()` call at T4 if this index exists? How should the service handle the `DuplicateKeyError`?

---

## 8. WHAT'S NEXT?

Congratulations! You've now implemented the most operationally complex service in the platform.

**What you've mastered in this task**:
- Skip-based AND cursor-based pagination (and when to use each)
- Date range queries with `$lte`/`$gte`
- Dynamic key queries on Dict/Map fields
- Multi-condition compound queries (6+ conditions)
- Cross-collection validation against 2 other collections
- 7-status lifecycle with multi-scope approval
- Hard delete vs soft delete decision logic
- Status-based edit permissions
- The `$in` operator on deeply nested fields

**Your next task**: `TASK_07_ORDER.md` - Order Processing Service. You'll build the final transactional service that ties everything together: creating orders from promotions, managing order lifecycle, payment integration patterns, and your first **MongoDB transactions** (multi-document atomicity).
