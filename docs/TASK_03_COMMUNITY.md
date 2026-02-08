# TASK 03: Community Service

## 1. MISSION BRIEFING

Communities are where the **social** meets the **commerce**. A leader (celebrity/influencer) creates a community, curates content, and promotes products. Consumers join communities to discover content and products from leaders they follow.

This is the **first relationship-heavy entity** you'll implement. Communities reference Users (owner, members), and later tasks will reference communities (Posts, Promotions). Everything connects through communities.

### What You Will Build
The `CommunityService` class - 23 methods covering CRUD, membership, discovery with multi-filter pagination, access control, and admin moderation operations.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Cursor-based (keyset) pagination** | `discover_communities()`, `list_suspended_communities()`, `get_moderation_log()` |
| **`$in` operator** | Filtering communities by tags |
| **`$ne` operator** | Slug uniqueness check excluding current doc |
| **`$or` with compound sort** | Cursor pagination tiebreaker pattern |
| **`$gt` / `$lt` on dates** | Featured communities with expiration |
| **`find().sort().limit().to_list()`** | The Beanie query chain pattern |
| **Multi-filter query building** | Dynamic filter construction |
| **Denormalized data writes** | Storing owner snapshot from User into Community |
| **Array membership operations** | `member_ids` with add/remove via model helpers |
| **Optimistic locking** | Version checking before updates |
| **Cross-collection writes** | Moderation log in separate collection |
| **Idempotent operations** | Join/leave returning success regardless |
| **Access control patterns** | Anti-enumeration for private/suspended communities |

### How This Differs From TASK_01 & TASK_02

| Aspect | Auth Tasks (01/02) | Community (03) |
|--------|-------------------|---------------|
| Query complexity | Single `find_one` | Multi-filter `find` with pagination |
| Write pattern | Insert new doc | Insert + partial update + version lock |
| Relationships | Self-contained | References User, stores denormalized owner |
| Pagination | None | **Cursor-based keyset pagination** |
| Access control | Public endpoints | Private/suspended visibility rules |
| Collections touched | 1 per method | 2 (communities + moderation_logs) |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Community creation requires a User with `role=leader`
- Have at least one leader user registered and verified from TASK_01

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/community.py` | The data model - 11 indexes, 20+ helper methods |
| 2 | `shared/models/community_moderation_log.py` | Separate collection for audit trail |
| 3 | `apps/backend-service/src/schemas/community.py` | 30+ request/response schemas |
| 4 | `apps/backend-service/src/routes/community.py` | 15 endpoints calling your service |
| 5 | `apps/backend-service/src/utils/community_utils.py` | `encode_cursor`, `decode_cursor`, response builders |

### The Data Flow

```
HTTP Request
    │
    ▼
┌─────────┐   Extracts user_id, role, admin status    ┌───────────────┐
│  Route   │ ─────────────────────────────────────────▶│ community_utils│
│          │   from headers (X-User-ID, X-User-Role)   └───────────────┘
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────────────┐
│              CommunityService (YOU WRITE THIS)        │
│                                                      │
│  Touches TWO collections:                            │
│  ├── communities (main CRUD + membership)            │
│  └── community_moderation_logs (admin audit trail)   │
│                                                      │
│  Also reads from:                                    │
│  └── users (to validate owner exists, build owner)   │
└──────────────────────────────────────────────────────┘
    │                          │
    ▼                          ▼
┌──────────┐          ┌──────────────────┐
│communities│          │community_        │
│collection │          │moderation_logs   │
└──────────┘          └──────────────────┘
```

---

## 3. MODEL DEEP DIVE

### The Community Document (abbreviated)

```json
{
  "_id": ObjectId("..."),
  "name": "Tech Innovators Hub",
  "slug": "tech-innovators-hub",
  "description": "A community for tech enthusiasts...",
  "tagline": "Where innovation meets community",
  "purpose": {
    "mission_statement": "Connect tech innovators worldwide",
    "goals": ["Share knowledge", "Collaborate on projects"],
    "target_audience": "Tech professionals and enthusiasts"
  },
  "business_address": { "country": "US", "city": "San Francisco", "zip_code": "94105" },
  "owner": {
    "user_id": ObjectId("..."),
    "display_name": "Famous Leader",
    "avatar": "https://...",
    "is_verified": true,
    "business_email": "leader@example.com"
  },
  "member_ids": [ObjectId("..."), ObjectId("..."), ObjectId("...")],
  "category": "tech",
  "tags": ["innovation", "startups", "ai"],
  "branding": { "cover_image": "https://...", "logo": "...", "primary_color": "#FF5733" },
  "settings": {
    "visibility": "public",
    "requires_approval": false,
    "allow_member_posts": false,
    "moderate_posts": true,
    "max_members": null,
    "min_age": null,
    "allowed_countries": [],
    "blocked_countries": []
  },
  "rules": [{"rule_title": "Be respectful", "rule_description": "...", "display_order": 0}],
  "links": { "website": "https://...", "instagram": "techhub", "twitter": "techhub" },
  "stats": {
    "member_count": 3,
    "active_member_count": 0,
    "post_count": 0,
    "promotion_count": 0,
    "total_likes": 0,
    "total_comments": 0,
    "total_shares": 0,
    "last_post_at": null,
    "last_active_at": null
  },
  "status": "active",
  "deleted_at": null,
  "is_featured": false,
  "featured_until": null,
  "is_verified": false,
  "verified_at": null,
  "version": 1,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Key Design Decision: Denormalized Owner

The `owner` field stores a **snapshot** of the User's data at creation time:
```python
owner: CommunityOwner = {
    user_id: ObjectId("...")    # Reference to User (for lookups)
    display_name: "Famous Leader"  # COPY of user.profile.display_name
    avatar: "https://..."          # COPY of user.profile.avatar
    is_verified: true              # COPY of user.contact_info.email_verified
    business_email: "leader@..."   # COPY of user.contact_info.primary_email
}
```

**Why denormalize?** Every time someone views a community, they see the owner's name and avatar. Without denormalization, you'd need a `$lookup` (join) to the users collection for every community query. With denormalization, the data is already there - zero joins, maximum read speed.

**The trade-off:** If the user changes their display name, the community still shows the old name until explicitly refreshed. This is an acceptable trade-off for read performance.

### Key Design Decision: member_ids Array

Members are stored as an **array of ObjectIds** directly in the community document:
```python
member_ids: [ObjectId("aaa"), ObjectId("bbb"), ObjectId("ccc")]
```

This enables:
- Fast membership checks: `ObjectId("aaa") in community.member_ids` → O(n) in Python
- No joins needed to check membership
- The `member_ids` index allows: "find all communities where user X is a member"

**Scalability warning** (line 276 of model): For communities > 10K members, this array approach becomes problematic (document size, update contention). Production systems would use a separate `community_memberships` collection. This is noted in the model.

### Index Analysis (11 indexes!)

| Index | Fields | Used By |
|-------|--------|---------|
| **Slug** | `slug` | `get_community_by_slug()`, `_check_slug_unique()` |
| **Owner lookup** | `owner.user_id` + `status` + `created_at` desc | Not in this task |
| **Discovery (visibility)** | `status` + `settings.visibility` + `stats.member_count` desc | `discover_communities()` |
| **Discovery (category)** | `category` + `status` + `stats.member_count` desc | `discover_communities()` |
| **Location** | `business_address.country` + `city` + `status` | `discover_communities()` |
| **Featured** | `is_featured` + `featured_until` | `discover_communities()` |
| **Tags** | `tags` + `status` | `discover_communities()` |
| **Member lookup** | `member_ids` | "Find communities for user X" (not in this task) |
| **Active sort** | `stats.last_active_at` desc + `status` | Not in this task |
| **Soft delete** | `deleted_at` | Implicit in most queries |
| **Verified** | `is_verified` + `status` | `discover_communities()` |

> **The tags index is a multikey index.** When MongoDB indexes an array field, it creates an index entry for EACH element in the array. So a community with `tags: ["ai", "startups", "tech"]` gets 3 index entries. This is why `{"tags": {"$in": ["ai"]}}` is fast.

---

## 4. THE SERVICE CONTRACT

### 23 Methods Organized by Section

**Helpers (5):**
| Method | MongoDB Op | Purpose |
|--------|-----------|---------|
| `_get_user(user_id)` | `User.get()` | Validate user exists and not deleted |
| `_get_community(community_id)` | `Community.get()` | Validate community exists and not deleted |
| `_get_community_for_user(community_id, user_id, is_admin)` | Calls `_get_community` | Access control: private/suspended visibility |
| `_validate_version(community, expected)` | None (Python) | Optimistic locking check |
| `_check_slug_unique(slug, exclude_id)` | `Community.find_one()` | Slug uniqueness with `$ne` exclusion |
| `_build_owner(user)` | None (Python) | Build denormalized CommunityOwner from User |

**CRUD (7):**
| Method | MongoDB Op | Returns |
|--------|-----------|---------|
| `create_community(user_id, user_role, data)` | `insert()` | `Community` |
| `get_community_by_id(community_id, user_id, is_admin)` | `get()` | `Community` |
| `get_community_by_slug(slug, user_id, is_admin)` | `find_one()` | `Community` |
| `discover_communities(filters..., cursor, limit)` | `find().sort().limit()` | `Tuple[List, bool]` |
| `update_community(community_id, user_id, version, **updates)` | `save()` | `Community` |
| `delete_community(community_id, user_id, version)` | `soft_delete()` | `Community` |
| `archive_community(...)` / `unarchive_community(...)` | `save()` | `Community` |

**Membership (5):**
| Method | MongoDB Op | Returns |
|--------|-----------|---------|
| `join_community(community_id, user_id)` | model `add_member()` → `save()` | `Dict` |
| `leave_community(community_id, user_id)` | model `remove_member()` → `save()` | `Dict` |
| `check_membership(community_id, user_id)` | `get()` + Python check | `Dict` |
| `list_members(community_id, user_id, cursor, limit)` | Array slice | `Tuple` |
| `remove_member(community_id, actor_id, member_id, version)` | model `remove_member()` | `Community` |

**Admin (8):**
| Method | MongoDB Op | Returns |
|--------|-----------|---------|
| `suspend_community(...)` | model `suspend_community()` + `log_moderation_action()` | `Community` |
| `unsuspend_community(...)` | `save()` + `log_moderation_action()` | `Community` |
| `verify_community(...)` | model `verify_community()` + log | `Community` |
| `unverify_community(...)` | `save()` + log | `Community` |
| `feature_community(...)` | model `feature_community()` + log | `Community` |
| `unfeature_community(...)` | model `unfeature_community()` + log | `Community` |
| `list_suspended_communities(cursor, limit)` | `find().sort().limit()` | `Tuple[List, bool]` |
| `get_moderation_log(community_id, cursor, limit)` | `CommunityModerationLog.find()...` | `Tuple[List, bool]` |

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Helper Methods - The Foundation Layer

**Concepts:** `Document.get()` by ID, `find_one` with `$ne`, denormalized snapshot construction
**Difficulty:** Easy-Medium
**Why this matters:** Every other method in this service calls these helpers. Get them right and everything else flows naturally.

#### Implement 6 helper methods:

**5.1.1 - `_get_user(self, user_id: str) -> User`**

Requirements:
- Convert `user_id` to `PydanticObjectId` (wrap in try/except → `ValueError("Invalid user ID")`)
- `User.get(PydanticObjectId(user_id))`
- If not found or `user.deleted_at` is set → `ValueError("User not found")`
- Return the user

**5.1.2 - `_get_community(self, community_id: str) -> Community`**

Same pattern as `_get_user` but for Community:
- Convert, get, check `deleted_at` → `ValueError("Community not found")`

**5.1.3 - `_get_community_for_user(self, community_id, user_id, is_admin=False) -> Community`**

This is the **access control** method. It prevents non-members from discovering private communities and non-admins from seeing suspended ones.

Requirements:
1. Call `self._get_community(community_id)` to get the community
2. If `status == DELETED`: only admin can see → raise `ValueError("Community not found")` for non-admin
3. If `status == SUSPENDED`: only admin or owner can see → raise for others
4. If `visibility == PRIVATE`: only admin, owner, or member can see → raise for others

> **Anti-enumeration:** We always say "Community not found" (never "you don't have access"). This prevents attackers from discovering that private communities exist.

**5.1.4 - `_validate_version(self, community, expected_version) -> None`**

Compare `community.version` to `expected_version`. If different:
```python
raise ValueError(f"Version conflict - expected {expected_version}, got {community.version}")
```

**5.1.5 - `_check_slug_unique(self, slug, exclude_id=None) -> None`** *(NEW CONCEPT: `$ne`)*

Check if a slug is already taken, optionally excluding a specific community (for updates).

```python
query = {"slug": slug.lower()}
if exclude_id:
    query["_id"] = {"$ne": exclude_id}  # Exclude current community from check

existing = await Community.find_one(query)
if existing:
    raise ValueError("Slug already exists")
```

> **Why `$ne`?** When updating a community's slug, we need to check uniqueness but exclude the community itself. Without `$ne`, the community would always "find itself" and think the slug is taken.

**5.1.6 - `_build_owner(self, user: User) -> CommunityOwner`**

Build a **denormalized snapshot** of the user:
```python
CommunityOwner(
    user_id=user.id,
    display_name=user.profile.display_name or user.contact_info.primary_email.split("@")[0],
    avatar=user.profile.avatar or "https://example.com/default-avatar.png",
    is_verified=user.contact_info.email_verified,
    business_email=user.contact_info.primary_email
)
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

These are all short methods. `_get_user` and `_get_community` follow the same pattern: try converting to ObjectId, call `.get()`, check for None or deleted_at. `_get_community_for_user` adds layered access checks. `_check_slug_unique` is a `find_one` with an optional `$ne` filter.

</details>

<details>
<summary><b>Hint Level 2</b> - _get_community_for_user pattern</summary>

```python
async def _get_community_for_user(self, community_id, user_id, is_admin=False):
    community = await self._get_community(community_id)

    if community.status == CommunityStatus.DELETED:
        if not is_admin:
            raise ValueError("Community not found")
        return community

    if community.status == CommunityStatus.SUSPENDED:
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Community not found")
        return community

    if community.settings.visibility == CommunityVisibility.PRIVATE:
        user_oid = PydanticObjectId(user_id)
        if not is_admin and not community.is_user_owner(user_oid) and not community.is_user_member(user_oid):
            raise ValueError("Community not found")

    return community
```

</details>

---

### Exercise 5.2: Create Community - Denormalized Writes

**Concept:** Building a complex document with denormalized data from another collection + `insert()`
**Difficulty:** Medium
**What's new:** You read from the `users` collection to build the `owner` snapshot, then write to `communities`. This is the first cross-collection data flow (read from one, write to another).

#### Implement: `create_community(self, user_id, user_role, data) -> Community`

**Business Rules:**
1. Verify `user_role == "leader"` → `ValueError("Only leaders can create communities")`
2. Get user via `self._get_user(user_id)`
3. Check slug uniqueness: `self._check_slug_unique(data["slug"])`
4. Validate category: `CommunityCategory(data["category"])` (catch ValueError)
5. Build settings from `data.get("settings") or {}`
6. Build rules list from `data.get("rules")`
7. Build links from `data.get("links")`
8. Construct the Community document with:
   - `owner=self._build_owner(user)` ← denormalized snapshot
   - `member_ids=[user.id]` ← owner is first member
   - `stats=CommunityStats(member_count=1)` ← owner counts
9. `await community.insert()`
10. Emit Kafka event: topic=`Topic.COMMUNITY`, action=`"created"`
11. Return the community

**The key insight:** The `data` parameter is a `dict` from `request_data.model_dump()`. You extract nested dicts from it to build embedded models.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The `data` dict has keys matching the schema: `name`, `slug`, `description`, `tagline`, `category`, `tags`, `purpose`, `business_address`, `branding`, `settings`, `rules`, `links`. Extract each and build the corresponding embedded model. Settings, rules, and links are optional.

</details>

<details>
<summary><b>Hint Level 2</b> - Building settings and rules</summary>

```python
# Settings (with defaults)
settings_data = data.get("settings") or {}
visibility = CommunityVisibility(settings_data.get("visibility", "public"))
settings = CommunitySettings(
    visibility=visibility,
    requires_approval=settings_data.get("requires_approval", False),
    allow_member_posts=settings_data.get("allow_member_posts", False),
    moderate_posts=settings_data.get("moderate_posts", True),
    max_members=settings_data.get("max_members"),
    min_age=settings_data.get("min_age"),
    allowed_countries=settings_data.get("allowed_countries") or [],
    blocked_countries=settings_data.get("blocked_countries") or []
)

# Rules
rules = []
if data.get("rules"):
    rules = [
        CommunityRules(
            rule_title=r["rule_title"],
            rule_description=r["rule_description"],
            display_order=r.get("display_order", i)
        )
        for i, r in enumerate(data["rules"])
    ]
```

</details>

#### Verify Exercise 5.2

```bash
curl -X POST http://localhost:8000/communities \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <leader-user-id-from-task-01>" \
  -H "X-User-Role: leader" \
  -d '{
    "name": "Tech Innovators Hub",
    "slug": "tech-innovators-hub",
    "description": "A community for tech enthusiasts to share ideas and discover innovative products.",
    "tagline": "Where innovation meets community",
    "category": "tech",
    "tags": ["innovation", "startups", "ai"],
    "purpose": {
      "mission_statement": "Connect tech innovators worldwide and foster collaboration",
      "goals": ["Share knowledge", "Collaborate on projects"],
      "target_audience": "Tech professionals and enthusiasts"
    },
    "business_address": {
      "country": "US",
      "city": "San Francisco",
      "zip_code": "94105"
    },
    "branding": {
      "cover_image": "https://cdn.example.com/covers/tech-hub.jpg",
      "primary_color": "#FF5733"
    },
    "rules": [
      {"rule_title": "Be respectful", "rule_description": "Treat all members with respect"},
      {"rule_title": "No spam", "rule_description": "No promotional spam allowed"}
    ]
  }'
```

**Verify in MongoDB:**
```javascript
db.communities.findOne({"slug": "tech-innovators-hub"})
// Check: owner.user_id matches your leader user
// Check: member_ids has exactly 1 entry (the owner)
// Check: stats.member_count is 1
```

---

### Exercise 5.3: Get Community - By ID, By Slug, With Access Control

**Concept:** `find_one` by slug + layered access control
**Difficulty:** Easy-Medium

#### Implement 2 methods:

**5.3.1 - `get_community_by_id(self, community_id, user_id, is_admin=False) -> Community`**

Simply delegates to the access-controlled helper:
```python
return await self._get_community_for_user(community_id, user_id, is_admin)
```

**5.3.2 - `get_community_by_slug(self, slug, user_id, is_admin=False) -> Community`**

Requirements:
1. `Community.find_one({"slug": slug.lower(), "deleted_at": None})`
2. If not found → `ValueError("Community not found")`
3. Pass through access control: `self._get_community_for_user(str(community.id), user_id, is_admin)`

> **Why two lookups?** First we find by slug (field query), then we apply access control via `_get_community_for_user` which uses the ID. This separates concerns: slug resolution vs access enforcement.

#### Verify

```bash
# By ID:
curl -X POST http://localhost:8000/communities/get \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <your-user-id>" \
  -d '{"community_id": "<community-id-from-exercise-5.2>"}'

# By slug:
curl -X POST http://localhost:8000/communities/get-by-slug \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <your-user-id>" \
  -d '{"slug": "tech-innovators-hub"}'
```

---

### Exercise 5.4: Discover Communities - Multi-Filter Cursor Pagination

**Concept:** Dynamic query building + `$in` operator + cursor-based keyset pagination with `$or` tiebreaker
**Difficulty:** HIGH - This is the most important exercise in TASK_03
**What's new:** Everything about pagination. This is the first time you build a production-quality paginated query.

#### Implement: `discover_communities(self, user_id, is_admin, category, tags, country, city, is_featured, is_verified, cursor, limit) -> Tuple[List[Community], bool]`

This method has **4 phases**:

#### Phase 1: Build the base query
```python
query = {
    "status": CommunityStatus.ACTIVE.value,
    "deleted_at": None
}

# Non-admins only see public communities
if not is_admin:
    query["settings.visibility"] = CommunityVisibility.PUBLIC.value
```

#### Phase 2: Apply optional filters
Each filter is additive (AND logic):

```python
if category:
    query["category"] = category

if tags:
    query["tags"] = {"$in": [t.lower() for t in tags]}  # Match ANY tag

if country:
    query["business_address.country"] = country.upper()

if city:
    query["business_address.city"] = city

if is_featured is True:
    query["is_featured"] = True
    query["featured_until"] = {"$gt": utc_now()}  # Not expired

if is_verified is True:
    query["is_verified"] = True
```

> **`$in` on arrays:** When `tags` is an array field and you query `{"tags": {"$in": ["ai", "tech"]}}`, MongoDB matches documents where the `tags` array contains at least ONE of the specified values. This uses the multikey index on `tags`.

#### Phase 3: Cursor pagination (THE HARD PART)

Cursor-based pagination (also called keyset pagination) is fundamentally different from offset pagination (`skip/limit`):

**Offset:** `db.find().skip(100).limit(20)` → Must count through 100 documents to skip them. O(skip + limit).
**Keyset:** `db.find({sort_field: {$lt: last_value}}).limit(20)` → Jumps directly to the right spot via index. O(limit).

The cursor encodes the **last seen sort value + document ID**:
```python
if cursor:
    cursor_data = decode_cursor(cursor)  # {"sort_value": "42", "id": "507f..."}
    query["$or"] = [
        # Either: member_count is LESS than the last seen value
        {"stats.member_count": {"$lt": int(cursor_data["sort_value"])}},
        # OR: same member_count but ID is less (tiebreaker)
        {
            "stats.member_count": int(cursor_data["sort_value"]),
            "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
        }
    ]
```

> **Why the `$or` tiebreaker?** Imagine 50 communities all have `member_count: 100`. If we only filter by `member_count < 100`, we'd skip all 50 at once. The `_id` tiebreaker ensures we paginate through communities with the same member_count one by one.

#### Phase 4: Execute the query
```python
limit = min(limit, self.max_page_size)  # Cap at 100

communities = await Community.find(query).sort(
    [("stats.member_count", -1), ("_id", -1)]  # Most members first, then by _id
).limit(limit + 1).to_list()  # Fetch one extra to check has_more

has_more = len(communities) > limit
if has_more:
    communities = communities[:limit]  # Trim the extra

return communities, has_more
```

> **The `limit + 1` trick:** We fetch one more than requested. If we get `limit + 1` results, there are more pages. We trim the extra before returning. This avoids a separate count query.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Build the query dict step by step. Start empty with just base filters, add each optional filter, add cursor if present, then execute with sort+limit. The `decode_cursor` function from `community_utils` returns a dict with `sort_value` and `id` keys.

</details>

<details>
<summary><b>Hint Level 2</b> - The complete query chain</summary>

```python
# Execute (Beanie chain pattern)
communities = await Community.find(query).sort(
    [("stats.member_count", -1), ("_id", -1)]
).limit(limit + 1).to_list()
```

This chains: `find(filter)` → `sort(fields)` → `limit(n)` → `to_list()` (executes and returns Python list)

</details>

<details>
<summary><b>Hint Level 3</b> - Complete cursor pagination block</summary>

```python
if cursor:
    cursor_data = decode_cursor(cursor)
    query["$or"] = [
        {"stats.member_count": {"$lt": int(cursor_data["sort_value"])}},
        {
            "stats.member_count": int(cursor_data["sort_value"]),
            "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
        }
    ]
```

</details>

#### Verify Exercise 5.4

First, create 3+ communities with different categories:
```bash
# Create a second community (different category)
curl -X POST http://localhost:8000/communities \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <leader-id>" \
  -H "X-User-Role: leader" \
  -d '{
    "name": "Fashion Forward",
    "slug": "fashion-forward",
    "description": "The latest trends in fashion, curated by top influencers.",
    "category": "fashion",
    "tags": ["style", "trends"],
    "purpose": {"mission_statement": "Make fashion accessible to everyone worldwide"},
    "business_address": {"country": "US", "city": "New York", "zip_code": "10001"},
    "branding": {"cover_image": "https://cdn.example.com/covers/fashion.jpg"}
  }'
```

Then test discovery:
```bash
# Discover all
curl -X POST http://localhost:8000/communities/discover \
  -H "X-User-ID: <any-user-id>" \
  -d '{"limit": 10}'

# Filter by category
curl -X POST http://localhost:8000/communities/discover \
  -H "X-User-ID: <any-user-id>" \
  -d '{"category": "tech", "limit": 10}'

# Filter by tags
curl -X POST http://localhost:8000/communities/discover \
  -H "X-User-ID: <any-user-id>" \
  -d '{"tags": ["ai"], "limit": 10}'

# Pagination: use next_cursor from first response
curl -X POST http://localhost:8000/communities/discover \
  -H "X-User-ID: <any-user-id>" \
  -d '{"limit": 1, "cursor": "<next_cursor-from-above>"}'
```

---

### Exercise 5.5: Update Community - Partial Updates with Optimistic Locking

**Concept:** Optimistic locking pattern + partial field application + slug uniqueness with `$ne`
**Difficulty:** Medium-High

#### Implement: `update_community(self, community_id, user_id, expected_version, is_admin=False, **updates) -> Community`

**Business Rules:**
1. Get community: `self._get_community(community_id)`
2. If `status == DELETED` → `ValueError("Community not found")`
3. If `status == SUSPENDED` and not admin → `ValueError("Community is suspended")`
4. If not admin and not owner → `ValueError("Not authorized to update this community")`
5. Validate version: `self._validate_version(community, expected_version)`
6. If `slug` changed: check uniqueness with `_check_slug_unique(new_slug, community.id)` ← uses `$ne`
7. Apply each field from `**updates` if present and not None
8. Increment version, update timestamp, save

**The partial update pattern:** Check each possible field from `updates`:
```python
if "name" in updates and updates["name"]:
    community.name = updates["name"]

if "description" in updates and updates["description"]:
    community.description = updates["description"]

if "tagline" in updates:  # tagline can be None (clearing it)
    community.tagline = updates["tagline"]
```

For nested objects (purpose, branding, settings), rebuild the entire embedded object merging old + new values:
```python
if "purpose" in updates and updates["purpose"]:
    p = updates["purpose"]
    community.purpose = CommunityPurpose(
        mission_statement=p.get("mission_statement", community.purpose.mission_statement),
        goals=p.get("goals", community.purpose.goals),
        target_audience=p.get("target_audience", community.purpose.target_audience)
    )
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

There are ~10 optional fields to check. For simple fields (name, description, tags), directly assign. For embedded objects (purpose, branding, settings), merge old values with new ones. End with `community.version += 1` and `await community.save()`.

</details>

#### Verify

```bash
curl -X POST http://localhost:8000/communities/update \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <owner-user-id>" \
  -d '{
    "community_id": "<community-id>",
    "expected_version": 1,
    "tagline": "Updated tagline!",
    "tags": ["innovation", "startups", "ai", "ml"]
  }'
```

**Test version conflict:**
```bash
# Send the same version again (should be 2 now):
curl -X POST http://localhost:8000/communities/update \
  -H "X-User-ID: <owner-id>" \
  -d '{"community_id": "<id>", "expected_version": 1, "name": "New Name"}'
# → 409 Version conflict
```

---

### Exercise 5.6: Delete, Archive, Unarchive - Status Transitions

**Concept:** State machine transitions + soft delete + optimistic locking
**Difficulty:** Easy-Medium

#### Implement 3 methods:

**5.6.1 - `delete_community(...)` → soft delete**
1. Get community, check not already deleted, check ownership/admin, validate version
2. Call `await community.soft_delete()` (model helper)

**5.6.2 - `archive_community(...)` → ACTIVE → ARCHIVED**
1. Get community, check status is ACTIVE, check ownership/admin, validate version
2. Call `await community.archive_community()`

**5.6.3 - `unarchive_community(...)` → ARCHIVED → ACTIVE**
1. Get community, check status is ARCHIVED, check ownership/admin, validate version
2. Set `status = ACTIVE`, increment version, save

**State machine:**
```
ACTIVE ──▶ ARCHIVED ──▶ ACTIVE (reversible)
ACTIVE ──▶ SUSPENDED ──▶ ACTIVE (admin only, Exercise 5.9)
Any ──────▶ DELETED (soft delete, irreversible)
```

---

### Exercise 5.7: Join & Leave - Idempotent Membership

**Concept:** Idempotent operations + array manipulation via model helpers
**Difficulty:** Medium
**What's new:** Idempotent design - calling "join" twice doesn't error, calling "leave" when not a member doesn't error.

#### Implement 3 methods:

**5.7.1 - `join_community(self, community_id, user_id) -> Dict`**

1. Get community, convert user_id to `PydanticObjectId`
2. Check suspended → `ValueError("Community is suspended...")`
3. Check not active → `ValueError("Community is not accepting new members")`
4. **Idempotent:** If already a member, return success with `already_member: True`
5. Check capacity: `community.can_accept_members()` → `ValueError("Community has reached maximum capacity")`
6. Call `await community.add_member(user_oid)` (model helper)
7. Emit Kafka event: `"member_joined"`
8. Return with `already_member: False`

**5.7.2 - `leave_community(self, community_id, user_id) -> Dict`**

1. Get community, convert user_id
2. If owner → `ValueError("Owner cannot leave the community...")`
3. **Idempotent:** If not a member, return success with `was_member: False`
4. Call `await community.remove_member(user_oid)`
5. Emit Kafka event: `"member_left"`
6. Return with `was_member: True`

**5.7.3 - `check_membership(self, community_id, user_id) -> Dict`**

Simply get community and return `is_member` and `is_owner` using model helpers.

> **Why idempotent?** Network requests can retry. If a user's "join" request times out and they retry, the second request should succeed (not error with "already a member"). Same for leave.

#### Verify

```bash
# Join (as a different user than the owner)
curl -X POST http://localhost:8000/communities/join \
  -H "X-User-ID: <consumer-user-id>" \
  -d '{"community_id": "<community-id>"}'

# Join again (idempotent - should return already_member: true)
curl -X POST http://localhost:8000/communities/join \
  -H "X-User-ID: <consumer-user-id>" \
  -d '{"community_id": "<community-id>"}'

# Check membership
curl -X POST http://localhost:8000/communities/check-membership \
  -H "X-User-ID: <consumer-user-id>" \
  -d '{"community_id": "<community-id>"}'

# Leave
curl -X POST http://localhost:8000/communities/leave \
  -H "X-User-ID: <consumer-user-id>" \
  -d '{"community_id": "<community-id>"}'
```

**Verify in MongoDB:**
```javascript
db.communities.findOne({"slug": "tech-innovators-hub"}, {"member_ids": 1, "stats.member_count": 1})
// After join: member_ids should have 2 entries, member_count: 2
// After leave: member_ids back to 1, member_count: 1
```

---

### Exercise 5.8: List Members & Remove Member

**Concept:** Array-based pagination + ownership authorization
**Difficulty:** Medium

#### Implement 2 methods:

**5.8.1 - `list_members(self, community_id, user_id, is_admin, cursor, limit) -> Tuple[List[PydanticObjectId], int, bool]`**

This uses a different pagination strategy - **array slicing** (since members are stored in the document):

1. Get community with access control: `_get_community_for_user()`
2. Decode cursor to get offset (cursor `sort_value` is the offset)
3. Slice the array: `community.member_ids[offset:offset + limit + 1]`
4. Check `has_more` with the `limit + 1` trick
5. Return `(members, community.stats.member_count, has_more)`

**5.8.2 - `remove_member(self, community_id, user_id, member_user_id, expected_version, is_admin) -> Community`**

1. Get community, check ownership/admin authorization
2. Validate version
3. Cannot remove the owner → `ValueError("Cannot remove the community owner")`
4. If not a member → `ValueError("User is not a member of this community")`
5. Call `community.remove_member(member_oid)`

---

### Exercise 5.9: Admin Operations - Moderation with Audit Trail

**Concept:** Writing to a separate collection (`community_moderation_logs`) + status transitions + time-based features
**Difficulty:** Medium
**What's new:** Every admin action creates a log entry in a separate collection using `log_moderation_action()`.

#### Implement 6 methods:

**5.9.1 - `suspend_community(self, community_id, admin_id, reason, expected_version)`**
1. Get community, check status is ACTIVE, validate version
2. Save `previous_status`
3. Call `await community.suspend_community()` (model helper)
4. Emit Kafka event: `"suspended"`
5. Log: `await log_moderation_action(community.id, ModerationAction.SUSPEND, PydanticObjectId(admin_id), reason, previous_status, community.status.value)`

**5.9.2 - `unsuspend_community(...)` → SUSPENDED → ACTIVE**
Same pattern but: check status is SUSPENDED, set status to ACTIVE manually, save, log.

**5.9.3 - `verify_community(self, community_id, admin_id)`**
1. Check not already verified
2. Call `await community.verify_community()` (model helper)
3. Emit Kafka + log

**5.9.4 - `unverify_community(self, community_id, admin_id)`**
1. Check is verified
2. Set `is_verified = False`, `verified_at = None`, increment version, save
3. Log

**5.9.5 - `feature_community(self, community_id, admin_id, duration_days=7)`**
1. Check status is ACTIVE
2. Call `await community.feature_community(duration_days)` (model helper sets `featured_until`)
3. Log with metadata: `{"duration_days": duration_days, "featured_until": community.featured_until.isoformat()}`

**5.9.6 - `unfeature_community(self, community_id, admin_id)`**
1. Check is featured
2. Call `await community.unfeature_community()`
3. Log

> **Import required:** `from shared.models.community_moderation_log import CommunityModerationLog, ModerationAction, log_moderation_action`

---

### Exercise 5.10: List Suspended + Moderation Log - Cursor Pagination Redux

**Concept:** Applying the cursor pagination pattern to different collections and sort fields
**Difficulty:** Medium
**What's reinforced:** Same `$or` tiebreaker pattern from Exercise 5.4, but with different sort fields.

#### Implement 2 methods:

**5.10.1 - `list_suspended_communities(self, cursor, limit) -> Tuple[List[Community], bool]`**

Same pattern as `discover_communities` but:
- Base query: `{"status": CommunityStatus.SUSPENDED.value}`
- Sort by: `updated_at` desc (most recently suspended first) + `_id` desc
- Cursor tiebreaker uses `datetime.fromisoformat(cursor_data["sort_value"])`

```python
if cursor:
    cursor_data = decode_cursor(cursor)
    query["$or"] = [
        {"updated_at": {"$lt": datetime.fromisoformat(cursor_data["sort_value"])}},
        {
            "updated_at": datetime.fromisoformat(cursor_data["sort_value"]),
            "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
        }
    ]
```

**5.10.2 - `get_moderation_log(self, community_id, cursor, limit) -> Tuple[List[CommunityModerationLog], bool]`**

Query the **separate** `community_moderation_logs` collection:
- Base query: `{"community_id": PydanticObjectId(community_id)}`
- Sort by: `created_at` desc + `_id` desc
- Same cursor tiebreaker pattern
- Uses `CommunityModerationLog.find(...)` (different model class!)

---

## 6. VERIFICATION CHECKLIST

### Functional Checks
- [ ] **Create** - leader creates community, owner auto-added as member
- [ ] **Create** - non-leader rejected with 403
- [ ] **Slug uniqueness** - duplicate slug rejected
- [ ] **Get by ID** - returns full community
- [ ] **Get by slug** - returns same community
- [ ] **Private visibility** - non-member gets "not found" (anti-enumeration)
- [ ] **Discover** - returns only active, public communities
- [ ] **Discover + category** - filters correctly
- [ ] **Discover + tags** - `$in` matches communities with any matching tag
- [ ] **Discover + pagination** - cursor returns next page correctly
- [ ] **Update** - partial fields applied, version incremented
- [ ] **Update version conflict** - wrong version returns 409
- [ ] **Update slug** - `$ne` exclusion allows changing to same slug, rejects duplicates
- [ ] **Delete** - soft delete sets `deleted_at` and `status=deleted`
- [ ] **Archive/Unarchive** - status transitions work correctly
- [ ] **Join** - adds to member_ids, increments member_count
- [ ] **Join idempotent** - second join returns `already_member: true`
- [ ] **Leave** - removes from member_ids, decrements member_count
- [ ] **Leave idempotent** - leaving when not member returns `was_member: false`
- [ ] **Owner cannot leave** - returns error
- [ ] **Remove member** - owner/admin can remove, version checked
- [ ] **Suspend/Unsuspend** - admin can change status, moderation log created
- [ ] **Verify/Unverify** - toggles `is_verified`, moderation log created
- [ ] **Feature/Unfeature** - sets `featured_until` with duration, log created
- [ ] **List suspended** - cursor pagination works
- [ ] **Moderation log** - entries exist for each admin action

### Database Checks
- [ ] `db.communities.getIndexes()` - all 11 indexes present
- [ ] `db.community_moderation_logs.getIndexes()` - all 4 indexes present
- [ ] Owner field has denormalized data matching the user
- [ ] `member_ids` array grows/shrinks with join/leave
- [ ] `stats.member_count` stays in sync with `member_ids.length`

---

## 7. ADVANCED CHALLENGES

### Challenge A: Cursor Pagination Deep Dive

With 5+ communities created, test pagination with `limit: 2`:
```bash
# Page 1
curl -X POST http://localhost:8000/communities/discover \
  -d '{"limit": 2}'

# Page 2 (use next_cursor from page 1)
curl -X POST http://localhost:8000/communities/discover \
  -d '{"limit": 2, "cursor": "<cursor>"}'
```

Manually decode the cursor:
```python
import base64, json
cursor = "<next_cursor-value>"
decoded = json.loads(base64.urlsafe_b64decode(cursor + "=="))
print(decoded)  # {"sort_value": "1", "id": "507f..."}
```

Now explain: why does the cursor encode `sort_value` AND `id`? What happens if you only encode `sort_value`?

### Challenge B: Multikey Index Behavior

```javascript
// How many index entries for this community?
db.communities.findOne({"slug": "tech-innovators-hub"}, {"tags": 1, "member_ids": 1})
// If tags has 3 elements → 3 entries in the tags index
// If member_ids has 5 elements → 5 entries in the member_ids index
```

What's the maximum document size in MongoDB? (16MB). If each ObjectId in `member_ids` is 12 bytes, what's the theoretical maximum members before hitting the document size limit? How does this relate to the model's warning at line 276?

### Challenge C: Stale Denormalized Data

The owner's `display_name` is snapshotted at community creation. If the user later changes their display name, the community still shows the old name.

Design a solution: how would you keep the denormalized `owner` data fresh? Consider:
1. Update on every community query (expensive)
2. Background job that syncs periodically
3. Event-driven: when user updates profile, emit event → consumer updates all their communities
4. Accept staleness (current approach)

Which approach fits this platform best and why?

---

## 8. WHAT'S NEXT

You've mastered the first relationship-heavy service. You now understand:
- **Cursor-based keyset pagination** - the production-grade pagination pattern
- **`$in` on arrays** with multikey indexes
- **`$ne` for exclusion** in uniqueness checks
- **Denormalized writes** - snapshot data from one collection into another
- **Idempotent operations** - safe to retry without side effects
- **Multi-collection writes** - community + moderation log
- **Access control** - anti-enumeration patterns
- **Optimistic locking** - version conflict detection

**TASK 04: Product Service** will introduce:
- Dict/Map field queries (product variants)
- `$text` search on name/description
- Inventory math (quantity - reserved = available)
- Price range queries (`$gte` / `$lte`)
- Cross-collection validation (supplier must be verified to publish)
- Slug auto-generation from product name
