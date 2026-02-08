# TASK 04: Product Catalog Service

## 1. MISSION BRIEFING

Products are the **commerce core** of the platform. While Users socialize and Communities curate, Products are what actually get bought and sold. Every product is owned by a Supplier and goes through a lifecycle from draft to active to eventually discontinued or deleted.

This is the **most structurally complex entity** you've built so far. The Product model has 8 different embedded document types, a `Dict[str, ProductVariant]` map field (not just a list!), multi-location inventory tracking, and a 5-state lifecycle machine. You'll also write the first **public-facing discovery endpoint** with price range filters, tag matching, and full-text search.

### What You Will Build
The `ProductService` class - 13 methods covering CRUD, a 5-state lifecycle machine, cross-collection supplier validation, public product discovery with advanced filtering, and inventory-aware operations.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **`Dict` (Map) field queries** | Variants stored as `Dict[str, ProductVariant]` - querying nested dict values |
| **`$all` operator** | Tag filtering - product must have ALL specified tags |
| **`$gte` / `$lte` range queries** | Price range filtering on `base_price_cents` |
| **`$text` / `$search`** | Full-text search on product name/description |
| **`$in` operator** | Multi-status filtering (`status in ["active", "draft"]`) |
| **`$ne` with compound queries** | Name uniqueness excluding current doc + SKU uniqueness per supplier |
| **`$addToSet` atomic update** | Adding product ID to supplier's `product_ids` array |
| **Cross-collection validation** | Supplier must exist and be verified before publishing |
| **Denormalized data** | Caching `supplier_info` dict on product document |
| **State machine transitions** | 5-status lifecycle with guarded transitions |
| **Complex document construction** | Building 8+ embedded sub-documents from flat request data |
| **Cursor pagination** | Both supplier listing and public discovery |
| **Multi-condition `find_one`** | Public product requires `status=active` + `is_available=True` + `deleted_at=None` |
| **Idempotent delete** | Soft delete returns success even if already deleted |

### How This Differs From Previous Tasks

| Aspect | Auth (01/02) | Community (03) | Product (04) |
|--------|-------------|----------------|-------------|
| Embedded docs | 2-3 types | 1 type (CommunityOwner) | **8 types** |
| Data structure | Lists + flat fields | Lists (member_ids, tags) | **Dict/Map** (variants) + Lists |
| Query operators | `$ne` | `$in`, `$ne`, `$or`, `$gt`/`$lt` | **`$all`, `$gte`/`$lte`, `$text`**, `$in`, `$ne` |
| Collections touched | 1 | 2 (+ moderation_log) | **2** (products + suppliers for validation) |
| Write pattern | Insert + update | Insert + partial + version | **Insert + partial + lifecycle transitions** |
| Public access | None | Discovery endpoint | **Full public catalog** with advanced filters |
| Inventory | N/A | Member count | **Multi-location + variant inventory math** |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - You need users in the database
- **TASK_02 (Supplier) must be complete** - Products require a verified supplier
- **TASK_03 (Community) must be complete** - You practiced cursor pagination there
- Have at least one registered, verified supplier from TASK_02

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/product.py` | The data model - 667 lines, 8 embedded types, 11 indexes, Dict-based variants |
| 2 | `apps/backend-service/src/schemas/product.py` | Request/response schemas including nested variant/location requests |
| 3 | `apps/backend-service/src/routes/product.py` | 9 endpoints: CRUD + 4 lifecycle + public access |
| 4 | `shared/models/supplier.py` | Cross-collection reference - you'll read supplier data |
| 5 | `apps/backend-service/src/kafka/topics.py` | `Topic.PRODUCT` for event emission |

### The Data Flow

```
HTTP Request (Supplier JWT)
    │
    ▼
┌─────────┐   Extracts supplier_id from
│  Route   │   X-Supplier-ID header
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────────────┐
│              ProductService (YOU WRITE THIS)           │
│                                                        │
│  Reads from TWO collections:                           │
│  ├── products (main CRUD + lifecycle)                  │
│  └── suppliers (validation: exists? verified? limits?) │
│                                                        │
│  Writes to TWO collections:                            │
│  ├── products (insert, update, status changes)         │
│  └── suppliers ($addToSet product_id to supplier)      │
│                                                        │
│  Also emits Kafka events:                              │
│  └── Topic.PRODUCT → created, deleted, published,      │
│       discontinued, out_of_stock                       │
└──────────────────────────────────────────────────────┘
```

### The Product Lifecycle State Machine

```
                 ┌───────────────┐
                 │    DRAFT      │  ← Created here
                 └───────┬───────┘
                         │ publish_product()
                         ▼
                 ┌───────────────┐
            ┌───▶│    ACTIVE     │◀─── (not directly restorable)
            │    └──┬─────────┬──┘
            │       │         │
            │  mark_out_of    │ discontinue_product()
            │  _stock()       │
            │       ▼         ▼
            │ ┌──────────┐ ┌──────────────┐
            │ │OUT_OF_   │ │DISCONTINUED  │
            │ │STOCK     │ │              │
            │ └──────────┘ └──────────────┘
            │       │
            │       │ discontinue_product() (also valid)
            │       ▼
            │ ┌──────────────┐
            │ │DISCONTINUED  │
            │ └──────────────┘
            │
            │
            │  ┌───────────────┐
            │  │   DELETED     │  ← soft_delete() from any non-deleted state
            │  └───────┬───────┘
            │          │ restore_product()
            └──────────┘ (back to DRAFT, not ACTIVE)
```

---

## 3. MODEL DEEP DIVE

### Embedded Document Hierarchy (8 types!)

```
Product (Document)
│
├── supplier_info: Dict[str, str]              ← Denormalized supplier snapshot
│
├── images: ProductImages                       ← Primary + gallery + video
│
├── topic_descriptions: List[TopicDescription]  ← Structured product descriptions
│
├── metadata: ProductMetadata                   ← SKU, brand, tags, custom_attributes
│   └── tags: List[str]                         ← Multikey index for tag search
│   └── custom_attributes: Dict[str, str]       ← Flexible key-value pairs
│
├── stock_locations: List[StockLocation]        ← Multi-warehouse inventory
│   └── Each has: quantity, reserved, optional price_cents override
│
├── variants: Dict[str, ProductVariant]         ← THE BIG ONE: Map of variants
│   └── Each variant has:
│       ├── attributes: List[VariantAttribute]  ← Color: Red, Size: L
│       ├── package_dimensions: PackageDimensions
│       ├── price_cents, quantity, reserved
│       └── sku (unique within product)
│
├── shipping: ShippingInfo                      ← Free shipping, origin country, delivery
│
├── stats: ProductStats                         ← Denormalized counters (views, purchases, ratings)
│
└── status / version / timestamps               ← Lifecycle + optimistic locking
```

### Why `variants` is a `Dict` Not a `List`

```python
# Model definition (product.py line 314-317):
variants: Dict[str, ProductVariant]  # Keyed by variant_name

# In MongoDB, stored as:
{
  "variants": {
    "Red-Large": { "variant_id": "v1", "sku": "SHOE-RED-L", ... },
    "Blue-Small": { "variant_id": "v2", "sku": "SHOE-BLU-S", ... }
  }
}
```

This is different from Community's `member_ids: List[PydanticObjectId]`. A Dict/Map gives you:
- **O(1) lookup by name** (`variants.get("Red-Large")`)
- **Unique keys enforced** by Python dict
- **But**: you can't use `$in` on dict keys, and querying deep into dict values requires dot-notation on dynamic keys

### Index Analysis (11 indexes)

```python
indexes = [
    # Index 1: Supplier's products listing
    [("supplier_id", 1), ("status", 1), ("created_at", -1)],
    # → Used by: list_products() - YOUR most-used index

    # Index 2: Category-based discovery with rating sort
    [("category", 1), ("status", 1), ("stats.average_rating", -1)],
    # → Used by: list_public_products() when filtering by category

    # Index 3: Slug lookup
    [("slug", 1)],
    # → Used by: potential future slug-based lookup

    # Index 4: Name uniqueness (trademark)
    [("name", 1)],
    # → Used by: _check_name_uniqueness()

    # Index 5: SKU uniqueness per supplier
    [("supplier_id", 1), ("metadata.base_sku", 1)],
    # → Used by: _check_sku_uniqueness() - COMPOUND index

    # Index 6: Tag search (MULTIKEY)
    [("metadata.tags", 1), ("status", 1)],
    # → Used by: list_public_products() with tags_filter

    # Index 7: Variant SKU search
    [("variants.sku", 1)],
    # → NOTE: This indexes into the Dict values!

    # Index 8: Stock location search
    [("stock_locations.location_id", 1)],
    # → Used by: location-based inventory lookups

    # Index 9: Public product listing
    [("status", 1), ("deleted_at", 1), ("is_available", 1), ("created_at", -1)],
    # → Used by: list_public_products() - the public discovery index

    # Index 10: Soft delete
    [("deleted_at", 1)],
    # → Used by: cleanup jobs

    # Index 11: Popular products
    [("stats.purchase_count", -1), ("status", 1)],
    # → Used by: potential "popular products" feature
]
```

### Key Model Helper Methods (already implemented for you)

| Method | What It Does | When You'll Use It |
|--------|-------------|-------------------|
| `get_total_inventory()` | Sum `quantity` across all locations + all variants | Building list response |
| `get_total_available()` | Sum `available` (quantity - reserved) across all | Publish validation |
| `get_price_range()` | Min/max price across variants | Public product response |
| `get_variant_by_name(name)` | Dict lookup | Variant operations |
| `get_variant_by_id(id)` | Loop through dict values | Variant by ID |
| `get_location_by_id(id)` | Loop through list | Location operations |
| `publish()` | Sets status=ACTIVE, is_available=True, published_at | `publish_product()` |
| `soft_delete()` | Sets deleted_at, status=DELETED, is_available=False | `delete_product()` |
| `to_public_dict()` | Full public-safe serialization | `list_public_products()` |

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/backend-service/src/services/product.py`

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_generate_slug(name)` | None (pure Python) | Easy |
| 2 | `_check_supplier_can_create(supplier)` | Permission checks on model | Easy |
| 3 | `_check_name_uniqueness(name, exclude_id)` | `find_one` + `$ne` | Medium |
| 4 | `_check_sku_uniqueness(supplier_id, sku, exclude_id)` | Compound `find_one` + `$ne` | Medium |
| 5 | `_add_product_to_supplier(supplier, product_id)` | `$addToSet` atomic update | Medium |
| 6 | `_validate_publish_requirements(product)` | None (pure Python) | Easy |
| 7 | `create_product(supplier_id, product_data)` | Cross-collection get + massive insert | Hard |
| 8 | `get_product(product_id, supplier_id)` | Compound `find_one` (anti-enumeration) | Easy |
| 9 | `list_products(supplier_id, ...)` | `$in`, `$text`, cursor pagination | Hard |
| 10 | `update_product(product_id, supplier_id, updates)` | Get + uniqueness checks + partial update | Medium |
| 11 | `delete_product(product_id, supplier_id)` | Get + soft delete (idempotent) | Easy |
| 12 | `publish_product(product_id, supplier_id)` | Cross-collection supplier check + status gate | Medium |
| 13 | `discontinue_product(product_id, supplier_id)` | Status gate + transition | Easy |
| 14 | `mark_out_of_stock(product_id, supplier_id)` | Status gate + transition | Easy |
| 15 | `restore_product(product_id, supplier_id)` | Status gate + clear deleted_at | Easy |
| 16 | `get_public_product(product_id)` | Multi-condition `find_one` | Medium |
| 17 | `list_public_products(...)` | `$all`, `$gte`/`$lte`, `$text`, cursor pagination | Hard |

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods Foundation

**Concept**: Pure Python helpers + basic MongoDB queries with `$ne`

These helper methods are called by every other method in the service. Get them right first.

#### 5.1a: `_generate_slug(name)`

**What it does**: Converts a product name to a URL-friendly slug.

**Input**: `name = "Premium Wireless Headphones (2024 Edition!)"`
**Output**: `"premium-wireless-headphones-2024-edition"`

**Algorithm**:
1. Lowercase and strip the name
2. Remove all characters that aren't alphanumeric, whitespace, or hyphens
3. Replace any sequence of whitespace or hyphens with a single hyphen

> **Hint Level 1**: This is pure Python - use `re.sub()` twice.

> **Hint Level 2**: First `re.sub(r'[^\w\s-]', '', slug)` to strip special chars, then `re.sub(r'[-\s]+', '-', slug)` to collapse spaces/hyphens.

<details>
<summary>Hint Level 3 - Full Implementation</summary>

```python
def _generate_slug(self, name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug
```
</details>

---

#### 5.1b: `_check_supplier_can_create(supplier)`

**What it does**: Validates that a supplier has permission to create products.

**Business Rules**:
1. ~~Supplier must be active~~ (commented out - TODO for production)
2. ~~Supplier must be verified~~ (commented out - TODO for production)
3. Supplier must have `permissions.can_create_products == True`
4. Supplier must not have reached `permissions.max_products` limit

**Design Note**: The active/verified checks are commented out with a `# TODO: Re-enable for production` comment. This is intentional - during development, we don't want to block product creation while testing. But the permission and limit checks are always enforced.

**How to count products**: Count the length of `supplier.product_ids` list.

> **Hint Level 1**: Access `supplier.permissions.can_create_products` and `supplier.permissions.max_products`. Compare active count to max.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def _check_supplier_can_create(self, supplier: Supplier) -> None:
    if not supplier.permissions.can_create_products:
        raise ValueError("Insufficient permissions to create products")

    active_count = len([pid for pid in supplier.product_ids])
    if active_count >= supplier.permissions.max_products:
        raise ValueError(f"Maximum product limit reached ({supplier.permissions.max_products})")
```
</details>

---

#### 5.1c: `_check_name_uniqueness(name, exclude_id=None)`

**What it does**: Checks if a product name is already taken (trademark requirement). When updating, excludes the current product from the check.

**MongoDB Pattern**: `find_one` with optional `$ne` on `_id`

```
Query when CREATING:
  { "name": "Cool Headphones" }

Query when UPDATING (exclude current product):
  { "name": "Cool Headphones", "_id": { "$ne": ObjectId("abc123") } }
```

> **Why `$ne` instead of two separate queries?** A single atomic query is both faster and race-condition-safe. Without `$ne`, you'd need: "find product with this name" → "check if it's me" → gap where another insert could sneak in.

> **Hint Level 1**: Build a query dict. If `exclude_id` is provided, add `"_id": {"$ne": ObjectId(exclude_id)}` to the query.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def _check_name_uniqueness(self, name: str, exclude_id: Optional[str] = None) -> None:
    query = {"name": name}
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}

    existing = await Product.find_one(query)
    if existing:
        raise ValueError(f"Product name '{name}' already exists")
```
</details>

---

#### 5.1d: `_check_sku_uniqueness(supplier_id, base_sku, exclude_id=None)`

**What it does**: Checks if a base SKU already exists **for this specific supplier**. Different suppliers can have the same SKU.

**MongoDB Pattern**: Compound query on `supplier_id` + nested field `metadata.base_sku`

```
Query: {
  "supplier_id": PydanticObjectId("..."),
  "metadata.base_sku": "HDPH-001",    ← Dot-notation into embedded doc!
  "_id": { "$ne": ObjectId("...") }    ← Optional: exclude current
}
```

**Index used**: `[("supplier_id", 1), ("metadata.base_sku", 1)]` - compound index (Index #5)

> **Think about it**: Why is SKU uniqueness per-supplier but name uniqueness is global? Because "HDPH-001" is an internal identifier that only the supplier sees, while "Premium Wireless Headphones" is the public-facing product name (trademark).

> **Hint Level 1**: Same pattern as `_check_name_uniqueness` but with TWO conditions in the query. Remember to normalize the SKU to uppercase with `.upper()`.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def _check_sku_uniqueness(self, supplier_id: str, base_sku: str, exclude_id: Optional[str] = None) -> None:
    query = {
        "supplier_id": PydanticObjectId(supplier_id),
        "metadata.base_sku": base_sku.upper()
    }
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}

    existing = await Product.find_one(query)
    if existing:
        raise ValueError(f"SKU '{base_sku}' already exists for this supplier")
```
</details>

---

#### 5.1e: `_add_product_to_supplier(supplier, product_id)`

**What it does**: Adds the new product's ID to the supplier's `product_ids` array using `$addToSet`.

**MongoDB Pattern**: `$addToSet` - adds an element to an array ONLY if it doesn't already exist (idempotent).

```python
# $addToSet vs $push:
# $push:     Always adds → can create duplicates
# $addToSet: Only adds if not present → idempotent (safe to retry)
```

**Error handling**: Wrap in try/except, print a warning but don't fail. A reconciliation job will fix any missed updates.

> **Hint Level 1**: Use `supplier.update({"$addToSet": {"product_ids": product_id}})`. Wrap in try/except.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def _add_product_to_supplier(self, supplier: Supplier, product_id: PydanticObjectId) -> None:
    try:
        await supplier.update({"$addToSet": {"product_ids": product_id}})
    except Exception as e:
        print(f"Warning: Failed to update supplier array: {e}")
```
</details>

---

#### 5.1f: `_validate_publish_requirements(product)`

**What it does**: Business rule validation before publishing. Pure Python - no MongoDB.

**Requirements to publish**:
1. Must have a primary image (`product.images.primary_image`)
2. Must have available stock (`product.get_total_available() > 0`)
3. Must have a short description (`product.short_description`)

**Pattern**: Collect all errors, then raise once with all messages joined.

<details>
<summary>Hint Level 1 - Full Implementation</summary>

```python
def _validate_publish_requirements(self, product: Product) -> None:
    errors = []
    if not product.images or not product.images.primary_image:
        errors.append("At least one image is required")
    if product.get_total_available() <= 0:
        errors.append("Product must have available stock")
    if not product.short_description:
        errors.append("Short description is required")
    if errors:
        raise ValueError(f"Cannot publish product: {', '.join(errors)}")
```
</details>

---

### Exercise 5.2: Create Product - The Construction Challenge

**Concept**: Building a complex document with 8+ embedded types from flat request data, cross-collection validation, denormalized snapshot, and `$addToSet`

This is the **hardest construction exercise** in the entire course. The `create_product` method takes a flat `product_data` dict and must build a deeply nested `Product` document with multiple embedded objects.

#### The Method Signature

```python
async def create_product(
    self,
    supplier_id: str,
    product_data: Dict[str, Any]
) -> Dict[str, Any]:
```

#### Step-by-Step Algorithm

```
1. Get supplier by ID (cross-collection)
   └── Supplier.get(PydanticObjectId(supplier_id))
   └── Raise "Supplier not found" if None

2. Check supplier can create products
   └── await self._check_supplier_can_create(supplier)

3. Check name uniqueness (global)
   └── await self._check_name_uniqueness(product_data["name"])

4. Check SKU uniqueness (per supplier)
   └── await self._check_sku_uniqueness(supplier_id, product_data["base_sku"])

5. Generate slug from name
   └── slug = self._generate_slug(product_data["name"])

6. Build ProductImages
   └── Extract primary image (is_primary=True or first image)
   └── Extract gallery images (all non-primary)
   └── Construct ProductImages(primary_image=..., gallery_images=[...])

7. Build ProductMetadata
   └── ProductMetadata(base_sku=..., barcode=..., brand=..., tags=..., ...)

8. Build variants Dict[str, ProductVariant]
   └── For each (variant_name, variant_data) in product_data["variants"]:
       ├── Build List[VariantAttribute] from variant_data["attributes"]
       ├── Build PackageDimensions from variant_data["package_dimensions"]
       └── Build ProductVariant with all fields

9. Build List[StockLocation]
   └── For each loc in product_data["stock_locations"]:
       └── StockLocation(location_id=..., city=..., quantity=..., ...)

10. Build List[TopicDescription]
    └── For each td in product_data["topic_descriptions"]:
        └── TopicDescription(topic=..., description=..., display_order=...)

11. Build ShippingInfo
    └── ShippingInfo(free_shipping=..., ships_from_country=..., ...)

12. Build denormalized supplier_info
    └── {"id": str(supplier.id), "name": supplier.company_info.legal_name, "logo": supplier.business_info.logo or ""}

13. Construct Product document with ALL embedded objects
    └── Product(supplier_id=..., name=..., slug=..., images=..., metadata=..., variants=..., ...)
    └── Status = DRAFT, is_available = False

14. await product.insert()

15. Emit Kafka event (Topic.PRODUCT, action="created")

16. await self._add_product_to_supplier(supplier, product.id)

17. Return summary dict
```

#### The Denormalized `supplier_info` Pattern

```python
# Why store supplier data ON the product?
# Because when displaying a product, you don't want to JOIN to the suppliers collection.
# MongoDB doesn't have JOINs - instead, you embed frequently-read data.

supplier_info = {
    "id": str(supplier.id),
    "name": supplier.company_info.legal_name,  # ← From Supplier model
    "logo": supplier.business_info.logo or ""   # ← From Supplier model
}
```

> **Trade-off**: If the supplier changes their name, the product still shows the old name. This is acceptable because:
> 1. Business names rarely change
> 2. A background job can refresh denormalized data
> 3. The performance win is massive (no cross-collection lookup per product view)

#### Building the Variants Dict (the tricky part)

```python
# product_data["variants"] arrives as:
# {
#   "Red-Large": {
#     "variant_id": "v1",
#     "sku": "SHOE-RED-L",
#     "attributes": [{"attribute_name": "Color", "attribute_value": "Red"}, ...],
#     "package_dimensions": {"width_cm": 30, "height_cm": 15, ...},
#     "price_cents": 9999,
#     ...
#   }
# }

# You need to build:
variants_dict = {}
for variant_name, variant_data in product_data.get("variants", {}).items():
    # Build the nested objects first
    attributes = [VariantAttribute(...) for attr in variant_data["attributes"]]
    package_dimensions = PackageDimensions(...)

    # Then the variant itself
    variants_dict[variant_name] = ProductVariant(
        variant_id=variant_data["variant_id"],
        variant_name=variant_name,  # ← Key must match variant_name field!
        attributes=attributes,
        sku=variant_data["sku"],
        price_cents=variant_data["price_cents"],
        # ... more fields
    )
```

> **Hint Level 1**: Follow the 17-step algorithm above. The hardest part is steps 6-11 where you construct embedded objects. Use `.get()` with defaults for optional fields.

> **Hint Level 2**: Pay attention to `images_data` processing - find the primary image with `next((img for img in images_data if img.get("is_primary")), images_data[0] if images_data else None)`.

<details>
<summary>Hint Level 3 - Full Implementation</summary>

```python
async def create_product(self, supplier_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 1. Get supplier
        supplier = await Supplier.get(PydanticObjectId(supplier_id))
        if not supplier:
            raise ValueError("Supplier not found")

        # 2. Permission check
        await self._check_supplier_can_create(supplier)

        # 3-4. Uniqueness checks
        await self._check_name_uniqueness(product_data["name"])
        await self._check_sku_uniqueness(supplier_id, product_data["base_sku"])

        # 5. Generate slug
        slug = self._generate_slug(product_data["name"])

        # 6. Build images
        images_data = product_data.get("images", [])
        primary_img = next((img for img in images_data if img.get("is_primary")), images_data[0] if images_data else None)
        gallery_imgs = [img["url"] for img in images_data if not img.get("is_primary")]
        product_images = ProductImages(
            primary_image=primary_img["url"] if primary_img else "https://placeholder.com/default.jpg",
            gallery_images=gallery_imgs
        )

        # 7. Build metadata
        metadata = ProductMetadata(
            base_sku=product_data["base_sku"],
            barcode=product_data.get("barcode"),
            brand=product_data.get("brand"),
            manufacturer=product_data.get("manufacturer"),
            model_number=product_data.get("model_number"),
            tags=product_data.get("tags", []),
            custom_attributes=product_data.get("custom_attributes", {})
        )

        # 8. Build variants
        variants_dict = {}
        for variant_name, variant_data in product_data.get("variants", {}).items():
            attributes = [
                VariantAttribute(
                    attribute_name=attr["attribute_name"],
                    attribute_value=attr["attribute_value"]
                )
                for attr in variant_data.get("attributes", [])
            ]
            pkg_dims = variant_data["package_dimensions"]
            package_dimensions = PackageDimensions(
                width_cm=pkg_dims["width_cm"],
                height_cm=pkg_dims["height_cm"],
                depth_cm=pkg_dims["depth_cm"],
                weight_grams=pkg_dims["weight_grams"]
            )
            variants_dict[variant_name] = ProductVariant(
                variant_id=variant_data["variant_id"],
                variant_name=variant_name,
                attributes=attributes,
                sku=variant_data["sku"],
                price_cents=variant_data["price_cents"],
                cost_cents=variant_data.get("cost_cents"),
                quantity=variant_data.get("quantity", 0),
                reserved=0,
                package_dimensions=package_dimensions,
                image_url=variant_data.get("image_url"),
                is_active=True
            )

        # 9. Build stock locations
        stock_locations = [
            StockLocation(
                location_id=loc["location_id"],
                location_name=loc["location_name"],
                street_address=loc.get("street_address"),
                city=loc["city"],
                state=loc.get("state"),
                zip_code=loc["zip_code"],
                country=loc["country"],
                quantity=loc.get("quantity", 0),
                reserved=loc.get("reserved", 0)
            )
            for loc in product_data.get("stock_locations", [])
        ]

        # 10. Build topic descriptions
        topic_descriptions = [
            TopicDescription(
                topic=td["topic"],
                description=td["description"],
                display_order=td.get("display_order", 0)
            )
            for td in product_data.get("topic_descriptions", [])
        ]

        # 11. Build shipping
        shipping_data = product_data["shipping"]
        shipping = ShippingInfo(
            free_shipping=shipping_data.get("free_shipping", False),
            shipping_cost_cents=shipping_data.get("shipping_cost_cents"),
            ships_from_country=shipping_data["ships_from_country"],
            ships_to_countries=shipping_data.get("ships_to_countries", []),
            estimated_delivery_days=shipping_data.get("estimated_delivery_days")
        )

        # 12. Denormalized supplier info
        supplier_info = {
            "id": str(supplier.id),
            "name": supplier.company_info.legal_name,
            "logo": supplier.business_info.logo or ""
        }

        # 13. Construct product
        product = Product(
            supplier_id=PydanticObjectId(supplier_id),
            supplier_info=supplier_info,
            name=product_data["name"],
            slug=slug,
            short_description=product_data.get("short_description"),
            topic_descriptions=topic_descriptions,
            category=ProductCategory(product_data["category"]),
            condition=ProductCondition(product_data.get("condition", "new")),
            unit_type=UnitType(product_data.get("unit_type", "piece")),
            images=product_images,
            metadata=metadata,
            stock_locations=stock_locations,
            variants=variants_dict,
            base_price_cents=product_data["base_price_cents"],
            currency=product_data.get("currency", "USD"),
            shipping=shipping,
            status=ProductStatus.DRAFT,
            is_available=False
        )

        # 14. Insert
        await product.insert()

        # 15. Kafka event
        product_id = oid_to_str(product.id)
        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="created",
            entity_id=product_id,
            data=product.model_dump(mode="json"),
        )

        # 16. Update supplier's product array
        await self._add_product_to_supplier(supplier, product.id)

        # 17. Return summary
        return {
            "id": product_id,
            "supplier_id": str(product.supplier_id),
            "name": product.name,
            "slug": product.slug,
            "status": product.status.value,
            "is_available": product.is_available,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat()
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to create product: {str(e)}")
```
</details>

#### Verification

```javascript
// In MongoDB shell - verify the product was created correctly:
db.products.findOne({ name: "Your Product Name" })

// Check all embedded objects are present:
db.products.findOne(
  { name: "Your Product Name" },
  {
    "supplier_info": 1,
    "images": 1,
    "metadata.base_sku": 1,
    "metadata.tags": 1,
    "variants": 1,
    "stock_locations": 1,
    "shipping": 1,
    "status": 1
  }
)

// Verify supplier's product_ids was updated:
db.suppliers.findOne(
  { _id: ObjectId("your_supplier_id") },
  { product_ids: 1 }
)
```

---

### Exercise 5.3: Get Product (Ownership-Scoped)

**Concept**: Compound `find_one` query for access control (anti-enumeration)

#### The Method Signature

```python
async def get_product(self, product_id: str, supplier_id: str) -> Optional[Product]:
```

#### The Security Pattern

```python
# WRONG - Information leak:
product = await Product.get(PydanticObjectId(product_id))
if product.supplier_id != supplier_id:
    raise ValueError("Forbidden")  # ← Attacker now knows product EXISTS

# RIGHT - Anti-enumeration:
product = await Product.find_one({
    "_id": PydanticObjectId(product_id),
    "supplier_id": PydanticObjectId(supplier_id)
})
if not product:
    raise ValueError("Product not found")  # ← Same error whether it doesn't exist or wrong owner
```

> **You already used this pattern in TASK_03** for community access control. Same idea here - always return "not found" to prevent ownership enumeration.

> **Hint Level 1**: Single `find_one` with both `_id` and `supplier_id` in the query.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def get_product(self, product_id: str, supplier_id: str) -> Optional[Product]:
    try:
        product = await Product.find_one({
            "_id": PydanticObjectId(product_id),
            "supplier_id": PydanticObjectId(supplier_id)
        })
        if not product:
            raise ValueError("Product not found")
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to get product: {str(e)}")
```
</details>

---

### Exercise 5.4: List Supplier's Products (Filtered + Paginated)

**Concept**: Dynamic query building with `$in`, `$text`, cursor pagination, and `find().sort().limit().to_list()`

#### The Method Signature

```python
async def list_products(
    self,
    supplier_id: str,
    page_size: int = 20,
    cursor: Optional[str] = None,
    status_filter: Optional[List[str]] = None,
    category_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
```

#### Query Building (Dynamic Filters)

```python
# Start with the base query (always filter by supplier)
query = {"supplier_id": PydanticObjectId(supplier_id)}

# Add optional filters:
if status_filter:      query["status"] = {"$in": status_filter}
if category_filter:    query["category"] = category_filter
if search:             query["$text"] = {"$search": search}

# Cursor pagination:
if cursor:             query["_id"] = {"$gt": PydanticObjectId(cursor)}
```

#### New Operator: `$in`

```python
# $in: Match ANY value in the provided array
{"status": {"$in": ["active", "draft"]}}
# Matches products where status is "active" OR "draft"

# Compare to $all (which you'll use in Exercise 5.7):
{"metadata.tags": {"$all": ["electronics", "wireless"]}}
# Matches products that have BOTH "electronics" AND "wireless" tags
```

#### New Operator: `$text` / `$search`

```python
# Full-text search using MongoDB text index
{"$text": {"$search": "wireless headphones"}}
# Searches across all text-indexed fields
# MongoDB automatically handles word stemming, stop words, etc.
```

> **Important**: `$text` requires a text index on the collection. The Product model doesn't explicitly define one, but this is the pattern used in the service. In production, you'd add `[("name", "text"), ("short_description", "text")]` to the indexes.

#### The Fetch + Has-More Pattern

```python
# Fetch page_size + 1 to check if there are more results
products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

has_more = len(products) > page_size
if has_more:
    products = products[:-1]  # Remove the extra item

next_cursor = str(products[-1].id) if has_more and products else None
```

> **You already did this in TASK_03** with `discover_communities()`. The pattern is identical.

#### Response Building

Build a list of product summaries (not full product objects):

```python
product_list = [
    {
        "id": str(p.id),
        "name": p.name,
        "slug": p.slug,
        "status": p.status.value,
        "category": p.category.value,
        "base_price_cents": p.base_price_cents,
        "currency": p.currency,
        "primary_image": str(p.images.primary_image) if p.images else None,
        "stock_quantity": p.get_total_inventory(),  # ← Uses model helper!
        "is_available": p.is_available,
        "created_at": p.created_at,
        "updated_at": p.updated_at
    }
    for p in products
]
```

> **Hint Level 1**: Build the query dict incrementally, adding filters only when they're provided. Use `min()` to cap page_size. Apply the fetch+has-more pattern.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def list_products(
    self, supplier_id: str, page_size: int = 20, cursor: Optional[str] = None,
    status_filter: Optional[List[str]] = None, category_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    try:
        query = {"supplier_id": PydanticObjectId(supplier_id)}

        if status_filter:
            query["status"] = {"$in": status_filter}
        if category_filter:
            query["category"] = category_filter
        if search:
            query["$text"] = {"$search": search}
        if cursor:
            query["_id"] = {"$gt": PydanticObjectId(cursor)}

        page_size = min(page_size, self.max_page_size)

        products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

        has_more = len(products) > page_size
        if has_more:
            products = products[:-1]

        product_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "slug": p.slug,
                "status": p.status.value,
                "category": p.category.value,
                "base_price_cents": p.base_price_cents,
                "currency": p.currency,
                "primary_image": str(p.images.primary_image) if p.images else None,
                "stock_quantity": p.get_total_inventory(),
                "is_available": p.is_available,
                "created_at": p.created_at,
                "updated_at": p.updated_at
            }
            for p in products
        ]

        next_cursor = str(products[-1].id) if has_more and products else None

        return {
            "products": product_list,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size
            }
        }
    except Exception as e:
        raise Exception(f"Failed to list products: {str(e)}")
```
</details>

---

### Exercise 5.5: Update Product (Partial Update)

**Concept**: Get-then-modify with uniqueness validation, status gate, and auto-slug regeneration

#### The Method Signature

```python
async def update_product(
    self,
    product_id: str,
    supplier_id: str,
    updates: Dict[str, Any]
) -> Product:
```

#### Algorithm

```
1. Get product (reuse self.get_product - ownership check included)
2. Status gate: cannot update DELETED products
3. If "name" changed → check name uniqueness (exclude current product!)
4. If "name" changed → regenerate slug
5. If "base_sku" changed → check SKU uniqueness (exclude current product!)
6. Apply each update field to the product object
7. await product.save()
8. Return updated product
```

#### The `exclude_id` Pattern in Action

```python
# When CREATING: no exclude
await self._check_name_uniqueness("Cool Headphones")

# When UPDATING: exclude THIS product's ID
await self._check_name_uniqueness(updates["name"], product_id)
# ↑ Without this, updating ANY field on a product named "Cool Headphones"
#   would fail because it finds ITSELF
```

#### Partial Update Application

```python
# Only apply fields that are present in the updates dict:
if "name" in updates:
    product.name = updates["name"]
if "short_description" in updates:
    product.short_description = updates["short_description"]
if "category" in updates:
    product.category = ProductCategory(updates["category"])
if "base_price_cents" in updates:
    product.base_price_cents = updates["base_price_cents"]
if "tags" in updates:
    product.metadata.tags = updates["tags"]  # ← Note: nested field update!
```

> **Note**: The route layer already filtered out `None` values before calling us. So if `"name"` is in updates, the caller definitely wants to change it.

> **Hint Level 1**: Follow the algorithm steps. The key insight is using `product_id` as the `exclude_id` parameter for uniqueness checks.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def update_product(self, product_id: str, supplier_id: str, updates: Dict[str, Any]) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status == ProductStatus.DELETED:
            raise ValueError("Cannot update deleted product. Use restore endpoint first")

        if "name" in updates and updates["name"] != product.name:
            await self._check_name_uniqueness(updates["name"], product_id)
            product.slug = self._generate_slug(updates["name"])

        if "base_sku" in updates and updates["base_sku"] != product.metadata.base_sku:
            await self._check_sku_uniqueness(supplier_id, updates["base_sku"], product_id)

        if "name" in updates:
            product.name = updates["name"]
        if "short_description" in updates:
            product.short_description = updates["short_description"]
        if "category" in updates:
            product.category = ProductCategory(updates["category"])
        if "base_price_cents" in updates:
            product.base_price_cents = updates["base_price_cents"]
        if "tags" in updates:
            product.metadata.tags = updates["tags"]

        await product.save()
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to update product: {str(e)}")
```
</details>

---

### Exercise 5.6: Product Lifecycle - State Machine Transitions

**Concept**: Status gates, cross-collection validation, idempotent operations, and the soft-delete/restore pattern

This exercise covers 5 lifecycle methods. Each one checks the current status, validates the transition is allowed, and updates the product.

#### 5.6a: `delete_product(product_id, supplier_id)` - Soft Delete (Idempotent)

```python
# Algorithm:
# 1. Get product (ownership check)
# 2. If already DELETED → return (idempotent, don't error!)
# 3. Call product.soft_delete() (model helper handles status + deleted_at)
# 4. Emit Kafka event
```

**The Idempotent Pattern**: DELETE should always return success. If the product is already deleted, that's fine - the end state is what the caller wanted.

```python
if product.status == ProductStatus.DELETED:
    return  # ← Already deleted, success!
```

<details>
<summary>Full Implementation</summary>

```python
async def delete_product(self, product_id: str, supplier_id: str) -> None:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status == ProductStatus.DELETED:
            return  # Idempotent

        await product.soft_delete()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="deleted",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to delete product: {str(e)}")
```
</details>

---

#### 5.6b: `publish_product(product_id, supplier_id)` - Draft to Active

```python
# Algorithm:
# 1. Get product (ownership check)
# 2. Cross-collection: Get supplier, check verification status
# 3. Status gate: must be DRAFT
# 4. Validate publish requirements (images, stock, description)
# 5. Call product.publish() (model helper)
# 6. Emit Kafka event
```

**Cross-collection validation**: This is the first time you fetch a SECOND document to validate an operation on the first.

```python
supplier = await Supplier.get(PydanticObjectId(supplier_id))
if supplier.verification.verification_status.value != "verified":
    raise ValueError("Supplier must be verified to publish products")
```

> **Think about it**: Why check supplier verification on PUBLISH but not on CREATE? Because creating a draft is low-risk (no one can see it). Publishing makes it visible to all users - we need to ensure the supplier is legitimate.

<details>
<summary>Full Implementation</summary>

```python
async def publish_product(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        supplier = await Supplier.get(PydanticObjectId(supplier_id))
        if supplier.verification.verification_status.value != "verified":
            raise ValueError("Supplier must be verified to publish products")

        if product.status != ProductStatus.DRAFT:
            raise ValueError(f"Cannot publish product with status '{product.status.value}'")

        self._validate_publish_requirements(product)
        await product.publish()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="published",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
                "category": product.category.value,
                "base_price_cents": product.base_price_cents,
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to publish product: {str(e)}")
```
</details>

---

#### 5.6c: `discontinue_product(product_id, supplier_id)`

**Status gate**: Only ACTIVE or OUT_OF_STOCK can be discontinued.

```python
if product.status not in [ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]:
    raise ValueError(f"Cannot discontinue product with status '{product.status.value}'")
```

**Update**: Set status to DISCONTINUED, is_available to False, save.

<details>
<summary>Full Implementation</summary>

```python
async def discontinue_product(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status not in [ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]:
            raise ValueError(f"Cannot discontinue product with status '{product.status.value}'")

        product.status = ProductStatus.DISCONTINUED
        product.is_available = False
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="discontinued",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to discontinue product: {str(e)}")
```
</details>

---

#### 5.6d: `mark_out_of_stock(product_id, supplier_id)`

**Status gate**: Only ACTIVE can be marked out of stock.

<details>
<summary>Full Implementation</summary>

```python
async def mark_out_of_stock(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status != ProductStatus.ACTIVE:
            raise ValueError(f"Cannot mark product with status '{product.status.value}' as out of stock")

        product.status = ProductStatus.OUT_OF_STOCK
        product.is_available = False
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="out_of_stock",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to mark product out of stock: {str(e)}")
```
</details>

---

#### 5.6e: `restore_product(product_id, supplier_id)`

**Status gate**: Only DELETED can be restored. Restores to DRAFT (not back to ACTIVE!).

```python
# Why restore to DRAFT, not ACTIVE?
# Because a deleted product may have become stale:
# - Stock may be zero
# - Images may be expired
# - Supplier may no longer be verified
# Forcing through DRAFT → publish ensures re-validation
```

<details>
<summary>Full Implementation</summary>

```python
async def restore_product(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status != ProductStatus.DELETED:
            raise ValueError(f"Product is not deleted (current status: '{product.status.value}')")

        product.status = ProductStatus.DRAFT
        product.deleted_at = None
        product.is_available = False
        await product.save()

        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to restore product: {str(e)}")
```
</details>

---

### Exercise 5.7: Public Product Endpoints - Discovery with Advanced Filters

**Concept**: Multi-condition `find_one`, `$all` for tag arrays, `$gte`/`$lte` for price ranges, `$text` search, cursor pagination

These endpoints serve the **public storefront** - no supplier authentication needed.

#### 5.7a: `get_public_product(product_id)`

**What it does**: Get a product for public viewing. Only returns products that are active, available, and not deleted.

**MongoDB Pattern**: Multi-condition `find_one`

```python
product = await Product.find_one({
    "_id": PydanticObjectId(product_id),
    "status": ProductStatus.ACTIVE,     # Must be published
    "is_available": True,                # Must be purchasable
    "deleted_at": None                   # Must not be soft-deleted
})
```

> **Why three conditions instead of just checking status?** Defense in depth. Even if a bug sets `status=active` on a deleted product, the `deleted_at` check catches it. The `is_available` flag is a separate business control that can disable purchasing without changing status.

**Index used**: `[("status", 1), ("deleted_at", 1), ("is_available", 1), ("created_at", -1)]` (Index #9)

<details>
<summary>Full Implementation</summary>

```python
async def get_public_product(self, product_id: str) -> Optional[Product]:
    try:
        product = await Product.find_one({
            "_id": PydanticObjectId(product_id),
            "status": ProductStatus.ACTIVE,
            "is_available": True,
            "deleted_at": None
        })
        if not product:
            raise ValueError("Product not found")
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to get public product: {str(e)}")
```
</details>

---

#### 5.7b: `list_public_products(...)` - THE BIG ONE

**This is the most complex query in TASK_04.** You'll combine FIVE different filter types into a single dynamic query.

#### The Method Signature

```python
async def list_public_products(
    self,
    page_size: int = 20,
    cursor: Optional[str] = None,
    category_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    min_price_cents: Optional[int] = None,
    max_price_cents: Optional[int] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
```

#### Query Building - Five Filter Layers

```python
# Layer 1: Base filter (always applied)
query = {
    "status": ProductStatus.ACTIVE,
    "is_available": True,
    "deleted_at": None
}

# Layer 2: Category (optional)
if category_filter:
    query["category"] = category_filter

# Layer 3: Tags with $all (optional) ← NEW OPERATOR!
if tags_filter:
    query["metadata.tags"] = {"$all": tags_filter}

# Layer 4: Price range with $gte/$lte (optional) ← NEW OPERATORS!
if min_price_cents is not None or max_price_cents is not None:
    price_filter = {}
    if min_price_cents is not None:
        price_filter["$gte"] = min_price_cents
    if max_price_cents is not None:
        price_filter["$lte"] = max_price_cents
    query["base_price_cents"] = price_filter

# Layer 5: Full-text search (optional)
if search:
    query["$text"] = {"$search": search}

# Cursor pagination
if cursor:
    query["_id"] = {"$gt": PydanticObjectId(cursor)}
```

#### New Operator: `$all`

```python
# $all: Array field must contain ALL specified values

# Find products tagged with BOTH "electronics" AND "wireless":
{"metadata.tags": {"$all": ["electronics", "wireless"]}}

# Compare:
# $in:  at least ONE tag matches (OR logic)   → used in list_products for status
# $all: ALL tags must match (AND logic)         → used here for tag filtering

# Example:
# Product A: tags = ["electronics", "wireless", "bluetooth"]
# Product B: tags = ["electronics", "wired"]
#
# Filter: {"$all": ["electronics", "wireless"]}
# → Matches A (has both), NOT B (missing "wireless")
```

#### New Operators: `$gte` / `$lte`

```python
# Range query on numeric fields:
{"base_price_cents": {"$gte": 1000, "$lte": 5000}}
# Matches products priced between $10.00 and $50.00

# You can use one or both:
{"base_price_cents": {"$gte": 1000}}      # Min $10.00, no max
{"base_price_cents": {"$lte": 5000}}      # No min, max $50.00
{"base_price_cents": {"$gte": 1000, "$lte": 5000}}  # Both bounds
```

> **Why build the price filter as a separate dict?** Because the caller might provide only `min_price_cents`, only `max_price_cents`, or both. Building the filter dict incrementally handles all three cases cleanly.

#### Response Building

```python
# Use the model's to_public_dict() helper for serialization:
product_list = [p.to_public_dict() for p in products]
```

> **Hint Level 1**: Start with the 3-field base query. Add each optional filter with an `if` guard. Apply cursor pagination. Use the fetch+has-more pattern. Serialize with `to_public_dict()`.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def list_public_products(
    self, page_size: int = 20, cursor: Optional[str] = None,
    category_filter: Optional[str] = None, tags_filter: Optional[List[str]] = None,
    min_price_cents: Optional[int] = None, max_price_cents: Optional[int] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    try:
        query = {
            "status": ProductStatus.ACTIVE,
            "is_available": True,
            "deleted_at": None
        }

        if category_filter:
            query["category"] = category_filter

        if tags_filter:
            query["metadata.tags"] = {"$all": tags_filter}

        if min_price_cents is not None or max_price_cents is not None:
            price_filter = {}
            if min_price_cents is not None:
                price_filter["$gte"] = min_price_cents
            if max_price_cents is not None:
                price_filter["$lte"] = max_price_cents
            query["base_price_cents"] = price_filter

        if search:
            query["$text"] = {"$search": search}

        if cursor:
            query["_id"] = {"$gt": PydanticObjectId(cursor)}

        page_size = min(page_size, self.max_page_size)

        products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

        has_more = len(products) > page_size
        if has_more:
            products = products[:-1]

        product_list = [p.to_public_dict() for p in products]
        next_cursor = str(products[-1].id) if has_more and products else None

        return {
            "products": product_list,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more
            }
        }
    except Exception as e:
        raise Exception(f"Failed to list public products: {str(e)}")
```
</details>

#### Verification

```javascript
// Test the public listing with various filters:

// 1. All active products
db.products.find({ status: "active", is_available: true, deleted_at: null }).count()

// 2. Category filter
db.products.find({ status: "active", is_available: true, deleted_at: null, category: "electronics" })

// 3. Tag filter with $all
db.products.find({ status: "active", "metadata.tags": { $all: ["wireless", "bluetooth"] } })

// 4. Price range
db.products.find({ status: "active", base_price_cents: { $gte: 1000, $lte: 5000 } })

// 5. Combined (category + price + tags)
db.products.find({
  status: "active",
  is_available: true,
  deleted_at: null,
  category: "electronics",
  "metadata.tags": { $all: ["wireless"] },
  base_price_cents: { $gte: 2000, $lte: 10000 }
})
```

---

## 6. VERIFICATION CHECKLIST

After implementing all methods, verify each one works:

| # | Method | Test |
|---|--------|------|
| 1 | `_generate_slug` | `"Premium Headphones (2024)"` → `"premium-headphones-2024"` |
| 2 | `create_product` | Create a product with 2 variants, 1 stock location, 2 tags |
| 3 | `get_product` | Get it back with the correct supplier_id |
| 4 | `get_product` (wrong supplier) | Should return "Product not found" |
| 5 | `list_products` | List all supplier products, verify pagination works |
| 6 | `list_products` with status filter | Filter by `["draft"]` - should only show drafts |
| 7 | `update_product` | Change the name, verify slug auto-updates |
| 8 | `update_product` (duplicate name) | Should fail with "already exists" |
| 9 | `publish_product` | Draft → Active (supplier must be verified) |
| 10 | `mark_out_of_stock` | Active → Out of Stock |
| 11 | `discontinue_product` | Active or OOS → Discontinued |
| 12 | `delete_product` | Any → Deleted (soft) |
| 13 | `delete_product` (already deleted) | Should succeed silently (idempotent) |
| 14 | `restore_product` | Deleted → Draft (not Active!) |
| 15 | `get_public_product` | Only returns active + available products |
| 16 | `list_public_products` | Test with category, tags ($all), price range ($gte/$lte) |

---

## 7. ADVANCED CHALLENGES

These are optional exercises for students who want to go deeper.

### Challenge 1: The Dict Field Index Puzzle

The Product model has this index:
```python
[("variants.sku", 1)]  # Index #7
```

**Question**: MongoDB stores variants as a Dict (map), not a list. How does MongoDB index dict values? Can you use `variants.sku` in a query even though variants is a dict with dynamic keys like `"Red-Large"`, `"Blue-Small"`?

**Experiment**: Run these in the MongoDB shell:
```javascript
// Does this work?
db.products.find({"variants.sku": "SHOE-RED-L"})

// What about this?
db.products.find({"variants.Red-Large.sku": "SHOE-RED-L"})

// Explain both:
db.products.find({"variants.sku": "SHOE-RED-L"}).explain("executionStats")
```

**Insight**: MongoDB can index through dict values, but it works differently than array indexing. `variants.sku` matches the `sku` field of ANY value in the variants dict. This is similar to how multikey indexes work on arrays, but applied to map values.

---

### Challenge 2: The $all vs $in Index Usage

Consider these two queries:
```javascript
// Query A: $in
db.products.find({"metadata.tags": {"$in": ["electronics", "wireless"]}})

// Query B: $all
db.products.find({"metadata.tags": {"$all": ["electronics", "wireless"]}})
```

Both use the multikey index `[("metadata.tags", 1), ("status", 1)]`.

**Questions**:
1. Which query returns more results? Why?
2. Run `.explain("executionStats")` on both. Which examines more documents?
3. Can MongoDB use the index for `$all`? How does it optimize it?

**Insight**: MongoDB optimizes `$all` by using the index to find documents matching the FIRST element, then post-filters for the remaining elements. So `{"$all": ["electronics", "wireless"]}` first uses the index to find all docs with "electronics", then filters those results for "wireless". This means the order of elements in `$all` matters for performance - put the most selective tag first.

---

### Challenge 3: Price Range vs Variant Prices

The current `list_public_products` filters on `base_price_cents`. But products have **variants with different prices**.

**Scenario**: A product has `base_price_cents: 5000` ($50) but a variant "Premium Gold" with `price_cents: 15000` ($150).

**Question**: If a user searches for products $100-$200, this product WON'T appear (base price is $50), even though a variant costs $150. How would you fix this?

**Think about**:
1. Adding `min_variant_price` and `max_variant_price` denormalized fields to the Product document
2. Updating these fields whenever variants are added/modified
3. Querying these denormalized fields instead of `base_price_cents`
4. What index would you need?

**Bonus**: Could you solve this WITHOUT denormalization using an aggregation pipeline with `$unwind` on the variants? What are the trade-offs?

---

## 8. WHAT'S NEXT

Congratulations! You've built the **product catalog** - the most structurally complex service so far.

**Concepts you mastered**:
- `Dict` (Map) field construction and querying
- `$all` operator for AND-logic on arrays
- `$gte` / `$lte` for numeric range queries
- `$text` / `$search` for full-text search
- Cross-collection validation (supplier verification)
- `$addToSet` for idempotent array updates
- 5-state lifecycle machine with guarded transitions
- Complex embedded document construction (8 types)
- Denormalized data (supplier_info snapshot)
- Public vs. supplier-scoped query patterns

**What comes next**:

**TASK_05: Post Service** - The social content layer. Posts live inside communities and reference products. You'll build:
- Feed generation with cursor pagination
- Engagement operations (like/unlike, save/unsave)
- Content distribution across communities
- Rich media attachment handling
- Comment threading

Posts bring together Users, Communities, and Products into the social feed - the heart of the platform.
