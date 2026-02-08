# TASK 08: Analytics Service - Aggregation Pipelines (Capstone)

## 1. MISSION BRIEFING

You've spent 7 tasks writing `find()`, `find_one()`, `insert()`, and `save()` queries. Now you enter a completely different world: **MongoDB Aggregation Pipelines**. Aggregation pipelines are multi-stage data processing workflows that transform, filter, group, join, and reshape documents - all executed server-side inside MongoDB. They're the equivalent of SQL's `GROUP BY`, `JOIN`, `HAVING`, window functions, and subqueries - but expressed as a pipeline of stages where each stage's output feeds into the next.

This is the **capstone task**. There are no routes or schemas to follow - you'll create a standalone `AnalyticsService` class from scratch and write 8 aggregation pipelines that answer real business questions by querying across ALL the data you've built in Tasks 01-07.

### What You Will Build
A new `AnalyticsService` class with 8 methods, each implementing a different aggregation pipeline pattern. These methods generate platform analytics: revenue breakdowns, top-performing entities, time-series trends, distribution analyses, and a full admin dashboard.

### What You Will Learn

| Aggregation Stage | Exercise | What It Does |
|------------------|----------|--------------|
| **`$match`** | All exercises | Filter documents before processing (always first!) |
| **`$group`** | Ex 1, 2, 6 | Group documents and compute aggregates (`$sum`, `$avg`, `$max`, `$first`) |
| **`$unwind`** | Ex 2, 3 | Flatten arrays into individual documents |
| **`$lookup`** | Ex 3 | Left outer join across collections |
| **`$project` + `$addFields`** | Ex 4 | Reshape output, compute new fields |
| **`$bucket`** | Ex 5 | Range-based grouping (histograms) |
| **`$dateToString`** | Ex 6 | Date formatting for time-series grouping |
| **`$sortByCount`** | Ex 7 | Frequency analysis (shorthand for `$group` + `$sort`) |
| **`$facet`** | Ex 8 | Multiple independent pipelines in a single query |

### How This Differs From All Previous Tasks

| Aspect | Tasks 01-07 | Task 08 (Analytics) |
|--------|-------------|---------------------|
| Query type | `find()`, `find_one()` | **Aggregation pipelines** |
| Data flow | Filter -> Return | **Multi-stage: filter -> transform -> group -> reshape** |
| Joins | Manual cross-collection reads | **`$lookup` server-side joins** |
| Output shape | Full documents | **Custom computed results** |
| Service file | Implement existing stub | **Create from scratch** |
| Routes | Pre-built | **None - run from tests/shell** |
| Collections | 1-4 per method | **All 8 collections available** |

---

## 2. BEFORE YOU START

### Prerequisites
- **ALL previous tasks (01-07) should be complete** with test data in the database
- The more data you have, the more interesting the analytics will be
- Recommended minimum: 3 users, 2 suppliers, 3 communities, 5 products, 10 posts, 3 promotions, 5 orders

### The Collections You'll Query

| Collection | Key Fields for Analytics |
|-----------|------------------------|
| `users` | `role`, `status`, `created_at`, `community_ids[]`, `contact_info.country` |
| `suppliers` | `status`, `verification.verification_status`, `created_at`, `product_ids[]` |
| `communities` | `status`, `category`, `tags[]`, `member_count`, `created_at`, `country` |
| `products` | `status`, `base_price_cents`, `category`, `tags[]`, `supplier_id`, `created_at` |
| `posts` | `status`, `post_type`, `community_id`, `author.user_id`, `stats.*`, `published_at` |
| `promotions` | `status`, `promotion_type`, `products[]`, `stats.*`, `visibility.*`, `created_at` |
| `orders` | `status`, `totals.*`, `items[]`, `customer.user_id`, `attribution.*`, `created_at` |
| `post_change_requests` | `status`, `post_id`, `requested_by`, `created_at` |

### Beanie Aggregation Syntax

In Beanie, you call `.aggregate()` on a Document class:

```python
# Basic aggregation
results = await Order.aggregate([
    {"$match": {"status": "confirmed"}},
    {"$group": {"_id": "$customer.user_id", "total": {"$sum": "$totals.total_cents"}}}
]).to_list()

# With raw motor collection (for $lookup across collections)
collection = Order.get_motor_collection()
results = await collection.aggregate([
    {"$match": {...}},
    {"$lookup": {...}},
    ...
]).to_list(length=None)
```

> **Important**: `Model.aggregate()` returns Beanie cursor that needs `.to_list()`. Raw motor aggregation needs `.to_list(length=None)` where `length=None` means "get all results".

### Create Your Service File

Create a new file: `apps/backend-service/src/services/analytics.py`

```python
"""
Analytics Service - Aggregation pipeline exercises
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from beanie import PydanticObjectId

from shared.models.order import Order
from shared.models.product import Product
from shared.models.user import User
from shared.models.community import Community
from shared.models.post import Post
from shared.models.promotion import Promotion
from shared.models.supplier import Supplier
from src.utils.datetime_utils import utc_now


class AnalyticsService:
    """
    Analytics service using MongoDB aggregation pipelines.

    Each method implements a different aggregation pattern
    that answers a real business question.
    """

    # Exercise 1-8 methods go here
    pass
```

---

## 3. AGGREGATION PIPELINE PRIMER

Before diving into exercises, understand the pipeline concept:

```
Documents in collection
    |
    v
┌──────────────┐
│  $match      │  Filter documents (like WHERE)
│  { status:   │  ALWAYS put this first for performance
│    "active"} │
└──────┬───────┘
       |
       v
┌──────────────┐
│  $unwind     │  Flatten array field into individual docs
│  "$items"    │  1 doc with 3 items -> 3 docs (one per item)
└──────┬───────┘
       |
       v
┌──────────────┐
│  $group      │  Group by key, compute aggregates
│  { _id:      │  Like GROUP BY + SUM/AVG/COUNT
│    "$field"} │
└──────┬───────┘
       |
       v
┌──────────────┐
│  $sort       │  Sort the results
│  { total: -1}│
└──────┬───────┘
       |
       v
┌──────────────┐
│  $project    │  Reshape output (include/exclude/compute fields)
│  { name: 1,  │  Like SELECT in SQL
│    total: 1} │
└──────┬───────┘
       |
       v
  Final Results
```

### The Golden Rule: `$match` First

```python
# GOOD: Filter 1M docs down to 1K, then group 1K
[
    {"$match": {"status": "confirmed"}},      # 1K docs pass through
    {"$group": {"_id": "$supplier_id", ...}}   # Group 1K docs
]

# BAD: Group 1M docs, then filter results
[
    {"$group": {"_id": "$supplier_id", ...}},  # Group ALL 1M docs
    {"$match": {"total": {"$gt": 1000}}}       # Filter results after
]
```

---

## 4. SERVICE CONTRACT

```python
class AnalyticsService:
    # Exercise 1: $match + $group
    async def revenue_by_supplier(self, start_date=None, end_date=None) -> List[Dict]

    # Exercise 2: $unwind + $group
    async def top_products_by_order_count(self, limit: int = 10) -> List[Dict]

    # Exercise 3: $lookup (cross-collection join)
    async def orders_with_product_details(self, supplier_id: str, limit: int = 20) -> List[Dict]

    # Exercise 4: $project + $addFields (computed fields)
    async def promotion_performance_report(self) -> List[Dict]

    # Exercise 5: $bucket (distribution analysis)
    async def product_price_distribution(self, currency: str = "USD") -> List[Dict]

    # Exercise 6: $dateToString (time-series)
    async def daily_revenue(self, days: int = 30) -> List[Dict]

    # Exercise 7: $sortByCount (frequency analysis)
    async def top_community_categories(self, limit: int = 10) -> List[Dict]

    # Exercise 8: $facet (admin dashboard)
    async def platform_dashboard(self) -> Dict[str, Any]
```

---

## 5. EXERCISES

---

### Exercise 1: Revenue by Supplier - `$match` + `$group`

**Aggregation Concepts**: `$match`, `$group`, `$sum`, `$avg`, `$first`, `$sort`

**Business Question**: "How much revenue has each supplier generated from confirmed orders?"

#### Method: `revenue_by_supplier`
```python
async def revenue_by_supplier(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
```

**The Pipeline:**

```python
pipeline = []

# Stage 1: $match - Filter to confirmed/delivered orders
match_filter = {
    "status": {"$in": ["confirmed", "processing", "shipped", "delivered"]}
}
if start_date:
    match_filter["created_at"] = {"$gte": start_date}
if end_date:
    match_filter.setdefault("created_at", {})["$lte"] = end_date

pipeline.append({"$match": match_filter})

# Stage 2: $unwind - Flatten items array
# Each order has multiple items, possibly from different suppliers
pipeline.append({"$unwind": "$items"})

# Stage 3: $group - Group by supplier_id, sum revenue
pipeline.append({"$group": {
    "_id": "$items.product_snapshot.supplier_id",
    "total_revenue_cents": {"$sum": "$items.final_price_cents"},
    "total_items_sold": {"$sum": "$items.quantity"},
    "order_count": {"$sum": 1},
    "avg_item_value_cents": {"$avg": "$items.final_price_cents"},
    "supplier_name": {"$first": "$items.product_snapshot.supplier_name"}
}})

# Stage 4: $sort - Highest revenue first
pipeline.append({"$sort": {"total_revenue_cents": -1}})

# Stage 5: $project - Clean up output
pipeline.append({"$project": {
    "_id": 0,
    "supplier_id": {"$toString": "$_id"},
    "supplier_name": 1,
    "total_revenue_cents": 1,
    "total_revenue_dollars": {"$divide": ["$total_revenue_cents", 100]},
    "total_items_sold": 1,
    "order_count": 1,
    "avg_item_value_cents": {"$round": ["$avg_item_value_cents", 0]}
}})

results = await Order.aggregate(pipeline).to_list()
return results
```

**Breaking down the key stages:**

**`$unwind "$items"`**: An order with 3 items becomes 3 documents, each with one item. This is necessary because each item may have a different `supplier_id` in its `product_snapshot`. Without unwind, you can't group by supplier at the item level.

**`$group` accumulators:**
- `$sum: "$items.final_price_cents"` - Adds up all revenue
- `$sum: "$items.quantity"` - Counts total units sold
- `$sum: 1` - Counts the number of order-item pairs (like COUNT(*))
- `$avg: "$items.final_price_cents"` - Average item value
- `$first: "$items.product_snapshot.supplier_name"` - Takes the supplier name from the first matching doc (they're all the same for one supplier)

**`$project` with `$divide` and `$round`**: These are **aggregation expressions** that compute new fields. `$divide: ["$total_revenue_cents", 100]` converts cents to dollars. `$round: ["$avg_item_value_cents", 0]` rounds to integer.

<details>
<summary>Hints</summary>

**Hint 1 - Date range**: Build the `$match` filter conditionally. If both dates are provided, `created_at` should have both `$gte` and `$lte`. If only one, just that condition.

**Hint 2 - $toString**: The `_id` from `$group` is an ObjectId. `$toString` converts it to a string for clean output. This is a `$project`-stage expression.

**Hint 3 - Index**: The `$match` stage can use the `[("status", 1), ("created_at", -1)]` index (order index #4). The `$unwind` and `$group` stages work in memory after the match filters the data.

</details>

**Expected Output:**
```json
[
  {
    "supplier_id": "507f1f77bcf86cd799439011",
    "supplier_name": "Artisan Crafts Co",
    "total_revenue_cents": 245000,
    "total_revenue_dollars": 2450.00,
    "total_items_sold": 23,
    "order_count": 15,
    "avg_item_value_cents": 10652
  },
  ...
]
```

---

### Exercise 2: Top Products by Order Count - `$unwind` + `$group`

**Aggregation Concepts**: `$unwind`, `$group`, `$sort`, `$limit`, nested field accumulation

**Business Question**: "Which products are ordered most frequently?"

#### Method: `top_products_by_order_count`
```python
async def top_products_by_order_count(self, limit: int = 10) -> List[Dict]:
```

**The Pipeline:**

```python
pipeline = [
    # Stage 1: Only confirmed+ orders
    {"$match": {
        "status": {"$in": ["confirmed", "processing", "shipped", "delivered"]}
    }},

    # Stage 2: Flatten items
    {"$unwind": "$items"},

    # Stage 3: Group by product_id
    {"$group": {
        "_id": "$items.product_snapshot.product_id",
        "product_name": {"$first": "$items.product_snapshot.product_name"},
        "supplier_name": {"$first": "$items.product_snapshot.supplier_name"},
        "sku": {"$first": "$items.product_snapshot.sku"},
        "times_ordered": {"$sum": 1},
        "total_quantity": {"$sum": "$items.quantity"},
        "total_revenue_cents": {"$sum": "$items.final_price_cents"},
        "avg_quantity_per_order": {"$avg": "$items.quantity"}
    }},

    # Stage 4: Sort by times ordered
    {"$sort": {"times_ordered": -1}},

    # Stage 5: Limit
    {"$limit": limit},

    # Stage 6: Clean output
    {"$project": {
        "_id": 0,
        "product_id": {"$toString": "$_id"},
        "product_name": 1,
        "supplier_name": 1,
        "sku": 1,
        "times_ordered": 1,
        "total_quantity": 1,
        "total_revenue_cents": 1,
        "avg_quantity_per_order": {"$round": ["$avg_quantity_per_order", 1]}
    }}
]

return await Order.aggregate(pipeline).to_list()
```

**Key teaching point - `$unwind` before `$group`:**

```
Order 1: {items: [Widget(qty:2), Gadget(qty:1)]}
Order 2: {items: [Widget(qty:3)]}

After $unwind:
  {item: Widget, qty:2, order:1}
  {item: Gadget, qty:1, order:1}
  {item: Widget, qty:3, order:2}

After $group by product_id:
  Widget: {times_ordered: 2, total_quantity: 5}
  Gadget: {times_ordered: 1, total_quantity: 1}
```

Without `$unwind`, you couldn't count individual products across orders because each order contains an array of items.

<details>
<summary>Hints</summary>

**Hint 1 - `$limit` placement**: Always put `$limit` AFTER `$sort`. If you limit before sorting, you get an arbitrary subset.

**Hint 2 - `times_ordered` vs `total_quantity`**: `$sum: 1` counts how many orders include this product. `$sum: "$items.quantity"` sums up the actual quantities. A product ordered 3 times with quantities 2, 1, 5 has `times_ordered=3` and `total_quantity=8`.

</details>

---

### Exercise 3: Orders with Product Details - `$lookup` (Cross-Collection Join)

**Aggregation Concepts**: `$lookup`, `$unwind` (for flattening join results), pipeline inside `$lookup`

**Business Question**: "For a given supplier, show their orders enriched with current product information."

#### Method: `orders_with_product_details`
```python
async def orders_with_product_details(
    self, supplier_id: str, limit: int = 20
) -> List[Dict]:
```

**The Pipeline (using raw motor for cross-collection `$lookup`):**

```python
collection = Order.get_motor_collection()

pipeline = [
    # Stage 1: Filter to orders containing this supplier's products
    {"$match": {
        "items.product_snapshot.supplier_id": PydanticObjectId(supplier_id),
        "status": {"$in": ["confirmed", "processing", "shipped", "delivered"]}
    }},

    # Stage 2: Sort newest first
    {"$sort": {"created_at": -1}},

    # Stage 3: Limit
    {"$limit": limit},

    # Stage 4: Unwind items to join per-item
    {"$unwind": "$items"},

    # Stage 5: Filter to only this supplier's items
    {"$match": {
        "items.product_snapshot.supplier_id": PydanticObjectId(supplier_id)
    }},

    # Stage 6: $lookup - Join with products collection
    {"$lookup": {
        "from": "products",
        "localField": "items.product_snapshot.product_id",
        "foreignField": "_id",
        "as": "current_product"
    }},

    # Stage 7: Unwind the lookup result (0 or 1 match)
    {"$unwind": {
        "path": "$current_product",
        "preserveNullAndEmptyArrays": True
    }},

    # Stage 8: Project final shape
    {"$project": {
        "_id": 0,
        "order_id": {"$toString": "$_id"},
        "order_number": 1,
        "order_status": "$status",
        "order_date": "$created_at",
        "customer_name": "$customer.display_name",

        # Snapshot data (at purchase time)
        "snapshot_product_name": "$items.product_snapshot.product_name",
        "snapshot_price_cents": "$items.unit_price_cents",
        "quantity": "$items.quantity",
        "final_price_cents": "$items.final_price_cents",
        "fulfillment_status": "$items.fulfillment_status",

        # Current product data (from $lookup)
        "current_product_name": "$current_product.name",
        "current_price_cents": "$current_product.base_price_cents",
        "current_status": "$current_product.status",
        "product_still_exists": {"$cond": {
            "if": {"$ifNull": ["$current_product", false]},
            "then": true,
            "else": false
        }},

        # Price drift
        "price_changed": {"$ne": [
            "$items.unit_price_cents",
            "$current_product.base_price_cents"
        ]}
    }}
]

results = await collection.aggregate(pipeline).to_list(length=None)
return results
```

**Understanding `$lookup`:**

```
$lookup is a LEFT OUTER JOIN:

orders collection          products collection
┌─────────────┐           ┌──────────────┐
│ order_item   │           │ product      │
│ product_id ──┼───JOIN───>│ _id          │
│              │           │ name         │
│              │           │ price        │
└─────────────┘           └──────────────┘

Result: each order item gets a "current_product" array
        (empty if product was deleted)
```

**Key options:**
- `from`: The collection to join with (string name, not the model)
- `localField`: The field in the current document to match
- `foreignField`: The field in the `from` collection to match against
- `as`: The output array field name

**`preserveNullAndEmptyArrays: True`**: Without this, orders for deleted products would be dropped from the results. With it, `current_product` is `null` for deleted products - which is exactly what we want (we can show "Product no longer available").

<details>
<summary>Hints</summary>

**Hint 1 - Raw motor**: Use `Order.get_motor_collection()` for cross-collection lookups. Beanie's `.aggregate()` works too but motor gives you more control.

**Hint 2 - Double $match**: The first `$match` filters orders (uses index). After `$unwind`, the second `$match` filters items within those orders to only this supplier's products. This is a common pattern: filter at collection level, then filter at array element level.

**Hint 3 - `$cond` and `$ifNull`**: These are aggregation expressions for conditional logic. `$ifNull: ["$field", default]` returns the field's value if it exists, or the default. `$cond: {if, then, else}` is a ternary operator.

</details>

---

### Exercise 4: Promotion Performance Report - `$project` + `$addFields`

**Aggregation Concepts**: `$addFields`, `$project`, `$cond`, `$divide`, `$multiply`, `$switch`, computed fields

**Business Question**: "Generate a performance report for all active/ended promotions with computed metrics."

#### Method: `promotion_performance_report`
```python
async def promotion_performance_report(self) -> List[Dict]:
```

**The Pipeline:**

```python
pipeline = [
    # Stage 1: Filter to promotions that have been active
    {"$match": {
        "status": {"$in": ["active", "paused", "ended"]},
        "deleted_at": None
    }},

    # Stage 2: Add computed fields
    {"$addFields": {
        # Click-through rate
        "computed_ctr": {
            "$cond": {
                "if": {"$gt": ["$stats.impressions", 0]},
                "then": {"$multiply": [
                    {"$divide": ["$stats.clicks", "$stats.impressions"]},
                    100
                ]},
                "else": 0
            }
        },
        # Conversion rate
        "computed_cvr": {
            "$cond": {
                "if": {"$gt": ["$stats.clicks", 0]},
                "then": {"$multiply": [
                    {"$divide": ["$stats.conversions", "$stats.clicks"]},
                    100
                ]},
                "else": 0
            }
        },
        # Revenue per impression (RPI)
        "revenue_per_impression": {
            "$cond": {
                "if": {"$gt": ["$stats.impressions", 0]},
                "then": {"$divide": ["$stats.revenue_cents", "$stats.impressions"]},
                "else": 0
            }
        },
        # Total products in promotion
        "product_count": {"$size": "$products"},

        # Performance tier
        "performance_tier": {
            "$switch": {
                "branches": [
                    {"case": {"$gte": ["$stats.conversions", 100]}, "then": "star"},
                    {"case": {"$gte": ["$stats.conversions", 50]}, "then": "high"},
                    {"case": {"$gte": ["$stats.conversions", 10]}, "then": "medium"},
                ],
                "default": "low"
            }
        }
    }},

    # Stage 3: Sort by revenue
    {"$sort": {"stats.revenue_cents": -1}},

    # Stage 4: Project final shape
    {"$project": {
        "_id": 0,
        "promotion_id": {"$toString": "$_id"},
        "title": 1,
        "type": "$promotion_type",
        "status": 1,
        "supplier_name": "$supplier.business_name",
        "product_count": 1,
        "visibility_type": "$visibility.type",
        "impressions": "$stats.impressions",
        "clicks": "$stats.clicks",
        "conversions": "$stats.conversions",
        "revenue_cents": "$stats.revenue_cents",
        "revenue_dollars": {"$divide": ["$stats.revenue_cents", 100]},
        "ctr_percent": {"$round": ["$computed_ctr", 2]},
        "cvr_percent": {"$round": ["$computed_cvr", 2]},
        "revenue_per_impression": {"$round": ["$revenue_per_impression", 2]},
        "performance_tier": 1,
        "start_date": "$schedule.start_date",
        "end_date": "$schedule.end_date"
    }}
]

return await Promotion.aggregate(pipeline).to_list()
```

**Key aggregation expressions:**

**`$addFields`** vs **`$project`**: `$addFields` adds new fields while keeping ALL existing fields. `$project` explicitly includes/excludes fields. Use `$addFields` for intermediate computation, `$project` for final output shaping.

**`$switch`**: MongoDB's equivalent of SQL's `CASE WHEN`. Each `branch` has a `case` (condition) and `then` (value). The `default` handles unmatched cases.

**`$size`**: Returns the length of an array field. `{"$size": "$products"}` gives the number of products in each promotion.

<details>
<summary>Hints</summary>

**Hint 1 - Division by zero**: Always wrap `$divide` in `$cond` that checks the denominator is `> 0`. MongoDB will error on division by zero without this guard.

**Hint 2 - `$round`**: `$round: [value, places]` rounds to N decimal places. `$round: ["$ctr", 2]` gives "12.34" instead of "12.341592...".

**Hint 3 - $addFields then $project**: The two-stage approach is cleaner than doing everything in `$project`. First compute intermediate values (`$addFields`), then select and format final output (`$project`).

</details>

---

### Exercise 5: Product Price Distribution - `$bucket`

**Aggregation Concepts**: `$bucket`, `$push`, `$sum`, range-based grouping

**Business Question**: "How are our product prices distributed? How many products in each price range?"

#### Method: `product_price_distribution`
```python
async def product_price_distribution(self, currency: str = "USD") -> List[Dict]:
```

**The Pipeline:**

```python
pipeline = [
    # Stage 1: Only active, non-deleted products
    {"$match": {
        "status": "active",
        "deleted_at": None,
        "currency": currency.upper()
    }},

    # Stage 2: $bucket - Group into price ranges
    {"$bucket": {
        "groupBy": "$base_price_cents",
        "boundaries": [0, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 1000000],
        # Boundaries: $0, $10, $25, $50, $100, $250, $500, $1000, $10000
        "default": "1000000+",  # Catches anything above $10,000
        "output": {
            "count": {"$sum": 1},
            "avg_price_cents": {"$avg": "$base_price_cents"},
            "min_price_cents": {"$min": "$base_price_cents"},
            "max_price_cents": {"$max": "$base_price_cents"},
            "products": {"$push": {
                "name": "$name",
                "price_cents": "$base_price_cents"
            }}
        }
    }},

    # Stage 3: Add human-readable labels
    {"$addFields": {
        "price_range": {
            "$switch": {
                "branches": [
                    {"case": {"$eq": ["$_id", 0]}, "then": "$0 - $9.99"},
                    {"case": {"$eq": ["$_id", 1000]}, "then": "$10 - $24.99"},
                    {"case": {"$eq": ["$_id", 2500]}, "then": "$25 - $49.99"},
                    {"case": {"$eq": ["$_id", 5000]}, "then": "$50 - $99.99"},
                    {"case": {"$eq": ["$_id", 10000]}, "then": "$100 - $249.99"},
                    {"case": {"$eq": ["$_id", 25000]}, "then": "$250 - $499.99"},
                    {"case": {"$eq": ["$_id", 50000]}, "then": "$500 - $999.99"},
                    {"case": {"$eq": ["$_id", 100000]}, "then": "$1,000 - $9,999.99"}
                ],
                "default": "$10,000+"
            }
        }
    }},

    # Stage 4: Final projection
    {"$project": {
        "_id": 0,
        "price_range": 1,
        "count": 1,
        "avg_price_dollars": {"$round": [{"$divide": ["$avg_price_cents", 100]}, 2]},
        "min_price_dollars": {"$divide": ["$min_price_cents", 100]},
        "max_price_dollars": {"$divide": ["$max_price_cents", 100]},
        "sample_products": {"$slice": ["$products", 3]}
    }}
]

return await Product.aggregate(pipeline).to_list()
```

**Understanding `$bucket`:**

```
Products:  Widget($5), Gadget($15), Tool($80), Machine($200)

$bucket with boundaries [0, 1000, 5000, 10000, 25000]:

Bucket $0-$9.99:    [Widget($5)]           -> count: 1
Bucket $10-$49.99:  [Gadget($15)]          -> count: 1
Bucket $50-$99.99:  [Tool($80)]            -> count: 1
Bucket $100-$249.99:[Machine($200)]        -> count: 1
```

Each document falls into the bucket where `boundaries[i] <= value < boundaries[i+1]`.

**`$push` inside `$bucket`**: Collects matching documents into an array. We later use `$slice` to take only the first 3 as samples (avoid huge arrays).

<details>
<summary>Hints</summary>

**Hint 1 - Boundaries in cents**: Since `base_price_cents` stores prices in cents, boundaries are also in cents. `1000` cents = $10.00, `5000` = $50.00, etc.

**Hint 2 - `default`**: Documents that don't fall into any bucket (price >= $10,000) go into the `default` bucket. The `_id` of the default bucket is the string you provide.

**Hint 3 - `$slice`**: `$slice: ["$products", 3]` takes the first 3 elements of the array. Without this, a bucket with 1000 products would return all 1000 names.

</details>

---

### Exercise 6: Daily Revenue - `$dateToString` (Time-Series)

**Aggregation Concepts**: `$dateToString`, `$group` by formatted date, `$sort`, time-series analysis

**Business Question**: "What is our daily revenue trend over the last N days?"

#### Method: `daily_revenue`
```python
async def daily_revenue(self, days: int = 30) -> List[Dict]:
```

**The Pipeline:**

```python
cutoff = utc_now() - timedelta(days=days)

pipeline = [
    # Stage 1: Filter to recent confirmed orders
    {"$match": {
        "status": {"$in": ["confirmed", "processing", "shipped", "delivered"]},
        "created_at": {"$gte": cutoff}
    }},

    # Stage 2: Group by date string
    {"$group": {
        "_id": {
            "$dateToString": {
                "format": "%Y-%m-%d",
                "date": "$created_at"
            }
        },
        "revenue_cents": {"$sum": "$totals.total_cents"},
        "order_count": {"$sum": 1},
        "items_sold": {"$sum": {"$size": "$items"}},
        "avg_order_value_cents": {"$avg": "$totals.total_cents"},
        "max_order_cents": {"$max": "$totals.total_cents"},
        "unique_customers": {"$addToSet": "$customer.user_id"}
    }},

    # Stage 3: Add computed fields
    {"$addFields": {
        "unique_customer_count": {"$size": "$unique_customers"}
    }},

    # Stage 4: Sort by date ascending (timeline order)
    {"$sort": {"_id": 1}},

    # Stage 5: Clean output
    {"$project": {
        "_id": 0,
        "date": "$_id",
        "revenue_cents": 1,
        "revenue_dollars": {"$divide": ["$revenue_cents", 100]},
        "order_count": 1,
        "items_sold": 1,
        "avg_order_value_cents": {"$round": ["$avg_order_value_cents", 0]},
        "max_order_cents": 1,
        "unique_customer_count": 1
    }}
]

return await Order.aggregate(pipeline).to_list()
```

**Understanding `$dateToString`:**

```python
# Input document: {"created_at": ISODate("2025-06-15T14:32:10Z")}
{"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
# Output: "2025-06-15"

# Used as $group _id, this groups all orders from the same day together
```

**Format tokens**: `%Y` = 4-digit year, `%m` = month, `%d` = day, `%H` = hour.
- Daily: `"%Y-%m-%d"` -> "2025-06-15"
- Monthly: `"%Y-%m"` -> "2025-06"
- Hourly: `"%Y-%m-%dT%H"` -> "2025-06-15T14"

**`$addToSet` for unique counts**: `$addToSet: "$customer.user_id"` collects unique customer IDs per day. Then `$size` counts them. This gives "unique customers per day" without needing `$distinct`.

<details>
<summary>Hints</summary>

**Hint 1 - Timezone**: `$dateToString` defaults to UTC. If you need local timezone: `{"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at", "timezone": "America/New_York"}}`.

**Hint 2 - Missing days**: If no orders were placed on a particular day, that date won't appear in the results. The pipeline only returns days that have data. Filling gaps (zero-revenue days) must be done in application code.

**Hint 3 - `$size` on `$items`**: `$size: "$items"` counts items per order BEFORE grouping. Inside `$group`, this is summed to get total items sold per day.

</details>

**Expected Output:**
```json
[
  {"date": "2025-06-01", "revenue_cents": 125000, "revenue_dollars": 1250.00, "order_count": 8, "items_sold": 15, "unique_customer_count": 6},
  {"date": "2025-06-02", "revenue_cents": 89000, "revenue_dollars": 890.00, "order_count": 5, "items_sold": 9, "unique_customer_count": 4},
  ...
]
```

---

### Exercise 7: Top Community Categories - `$sortByCount`

**Aggregation Concepts**: `$sortByCount` (shorthand), and the equivalent `$group` + `$sort` expansion

**Business Question**: "What are the most popular community categories on the platform?"

#### Method: `top_community_categories`
```python
async def top_community_categories(self, limit: int = 10) -> List[Dict]:
```

**The Simple Way - `$sortByCount`:**

```python
pipeline = [
    # Stage 1: Active communities only
    {"$match": {
        "status": "active",
        "deleted_at": None
    }},

    # Stage 2: sortByCount on category
    {"$sortByCount": "$category"},

    # Stage 3: Limit
    {"$limit": limit},

    # Stage 4: Rename fields
    {"$project": {
        "_id": 0,
        "category": "$_id",
        "community_count": "$count"
    }}
]

return await Community.aggregate(pipeline).to_list()
```

**`$sortByCount`** is a shorthand that expands to:
```python
# These two are equivalent:
{"$sortByCount": "$category"}

# Expands to:
{"$group": {"_id": "$category", "count": {"$sum": 1}}},
{"$sort": {"count": -1}}
```

**Now enhance it** - add richer metrics per category:

```python
pipeline = [
    {"$match": {"status": "active", "deleted_at": None}},

    {"$group": {
        "_id": "$category",
        "community_count": {"$sum": 1},
        "total_members": {"$sum": "$member_count"},
        "avg_members": {"$avg": "$member_count"},
        "verified_count": {"$sum": {
            "$cond": [{"$eq": ["$is_verified", True]}, 1, 0]
        }},
        "featured_count": {"$sum": {
            "$cond": [{"$eq": ["$is_featured", True]}, 1, 0]
        }},
        "top_community": {"$first": "$name"}  # After sort by member_count
    }},

    {"$sort": {"community_count": -1}},
    {"$limit": limit},

    {"$project": {
        "_id": 0,
        "category": "$_id",
        "community_count": 1,
        "total_members": 1,
        "avg_members": {"$round": ["$avg_members", 0]},
        "verified_count": 1,
        "featured_count": 1,
        "top_community": 1
    }}
]
```

**Conditional accumulation**: `$cond: [condition, true_value, false_value]` is the array-form ternary. Inside `$sum`, it acts as a conditional counter: count 1 if verified, 0 if not.

<details>
<summary>Hints</summary>

**Hint 1 - `$sortByCount` limitations**: It only gives you count. If you need additional metrics (total members, averages), you must expand to the full `$group` + `$sort` pattern.

**Hint 2 - `$cond` in `$sum`**: This is the idiomatic way to do "COUNT WHERE" in aggregation. `$sum: {$cond: [{$eq: ["$field", value]}, 1, 0]}` counts documents where field equals value.

</details>

---

### Exercise 8: Platform Dashboard - `$facet` (The Grand Finale)

**Aggregation Concepts**: `$facet`, multiple parallel pipelines, `$count`, combining results from different collections

**Business Question**: "Generate a complete platform dashboard with stats from every collection in a single operation."

#### Method: `platform_dashboard`
```python
async def platform_dashboard(self) -> Dict[str, Any]:
```

**`$facet` runs multiple pipelines in parallel on the same input:**

```
Input Documents
    |
    +---> Pipeline A (total count)        -> result_a
    +---> Pipeline B (status breakdown)   -> result_b
    +---> Pipeline C (recent activity)    -> result_c
    |
    v
{ result_a: [...], result_b: [...], result_c: [...] }
```

**Step 1: Order Dashboard Facet**

```python
order_pipeline = [
    {"$facet": {
        # Facet 1: Overall stats
        "overview": [
            {"$match": {"status": {"$ne": "failed"}}},
            {"$group": {
                "_id": None,
                "total_orders": {"$sum": 1},
                "total_revenue_cents": {"$sum": "$totals.total_cents"},
                "avg_order_value": {"$avg": "$totals.total_cents"},
                "total_items_sold": {"$sum": {"$size": "$items"}}
            }},
            {"$project": {"_id": 0}}
        ],

        # Facet 2: Orders by status
        "by_status": [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$project": {"_id": 0, "status": "$_id", "count": 1}}
        ],

        # Facet 3: Revenue by month
        "monthly_revenue": [
            {"$match": {"status": {"$in": ["confirmed", "processing", "shipped", "delivered"]}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                "revenue_cents": {"$sum": "$totals.total_cents"},
                "order_count": {"$sum": 1}
            }},
            {"$sort": {"_id": -1}},
            {"$limit": 6},
            {"$project": {"_id": 0, "month": "$_id", "revenue_cents": 1, "order_count": 1}}
        ],

        # Facet 4: Top 5 customers
        "top_customers": [
            {"$match": {"status": {"$in": ["confirmed", "processing", "shipped", "delivered"]}}},
            {"$group": {
                "_id": "$customer.user_id",
                "customer_name": {"$first": "$customer.display_name"},
                "order_count": {"$sum": 1},
                "total_spent_cents": {"$sum": "$totals.total_cents"}
            }},
            {"$sort": {"total_spent_cents": -1}},
            {"$limit": 5},
            {"$project": {
                "_id": 0,
                "customer_id": {"$toString": "$_id"},
                "customer_name": 1,
                "order_count": 1,
                "total_spent_cents": 1
            }}
        ]
    }}
]

order_stats = await Order.aggregate(order_pipeline).to_list()
```

**Step 2: Gather stats from other collections**

Since `$facet` runs within ONE collection, you need separate aggregations for other collections:

```python
# User stats
user_stats = await User.aggregate([
    {"$facet": {
        "total": [{"$count": "count"}],
        "by_role": [
            {"$group": {"_id": "$role", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "role": "$_id", "count": 1}}
        ],
        "recent_signups": [
            {"$match": {"created_at": {"$gte": utc_now() - timedelta(days=30)}}},
            {"$count": "count"}
        ]
    }}
]).to_list()

# Product stats
product_stats = await Product.aggregate([
    {"$facet": {
        "total": [{"$match": {"deleted_at": None}}, {"$count": "count"}],
        "by_status": [
            {"$match": {"deleted_at": None}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "status": "$_id", "count": 1}}
        ],
        "avg_price": [
            {"$match": {"status": "active", "deleted_at": None}},
            {"$group": {"_id": None, "avg_cents": {"$avg": "$base_price_cents"}}},
            {"$project": {"_id": 0}}
        ]
    }}
]).to_list()

# Community stats
community_stats = await Community.aggregate([
    {"$facet": {
        "total": [{"$match": {"deleted_at": None}}, {"$count": "count"}],
        "total_members": [
            {"$match": {"status": "active", "deleted_at": None}},
            {"$group": {"_id": None, "sum": {"$sum": "$member_count"}}},
            {"$project": {"_id": 0}}
        ],
        "top_categories": [
            {"$match": {"status": "active", "deleted_at": None}},
            {"$sortByCount": "$category"},
            {"$limit": 5},
            {"$project": {"_id": 0, "category": "$_id", "count": "$count"}}
        ]
    }}
]).to_list()

# Promotion stats
promo_stats = await Promotion.aggregate([
    {"$facet": {
        "total": [{"$match": {"deleted_at": None}}, {"$count": "count"}],
        "active": [{"$match": {"status": "active", "deleted_at": None}}, {"$count": "count"}],
        "total_impressions": [
            {"$group": {"_id": None, "sum": {"$sum": "$stats.impressions"}}},
            {"$project": {"_id": 0}}
        ]
    }}
]).to_list()
```

**Step 3: Combine into dashboard**

```python
# Helper to safely extract facet results
def _extract(facet_result, key, default=None):
    if facet_result and facet_result[0].get(key):
        return facet_result[0][key]
    return default if default is not None else []

return {
    "generated_at": utc_now().isoformat(),
    "orders": {
        "overview": _extract(order_stats, "overview", [{}])[0] if _extract(order_stats, "overview") else {},
        "by_status": _extract(order_stats, "by_status"),
        "monthly_revenue": _extract(order_stats, "monthly_revenue"),
        "top_customers": _extract(order_stats, "top_customers")
    },
    "users": {
        "total": _extract(user_stats, "total", [{"count": 0}])[0].get("count", 0),
        "by_role": _extract(user_stats, "by_role"),
        "recent_signups_30d": _extract(user_stats, "recent_signups", [{"count": 0}])[0].get("count", 0)
    },
    "products": {
        "total": _extract(product_stats, "total", [{"count": 0}])[0].get("count", 0),
        "by_status": _extract(product_stats, "by_status"),
        "avg_price_cents": _extract(product_stats, "avg_price", [{}])[0].get("avg_cents", 0)
    },
    "communities": {
        "total": _extract(community_stats, "total", [{"count": 0}])[0].get("count", 0),
        "total_members": _extract(community_stats, "total_members", [{"sum": 0}])[0].get("sum", 0),
        "top_categories": _extract(community_stats, "top_categories")
    },
    "promotions": {
        "total": _extract(promo_stats, "total", [{"count": 0}])[0].get("count", 0),
        "active": _extract(promo_stats, "active", [{"count": 0}])[0].get("count", 0),
        "total_impressions": _extract(promo_stats, "total_impressions", [{"sum": 0}])[0].get("sum", 0)
    }
}
```

**Why `$facet` is powerful**: Without `$facet`, the order dashboard would require 4 separate database round-trips. With `$facet`, it's 1 round-trip that runs 4 sub-pipelines in parallel on the server.

**Why multiple `$facet` calls**: `$facet` operates within a single collection. To get stats from orders, users, products, communities, and promotions, you need one `$facet` per collection (5 total round-trips instead of ~20).

<details>
<summary>Hints</summary>

**Hint 1 - `$count` stage**: `{"$count": "field_name"}` returns `{"field_name": N}`. It's a shorthand for `{"$group": {"_id": null, "field_name": {"$sum": 1}}}`.

**Hint 2 - Empty facet results**: A facet with no matching documents returns `[]` (empty array), not `[{count: 0}]`. Always handle empty results with defaults.

**Hint 3 - Performance**: Each `$facet` scans the collection once but runs all sub-pipelines. A `$match` at the top of a sub-pipeline uses indexes. But `$facet` itself cannot be preceded by stages that change the document set differently per facet - that's why each facet sub-pipeline starts with its own `$match`.

</details>

---

## 6. VERIFICATION CHECKLIST

Since there are no routes for analytics, verify by calling methods directly or via the MongoDB shell.

### Option A: Python Test Script

Create `test_analytics.py`:

```python
import asyncio
from services.analytics import AnalyticsService

async def main():
    # Initialize Beanie (copy from your app startup)
    analytics = AnalyticsService()

    # Exercise 1
    revenue = await analytics.revenue_by_supplier()
    print("Revenue by supplier:", revenue)

    # Exercise 2
    top_products = await analytics.top_products_by_order_count(limit=5)
    print("Top products:", top_products)

    # ... etc for each exercise

    # Exercise 8
    dashboard = await analytics.platform_dashboard()
    print("Dashboard:", json.dumps(dashboard, indent=2, default=str))

asyncio.run(main())
```

### Option B: MongoDB Shell (mongosh)

You can run any pipeline directly in the shell:

```javascript
// Exercise 1: Revenue by supplier
db.orders.aggregate([
  {$match: {status: {$in: ["confirmed", "processing", "shipped", "delivered"]}}},
  {$unwind: "$items"},
  {$group: {
    _id: "$items.product_snapshot.supplier_id",
    total: {$sum: "$items.final_price_cents"},
    count: {$sum: 1}
  }},
  {$sort: {total: -1}}
])

// Exercise 5: Price distribution
db.products.aggregate([
  {$match: {status: "active", deleted_at: null}},
  {$bucket: {
    groupBy: "$base_price_cents",
    boundaries: [0, 1000, 2500, 5000, 10000, 25000, 50000, 100000],
    default: "expensive",
    output: {count: {$sum: 1}, avg: {$avg: "$base_price_cents"}}
  }}
])
```

### Checklist

- [ ] Exercise 1: Revenue by supplier returns sorted list with dollars/cents
- [ ] Exercise 2: Top products shows order frequency and quantity
- [ ] Exercise 3: `$lookup` enriches orders with current product data
- [ ] Exercise 4: Promotion report has computed CTR, CVR, and performance tier
- [ ] Exercise 5: Price buckets have counts and sample products
- [ ] Exercise 6: Daily revenue shows time series for last N days
- [ ] Exercise 7: Category frequency sorted by count
- [ ] Exercise 8: Dashboard combines stats from all collections

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Pipeline Performance Analysis

Run `explain` on your pipelines to see execution stats:

```javascript
db.orders.explain("executionStats").aggregate([
  {$match: {status: {$in: ["confirmed", "processing", "shipped", "delivered"]}}},
  {$unwind: "$items"},
  {$group: {_id: "$items.product_snapshot.supplier_id", total: {$sum: "$items.final_price_cents"}}}
])
```

**Questions**:
1. Which stages use indexes? Which ones scan in memory?
2. Move the `$match` after `$unwind` and compare the `executionStats`. What changes?
3. Can `$group` ever use an index? Under what conditions?
4. For Exercise 6 (daily revenue), add an index on `[("status", 1), ("created_at", -1)]` and re-run explain. Does it help?

### Challenge 2: Build a $graphLookup

MongoDB supports recursive graph traversal with `$graphLookup`. Design a pipeline that finds the "social reach" of a community:

```
Community A has members [User1, User2, User3]
User1 is in communities [A, B]
User2 is in communities [A, C, D]
User3 is in communities [A]

Community A's "reach" = communities {B, C, D} (reachable through shared members)
```

**Questions**:
1. Write a `$graphLookup` that starts from a community, traverses through `member_ids` to users, and then to their other communities
2. This is computationally expensive. At what scale does it become impractical?
3. How would you pre-compute this as a "related communities" cache?

### Challenge 3: Window Functions with $setWindowFields

MongoDB 5.0+ supports window functions. Design a pipeline that computes:
- Running total of revenue per day
- 7-day moving average of order count
- Rank of each day's revenue within the month

```javascript
{$setWindowFields: {
  sortBy: {date: 1},
  output: {
    running_total: {
      $sum: "$revenue_cents",
      window: {documents: ["unbounded", "current"]}
    },
    moving_avg_7d: {
      $avg: "$order_count",
      window: {documents: [-6, "current"]}
    },
    revenue_rank: {
      $rank: {},
      window: {partitionBy: {$substr: ["$date", 0, 7]}}
    }
  }
}}
```

---

## 8. COURSE COMPLETION

Congratulations! You've completed all 8 tasks of the MongoDB Advanced Learning course.

### What You've Built

| Task | Domain | Key Skill |
|------|--------|-----------|
| 01 | User/Auth | CRUD basics, `find_one`, nested fields |
| 02 | Supplier | Complex nested docs, array queries |
| 03 | Community | `$addToSet`/`$pull`, cursor pagination, `$or` |
| 04 | Product | `Dict` fields, `$all`, `$text` search, `$gte`/`$lte` |
| 05 | Post | `$or`+`$and` composition, base64 cursors, 3-tier access |
| 06 | Promotion | Skip pagination, dynamic keys, date ranges, multi-scope approval |
| 07 | Order | Idempotency, price drift, inventory reservation, rollback |
| 08 | Analytics | **Aggregation pipelines**: `$group`, `$unwind`, `$lookup`, `$facet`, `$bucket` |

### MongoDB Mastery Checklist

After completing this course, you should be confident with:

- [ ] **Query operators**: `$in`, `$ne`, `$all`, `$gte`, `$lte`, `$or`, `$and`, `$text`
- [ ] **Update operators**: `$set` (via save), `$addToSet`, `$pull`, `$inc`
- [ ] **Aggregation stages**: `$match`, `$group`, `$unwind`, `$lookup`, `$project`, `$addFields`, `$bucket`, `$facet`, `$sortByCount`, `$dateToString`
- [ ] **Aggregation expressions**: `$sum`, `$avg`, `$min`, `$max`, `$first`, `$push`, `$addToSet`, `$size`, `$cond`, `$switch`, `$divide`, `$round`, `$toString`
- [ ] **Pagination**: Cursor-based (ascending `$gt`, descending `$lt`) and skip-based
- [ ] **Data patterns**: Denormalization, snapshots, soft delete, optimistic locking
- [ ] **Indexing**: Understanding compound indexes, multikey indexes, text indexes, unique indexes
- [ ] **Design patterns**: Anti-enumeration, idempotency, state machines, cross-collection validation
