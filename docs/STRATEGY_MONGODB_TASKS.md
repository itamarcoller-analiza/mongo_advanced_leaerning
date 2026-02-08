# MongoDB Advanced Learning - Task Strategy

## Philosophy & Core Idea

Students receive a **fully scaffolded Social Commerce Platform** with:
- **Models** (complete) - The data structures and indexes
- **Schemas** (complete) - The request/response contracts
- **Routes** (complete) - The HTTP endpoints that call services
- **Services** (EMPTY SHELLS) - **This is what students implement**

Each service file will be stripped down to **method signatures only** with docstrings explaining what the method should do. Students write every MongoDB query from scratch, guided by per-domain MD files.

> **The student never touches models, schemas, or routes. They ONLY write service-layer MongoDB queries.**

---

## How The MDs Work

### Each MD = One Domain (Model + Route pair)

```
docs/
├── STRATEGY_MONGODB_TASKS.md          ← This file (meta-strategy)
├── TASK_00_SETUP.md                   ← Environment setup + architecture primer
├── TASK_01_USER.md                    ← User authentication service
├── TASK_02_SUPPLIER.md                ← Supplier authentication service
├── TASK_03_COMMUNITY.md               ← Community management service
├── TASK_04_PRODUCT.md                 ← Product catalog service
├── TASK_05_POST.md                    ← Social content service
├── TASK_06_PROMOTION.md               ← Promotion workflow service
├── TASK_07_ORDER.md                   ← Order processing service
└── TASK_08_ANALYTICS.md               ← Cross-domain aggregation pipelines
```

### Strict Ordering - Each MD Unlocks The Next

```
TASK_01 (User)
   └─→ TASK_02 (Supplier)       ← Same patterns, harder model
         └─→ TASK_03 (Community) ← Introduces relationships to User
               ├─→ TASK_04 (Product)    ← References Supplier
               │     └─→ TASK_06 (Promotion) ← References Product + Community
               └─→ TASK_05 (Post)       ← References User + Community
                     └─→ TASK_07 (Order) ← References User + Product + Promotion
                           └─→ TASK_08 (Analytics) ← Aggregates everything
```

Students MUST complete earlier tasks before later ones because:
- Later services CALL earlier services (e.g., Order calls Product to validate stock)
- MongoDB concepts build incrementally
- Test data from earlier tasks feeds into later ones

---

## MD Template (Every MD follows this structure)

```markdown
# TASK_XX: [Domain Name] Service Implementation

## 1. MISSION BRIEFING
- What this entity does in the business
- Why it matters to the platform
- What the student will learn (MongoDB concepts)

## 2. BEFORE YOU START
- Prerequisites (which previous tasks must be complete)
- Files to read before coding:
  - Model file (understand the data)
  - Schema file (understand inputs/outputs)
  - Route file (understand how your service gets called)

## 3. MODEL DEEP DIVE
- Annotated walkthrough of the model
- Field-by-field explanation of WHY each field exists
- Index analysis: what queries are optimized
- Helper methods: what the model already gives you

## 4. THE SERVICE CONTRACT
- Every method signature with:
  - Input parameters (mapped to schema)
  - Expected return type
  - Business rules to enforce
  - Error conditions to handle

## 5. IMPLEMENTATION EXERCISES (ordered by difficulty)

### Exercise 5.1: [Name] - [MongoDB Concept]
**Concept:** What MongoDB operation this teaches
**Implement:** Which method(s) to write
**Requirements:**
  - Step-by-step business logic
  - Exact query patterns to use
  - Error handling expectations
**Hints:**
  - Beanie ODM syntax examples
  - Index usage reminders
**Verify:** curl command + expected response

### Exercise 5.2: [Name] - [MongoDB Concept]
...

## 6. VERIFICATION CHECKLIST
- [ ] All methods implemented
- [ ] All error cases handled
- [ ] Queries use appropriate indexes
- [ ] Optimistic locking enforced where needed
- [ ] Soft delete pattern followed

## 7. ADVANCED CHALLENGES (optional)
- Performance optimization tasks
- Aggregation pipeline exercises
- Edge case handling
```

---

## MongoDB Concept Progression Map

Each task introduces NEW MongoDB concepts while reinforcing previous ones.

### TASK_01: User Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| `find_one` with field match | `is_email_available()` | Basic document lookup by field |
| `insert` | `register_consumer()` | Document creation with Beanie |
| Nested field query | `login()` | Query `{"contact_info.primary_email": email}` |
| `$set` via `.save()` | `verify_email()` | Update specific fields |
| `$inc` pattern | `record_failed_login()` | Atomic increment |
| Compound query | `login()` lock check | `status + locked_until` |
| Unique index awareness | `register_*()` | Handle duplicate key errors |

**Reinforced:** None (this is the foundation)

---

### TASK_02: Supplier Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Array field query | `is_email_available()` | Query `additional_emails` array |
| Deeply nested documents | `register_supplier()` | Build complex nested structures |
| `$elemMatch` | Email lookup in arrays | Match elements within arrays |
| Dual token strategy | `login()` | Access + refresh token pattern |
| Document submission workflow | `submit_documents()` | Array append with validation |

**Reinforced:** find_one, insert, save, nested fields, password hashing

---

### TASK_03: Community Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| `$addToSet` | `join_community()` | Add to array without duplicates |
| `$pull` | `leave_community()` | Remove from array |
| Cursor-based pagination | `discover_communities()` | Keyset pagination with `$or` + `_id` tiebreaker |
| Denormalized writes | `create_community()` | Store owner info snapshot |
| Slug lookup | `get_by_slug()` | Unique text-based identifiers |
| Multi-filter queries | `discover_communities()` | Combine category + tags + country + featured |
| `$in` operator | Various | Match against list of values |
| Idempotent operations | `join/leave` | Handle duplicate calls gracefully |
| Optimistic locking | `update_community()` | Version field check before update |

**Reinforced:** find_one, find, insert, save, nested docs

---

### TASK_04: Product Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Dict/Map field queries | Variant operations | Query inside `variants` dict |
| `$text` search | `list_public_products()` | Full-text search on name/description |
| Complex nested structures | `create_product()` | Variants + stock locations + images |
| Inventory math | `reserve_inventory()` | `quantity - reserved = available` |
| Price range queries | `list_public_products()` | `$gte` / `$lte` on cents fields |
| Slug generation | `create_product()` | Programmatic unique slug creation |
| Cross-collection validation | `publish_product()` | Check supplier is verified |
| Status state transitions | lifecycle methods | DRAFT → ACTIVE → DISCONTINUED |

**Reinforced:** Cursor pagination, $addToSet (supplier.product_ids), soft delete, optimistic locking

---

### TASK_05: Post Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Multi-sort cursor pagination | `list_community_posts()` | Sort by `published_at` + `_id` tiebreaker |
| Cross-collection writes | `create_community_post()` | Update community.post_count |
| Access control queries | `_get_post_for_user()` | Different access for author vs member vs public |
| Array of embedded docs | Media attachments | Store complex media objects |
| Enum-based filtering | `list_community_posts()` | Filter by post_type, status |
| Pin limit enforcement | `pin_post()` | Count pinned posts (max 3), then update |
| Global distribution workflow | `request/approve/reject` | Multi-step approval state |
| Change request pattern | `create_change_request()` | Separate collection for proposed changes |

**Reinforced:** Cursor pagination, denormalized data, optimistic locking, soft delete

---

### TASK_06: Promotion Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Immutable snapshots | `_build_product_snapshot()` | Capture product state at creation time |
| Date range queries | `get_global_feed()` | `start_date <= now <= end_date` |
| Dynamic field paths | `approve/reject` | `f"approval.community_approvals.{id}.status"` |
| Complex state machine | All lifecycle methods | 8-state promotion lifecycle |
| Multi-scope approval | `approve_promotion()` | Global vs per-community approval |
| Conflict detection | `_check_product_active_promotion()` | Ensure no duplicate active promos per product |
| Offset pagination | `list_promotions()` | `.skip()` + `.limit()` pattern |
| Rejection history | `reject_promotion()` | Append to rejection array |
| `first_activated_at` immutability | `approve_promotion()` | Set once, never update |

**Reinforced:** Cross-collection validation, nested docs, status transitions, snapshots

---

### TASK_07: Order Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Idempotency key | `create_order()` | Prevent duplicate orders with unique key |
| Multi-step atomic flow | `complete_order()` | Reserve inventory → authorize payment → confirm |
| Rollback pattern | `complete_order()` | Release inventory if payment fails |
| Immutable product snapshots | `_build_product_snapshot()` | Freeze product data at purchase time |
| Order number generation | `_generate_order_number()` | Human-readable unique IDs |
| Timeline append | All status changes | `$push` to timeline array |
| Price drift detection | `create_order()` | Compare current vs expected price (5% threshold) |
| Cross-entity coordination | `complete_order()` | Touch User, Product, Promotion, Order |
| Inventory reservation | `complete_order()` | Atomic `reserved += quantity` on variants |
| Inventory release | `cancel_order()` | Atomic `reserved -= quantity` on variants |

**Reinforced:** Everything from previous tasks

---

### TASK_08: Analytics & Aggregation Pipelines
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| `$match` + `$group` | Revenue by supplier | Basic aggregation pipeline |
| `$unwind` | Products per promotion | Flatten arrays for grouping |
| `$lookup` | Order details with products | Left outer join across collections |
| `$facet` | Dashboard stats | Multiple aggregations in one query |
| `$bucket` | Price distribution | Range-based grouping |
| `$dateToString` | Daily revenue | Date-based aggregation |
| `$sortByCount` | Top categories | Frequency analysis |
| `$project` + `$addFields` | Computed fields | Transform output shapes |
| Pipeline optimization | All exercises | Filter early, project late |

**Reinforced:** Everything (this task is the capstone)

---

## Service Preparation Strategy

### What To Strip From Services Before Student Gets Them

For each service file, we create a **student version** that contains:

```python
class CommunityService:
    """
    Service layer for community management.
    Handles CRUD, membership, moderation, and discovery.
    """

    # ──────────────────────────────────────────────
    # HELPER METHODS
    # ──────────────────────────────────────────────

    @staticmethod
    async def _get_user(user_id: str) -> User:
        """
        Fetch a user by ID. Raise ValueError if not found or not active.

        MongoDB Concept: find_one by _id
        Error: "User not found" if None or status != ACTIVE
        """
        # TODO: Implement this method
        pass

    # ──────────────────────────────────────────────
    # EXERCISE 5.1: CREATE COMMUNITY
    # ──────────────────────────────────────────────

    @staticmethod
    async def create_community(
        user_id: str,
        data: CreateCommunityRequest,
    ) -> Community:
        """
        Create a new community owned by a leader.

        Business Rules:
        1. User must exist and be active
        2. User must be a LEADER role
        3. User must not exceed max_communities_owned
        4. Slug must be unique across all non-deleted communities
        5. Build denormalized owner snapshot from user data

        MongoDB Operations:
        - Find user by ID
        - Check slug uniqueness (find_one with slug + deleted_at filter)
        - Insert new community document
        - Increment user.communities_owned

        Returns: The created Community document
        Errors: ValueError with descriptive messages
        """
        # TODO: Implement this method
        pass
```

### What STAYS in the student version:
- Class definition
- All method signatures with full type hints
- Comprehensive docstrings explaining:
  - Business rules
  - MongoDB operations needed
  - Error conditions
  - Return types
- Import statements
- Constants (JWT_SECRET, etc.)
- Utility function signatures (hash_password, etc.)

### What gets REMOVED:
- All method bodies (replaced with `pass`)
- Implementation logic
- Query construction
- Error handling implementation

---

## How Students Use The MDs

### Workflow Per Task

```
1. READ the MD
   ├── Understand the domain
   ├── Read the model file (shared/models/X.py)
   ├── Read the schema file (schemas/X.py)
   └── Read the route file (routes/X.py)

2. IMPLEMENT exercises in order
   ├── Exercise 5.1 (easiest)
   ├── Exercise 5.2
   ├── ...
   └── Exercise 5.N (hardest)

3. VERIFY each exercise
   ├── Run the provided curl commands
   ├── Check responses match expected output
   └── Verify database state via MongoDB shell

4. COMPLETE the verification checklist

5. (Optional) ATTEMPT advanced challenges

6. MOVE to next task MD
```

### AI Assistant Integration

Each MD is designed so that an AI assistant can:
1. **Reference it** when helping the student
2. **Check student work** against the requirements
3. **Give hints** without giving away the answer (hint levels in each exercise)
4. **Validate** that the student used the correct MongoDB patterns
5. **Explain WHY** a pattern is used (each exercise links concept to real-world need)

The AI assistant should:
- Ask the student to read the model/schema/route FIRST before coding
- Guide through exercises IN ORDER (don't skip ahead)
- Encourage the student to try before revealing hints
- Verify each exercise works before moving to the next
- Point out when a query doesn't use indexes efficiently

---

## Difficulty Curve

```
Difficulty
    │
    │                                          ┌─ TASK_08 (Aggregation)
    │                                     ┌────┘
    │                                ┌────┘ TASK_07 (Orders/Transactions)
    │                           ┌────┘
    │                      ┌────┘ TASK_06 (Promotions/State Machines)
    │                 ┌────┘
    │            ┌────┘ TASK_05 (Posts/Feeds)
    │       ┌────┘
    │  ┌────┘ TASK_04 (Products/Variants)
    │──┘ TASK_03 (Communities/Arrays)
    │ TASK_02 (Supplier/Nested Docs)
    │ TASK_01 (User/CRUD Basics)
    └─────────────────────────────────────────── Time
```

### Per-Task Breakdown (approximate exercises per MD):
| Task | Exercises | Est. Effort | Key Challenge |
|------|-----------|-------------|---------------|
| 01 - User | 6 | Low | First time writing Beanie queries |
| 02 - Supplier | 6 | Low-Med | Deeper nesting, stricter validation |
| 03 - Community | 10 | Medium | Array ops, cursor pagination |
| 04 - Product | 8 | Medium | Variants, text search, inventory |
| 05 - Post | 10 | Medium-High | Feed generation, moderation workflow |
| 06 - Promotion | 12 | High | State machine, multi-scope approval |
| 07 - Order | 8 | High | Transactions, rollback, idempotency |
| 08 - Analytics | 8 | Very High | Pure aggregation pipelines |

---

## Exercise Design Principles

### 1. Every Exercise Has ONE Primary MongoDB Concept
Don't mix concepts. If the exercise is about `$addToSet`, that's the focus.

### 2. Every Exercise Has Real Business Context
Not "insert a document" but "Register a consumer who wants to buy handmade jewelry from their favorite influencer's community."

### 3. Three Hint Levels Per Exercise
- **Hint 1:** Direction (e.g., "Use Beanie's find_one with a filter dict")
- **Hint 2:** Pattern (e.g., "The filter should match on nested field contact_info.primary_email")
- **Hint 3:** Near-solution (e.g., "await User.find_one({'contact_info.primary_email': email, 'deleted_at': None})")

### 4. Verification Is Concrete
Every exercise ends with a curl command and expected JSON response that proves it works.

### 5. Error Cases Are Explicit
Each exercise lists error scenarios the student must handle (not discover on their own).

---

## Testing & Seed Data Strategy

### TASK_00 (Setup MD) Includes:
1. Docker compose up (MongoDB + app)
2. Seed script that creates:
   - 3 Users (2 consumers, 1 leader)
   - 2 Suppliers (1 verified, 1 pending)
   - Test data IDs are FIXED (deterministic) so curl commands work
3. MongoDB shell access instructions
4. How to check indexes: `db.collection.getIndexes()`
5. How to inspect documents: `db.collection.findOne()`

### Each subsequent task MD provides:
- Additional seed data specific to that domain
- curl commands using IDs from seed data + previous tasks

---

## File Delivery Plan

### Phase 1: Prepare Student Codebase
1. Create `student/` branch or directory
2. Strip all service implementations → method stubs with docstrings
3. Keep models, schemas, routes intact
4. Add seed data scripts

### Phase 2: Create MDs (in order)
1. `TASK_00_SETUP.md` - Environment + architecture primer
2. `TASK_01_USER.md` - User/Auth service
3. `TASK_02_SUPPLIER.md` - Supplier auth service
4. `TASK_03_COMMUNITY.md` - Community service
5. `TASK_04_PRODUCT.md` - Product service
6. `TASK_05_POST.md` - Post service
7. `TASK_06_PROMOTION.md` - Promotion service
8. `TASK_07_ORDER.md` - Order service
9. `TASK_08_ANALYTICS.md` - Aggregation pipeline exercises

### Phase 3: Create Solution Branch
- Full implementations as reference
- Students never see this unless instructor reveals it

---

## Success Criteria

A student who completes all 8 tasks will be able to:

1. **Write efficient MongoDB queries** using Beanie ODM
2. **Design compound indexes** and understand query optimization
3. **Implement cursor-based pagination** for production-scale datasets
4. **Handle concurrent updates** with optimistic locking
5. **Build multi-step workflows** (approval, state machines)
6. **Implement transactional patterns** (reservation + rollback)
7. **Write aggregation pipelines** for analytics and reporting
8. **Apply soft-delete patterns** consistently
9. **Build denormalized read models** for performance
10. **Handle edge cases** (idempotency, race conditions, data integrity)
