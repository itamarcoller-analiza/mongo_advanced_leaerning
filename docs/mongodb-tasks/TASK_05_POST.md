# TASK 05: Post Service - Social Content & Feed Operations

## 1. MISSION BRIEFING

Posts are the **social heartbeat** of the platform. They are the content that fills community feeds and the global timeline. Every post lives inside a community (or on the global feed), is authored by a user, and can carry text, images, videos, links, or polls. Posts can be liked, shared, saved, commented on, pinned, hidden, and promoted to global visibility.

This is the **most complex service** you've built so far. The Post service touches **3 collections** (posts, users, communities) plus a 4th collection (post_change_requests) for the change request workflow. You'll build a **home feed** that combines community posts with globally-distributed posts using `$or` + `$and` composition - the most complex query pattern in the course.

### What You Will Build
The `PostService` class - ~25 methods covering community post CRUD, home feed generation, global distribution workflow, change request system, moderation (hide/unhide/pin/unpin), and admin operations.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **`$or` + `$and` composition** | Home feed: community posts OR globally-distributed, combined with cursor pagination |
| **`$in` with ObjectId arrays** | Home feed: posts from user's communities |
| **Cursor pagination with `$or` tiebreaker** | 6 different paginated endpoints using `published_at`/`_id` |
| **Base64-encoded cursors** | Using `encode_cursor`/`decode_cursor` utilities |
| **Nested field queries** | `global_distribution.status`, `author.user_id` |
| **`.count()` for limits** | Max pinned posts per community |
| **Multi-collection operations** | Posts + PostChangeRequests (4th collection!) |
| **Cross-collection reads** | User lookup, Community membership/leadership checks |
| **Denormalized author data** | `PostAuthor` snapshot from User into Post |
| **Optimistic locking** | Version validation before every mutation |
| **Complex access control** | 3-tier: author vs. community leader vs. admin |
| **Anti-enumeration** | Always "Post not found" regardless of reason |
| **State machine** | Post lifecycle (draft/published/hidden/deleted) + Global distribution (none/pending/approved/rejected/revoked) |

### How This Differs From Previous Tasks

| Aspect | Product (04) | Post (05) |
|--------|-------------|-----------|
| Collections touched | 2 (products + suppliers) | **4** (posts + users + communities + change_requests) |
| Query complexity | Dynamic filters | **`$or` + `$and` + cursor in single query** |
| Cursor pagination | Simple `_id` cursor | **`published_at` + `_id` tiebreaker with base64** |
| Access control | Supplier ownership only | **3-tier**: author / leader / admin |
| State machines | 1 (product lifecycle) | **2** (post lifecycle + global distribution) |
| Write to other collections | `$addToSet` on supplier | **Full CRUD on PostChangeRequests** |
| Permissions | Simple ownership check | Draft: author only. Published: leader/admin. Global: admin only |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Posts require an author (User)
- **TASK_03 (Community) must be complete** - Posts live inside communities
- Have at least one community with a leader and a member from previous tasks
- Familiarity with cursor pagination `$or` tiebreaker from TASK_03

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/post.py` | 650 lines - 7 embedded types, 12 indexes, 2 state machines, engagement counters |
| 2 | `shared/models/post_change_request.py` | 166 lines - Separate collection for change request workflow |
| 3 | `apps/backend-service/src/schemas/post.py` | 376 lines - 20+ request schemas, 15+ response schemas |
| 4 | `apps/backend-service/src/routes/post.py` | 667 lines - 12 user-facing endpoints |
| 5 | `apps/backend-service/src/routes/admin.py` | Admin endpoints for distribution approval + change requests |
| 6 | `apps/backend-service/src/utils/post_utils.py` | `encode_cursor`, `decode_cursor`, response builders |

### The Data Flow

```
HTTP Request (User JWT)
    │
    ▼
┌──────────┐   Extracts user_id from X-User-ID header
│  Route    │   Extracts is_admin from X-Is-Admin header
│           │
│  Calls    │
│  your     │
│  service  │
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│              PostService (YOU WRITE THIS)                  │
│                                                            │
│  Reads from THREE collections:                             │
│  ├── posts (main CRUD + feeds)                             │
│  ├── users (author validation + denormalization)           │
│  └── communities (membership + leadership checks)          │
│                                                            │
│  Writes to TWO collections:                                │
│  ├── posts (insert, update, status changes)                │
│  └── post_change_requests (create, approve, reject)        │
│                                                            │
│  Emits Kafka events:                                       │
│  └── Topic.POST → created, deleted, hidden,                │
│       global_distribution_approved                         │
└──────────────────────────────────────────────────────────┘
```

### The Two State Machines

#### Post Lifecycle

```
┌───────┐  publish()   ┌───────────┐  hide_post()  ┌────────┐
│ DRAFT │─────────────▶│ PUBLISHED │──────────────▶│ HIDDEN │
└───────┘              └─────┬─────┘               └───┬────┘
    │                        │                         │
    │ soft_delete()          │ soft_delete()            │ unhide_post()
    │                        │                         │
    ▼                        ▼                         ▼
┌─────────┐           ┌─────────┐               ┌───────────┐
│ DELETED │           │ DELETED │               │ PUBLISHED │
└─────────┘           └─────────┘               └───────────┘
```

#### Global Distribution

```
┌──────┐  request_global_   ┌─────────┐  approve()   ┌──────────┐
│ NONE │──distribution()───▶│ PENDING │─────────────▶│ APPROVED │
└──────┘                    └────┬────┘              └────┬─────┘
    ▲                            │                        │
    │                     reject()                  revoke()
    │                            │                        │
    │                            ▼                        ▼
    │                     ┌──────────┐             ┌─────────┐
    │                     │ REJECTED │             │ REVOKED │
    │                     └──────────┘             └─────────┘
    │                            │                        │
    └────────────────────────────┘                        │
         can re-request                                   │
    └─────────────────────────────────────────────────────┘
         can re-request
```

---

## 3. MODEL DEEP DIVE

### Embedded Document Hierarchy (7 types)

```
Post (Document)
│
├── author: PostAuthor                       ← Denormalized from User
│   └── user_id, display_name, avatar, author_type, is_verified
│
├── media: List[MediaAttachment]             ← Images, videos, GIFs
│   └── media_type, media_url, thumbnail_url, width, height, duration_seconds
│
├── link_preview: Optional[LinkPreview]      ← Shared link metadata
│   └── url, title, description, image, site_name
│
├── poll: Optional[PollData]                 ← Only for poll-type posts
│   └── question, options: List[PollOption], allows_multiple_votes, ends_at
│       └── PollOption: option_id, option_text, vote_count
│
├── mentions: List[PostMentions]             ← @mentioned users
│   └── user_id, display_name
│
├── stats: PostStats                         ← Engagement counters
│   └── view_count, like_count, comment_count, share_count, save_count, engagement_rate
│
├── global_distribution: GlobalDistribution  ← Global visibility state machine
│   └── requested, status, requested_at, reviewed_at, reviewed_by, rejection_reason, ...
│
├── community_id / community_name            ← Denormalized community reference
├── tags: List[str]                          ← Hashtags
├── is_pinned / pinned_at / pinned_by        ← Pin state
├── hidden_at / hidden_by / hidden_reason    ← Moderation state
└── status / version / timestamps             ← Lifecycle + optimistic locking
```

### Index Analysis (12 indexes)

```python
indexes = [
    # Index 1: Author's posts
    [("author.user_id", 1), ("status", 1), ("created_at", -1)],
    # → Querying into denormalized embedded doc!

    # Index 2: Community posts (your main feed query)
    [("community_id", 1), ("status", 1), ("published_at", -1)],
    # → Used by: list_community_posts()

    # Index 3: Global posts (community_id is null)
    [("community_id", 1), ("status", 1), ("created_at", -1)],

    # Index 4: Published posts timeline
    [("status", 1), ("published_at", -1)],

    # Index 5: Tags (multikey)
    [("tags", 1), ("status", 1)],

    # Index 6: Mentions (multikey)
    [("mentions.user_id", 1)],
    # → Querying into embedded doc array!

    # Index 7-8: Popular posts
    [("stats.like_count", -1), ("status", 1)],
    [("stats.engagement_rate", -1), ("status", 1)],

    # Index 9: Pinned posts per community
    [("community_id", 1), ("is_pinned", 1), ("status", 1)],
    # → Used by: pin_post() count query

    # Index 10: Soft delete
    [("deleted_at", 1)],

    # Index 11-12: Global distribution
    [("global_distribution.status", 1), ("status", 1), ("published_at", -1)],
    [("global_distribution.status", 1), ("global_distribution.requested_at", 1)],
    # → Used by: get_home_feed() + get_pending_distribution_posts()
]
```

### PostChangeRequest Collection (Second Model)

```
PostChangeRequest (Document)
│
├── post_id: PydanticObjectId          ← Reference to the post
├── author_id: PydanticObjectId        ← Who submitted the request
├── requested_changes: Dict[str, Any]  ← Field → new value mapping
├── reason: str                        ← Why the change is needed
├── status: ChangeRequestStatus        ← pending / approved / rejected
├── original_values: Dict[str, Any]    ← Captured before applying (rollback data)
├── reviewed_at / reviewed_by / review_notes
├── applied_at                         ← When changes were applied to the post
└── created_at / updated_at
```

Allowed change fields: `text_content`, `media`, `link_preview`, `tags`
Not allowed (require new post): `post_type`, `poll`

### Key Model Helper Methods

| Method | What It Does | When You'll Use It |
|--------|-------------|-------------------|
| `is_published()` | status == PUBLISHED and deleted_at is None | Access control |
| `is_in_community()` | community_id is not None | Pin validation |
| `can_be_edited_by(user_id)` | Author check | Update permission |
| `can_be_deleted_by(user_id, is_leader)` | Author or leader | Delete permission |
| `publish()` | DRAFT → PUBLISHED + set published_at | `publish_post()` |
| `hide_post(actor_id, reason)` | PUBLISHED → HIDDEN | `hide_post()` |
| `unhide_post()` | HIDDEN → PUBLISHED | `unhide_post()` |
| `soft_delete()` | Sets deleted_at + DELETED | `delete_post()` |
| `pin_post(actor_id)` / `unpin_post()` | Pin/unpin in community | Moderation |
| `is_globally_tagged()` | Status is PENDING or APPROVED | Edit guard |
| `is_globally_distributed()` | Status is APPROVED | Home feed query |
| `can_request_global_distribution()` | Published + in community + status allows | Request guard |
| `request_global_distribution()` | Sets status to PENDING | Distribution request |
| `approve/reject/revoke_global_distribution()` | Admin operations | Distribution workflow |

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/backend-service/src/services/post.py`

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_get_user(user_id)` | `User.get()` + deleted check | Easy |
| 2 | `_get_community(community_id)` | `Community.get()` + deleted check | Easy |
| 3 | `_get_post(post_id)` | `Post.get()` + deleted check | Easy |
| 4 | `_get_post_for_user(post_id, user_id)` | Access control with anti-enumeration | Medium |
| 5 | `_check_community_membership(user_id, community_id)` | Placeholder (returns True) | Easy |
| 6 | `_check_community_leader(user_id, community_id)` | Cross-collection Community lookup | Easy |
| 7 | `_validate_version(post, version)` | Pure Python | Easy |
| 8 | `_build_author(user, is_leader)` | Denormalized snapshot from User | Easy |
| 9 | `_build_media_list/link_preview/poll/mentions` | Construction helpers | Easy |
| 10 | `create_community_post(...)` | Cross-collection + insert | Medium |
| 11 | `list_community_posts(...)` | Cursor pagination + `$or` tiebreaker + `$in` status | **Hard** |
| 12 | `get_home_feed(...)` | **`$or` + `$and` + `$in` + cursor** | **Very Hard** |
| 13 | `get_post(post_id, user_id)` | Delegates to `_get_post_for_user` | Easy |
| 14 | `update_post(...)` | Version check + globally-tagged guard | Medium |
| 15 | `delete_post(...)` | 3-tier permissions + soft delete + revoke | Medium |
| 16 | `publish_post(...)` | Version check + model helper + optional distribution | Medium |
| 17 | `request_global_distribution(...)` | Version check + model helper | Easy |
| 18 | `create_change_request(...)` | Cross-collection `find_one` for pending check + insert | Medium |
| 19 | `list_change_requests(...)` | Cursor pagination on PostChangeRequests | Medium |
| 20 | `hide_post(...)` | Leader/admin check + version + model helper | Medium |
| 21 | `unhide_post(...)` | Same pattern as hide | Easy |
| 22 | `pin_post(...)` | `.count()` for max pins + model helper | Medium |
| 23 | `unpin_post(...)` | Leader check + model helper | Easy |
| 24 | `create_global_post(...)` | Admin-only post with auto-approved distribution | Medium |
| 25 | `get_pending_distribution_posts(...)` | Cursor pagination on nested field | Medium |
| 26 | `approve/reject/revoke_global_distribution(...)` | Model helper delegation | Easy |
| 27 | `get_pending_change_requests(...)` | Cursor pagination on PostChangeRequests | Medium |
| 28 | `approve_change_request(...)` | Get + apply changes + capture originals | **Hard** |
| 29 | `reject_change_request(...)` | Get + model helper | Easy |

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods Foundation

**Concept**: Cross-collection lookups with `get()`, access control, denormalized data construction

#### 5.1a: Get Helpers - `_get_user`, `_get_community`, `_get_post`

All three follow the same pattern:

```python
# Pattern:
# 1. Try to get by ID (wrapping in try/except for invalid ObjectId)
# 2. Check if found AND not soft-deleted
# 3. Raise ValueError if not found
```

```python
async def _get_user(self, user_id: str) -> User:
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValueError("Invalid user ID")

    if not user or user.deleted_at:
        raise ValueError("User not found")

    return user
```

> **Why wrap `User.get()` in try/except?** Because `PydanticObjectId("not-a-valid-id")` throws an exception. We catch it and return a clear error message instead of exposing internal details.

Implement `_get_community` and `_get_post` following the same pattern. The only difference is the model class and error messages.

<details>
<summary>Full Implementation - All Three</summary>

```python
async def _get_user(self, user_id: str) -> User:
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValueError("Invalid user ID")
    if not user or user.deleted_at:
        raise ValueError("User not found")
    return user

async def _get_community(self, community_id: str) -> Community:
    try:
        community = await Community.get(PydanticObjectId(community_id))
    except Exception:
        raise ValueError("Invalid community ID")
    if not community or community.deleted_at:
        raise ValueError("Community not found")
    return community

async def _get_post(self, post_id: str) -> Post:
    try:
        post = await Post.get(PydanticObjectId(post_id))
    except Exception:
        raise ValueError("Invalid post ID")
    if not post or post.deleted_at:
        raise ValueError("Post not found")
    return post
```
</details>

---

#### 5.1b: `_get_post_for_user(post_id, user_id)` - Access Control

**What it does**: Gets a post but only if the user has access to it.

**Access rules** (in order of check):
1. If user is the **author** → always has access
2. If post is **published** AND **globally distributed** → anyone has access
3. If post is **published** AND in a **community** → members have access (TODO: proper check)
4. Otherwise → "Post not found" (anti-enumeration)

```python
# The anti-enumeration pattern (same as TASK_03, TASK_04):
# NEVER say "Access denied" - always say "Not found"
# This prevents attackers from discovering which posts exist
```

> **Hint Level 1**: Call `self._get_post(post_id)` first, then check the access rules. Return the post if any rule passes, raise "Post not found" if none do.

<details>
<summary>Full Implementation</summary>

```python
async def _get_post_for_user(self, post_id: str, user_id: str) -> Post:
    post = await self._get_post(post_id)

    # Author always has access
    if str(post.author.user_id) == user_id:
        return post

    if post.status == PostStatus.PUBLISHED:
        # Globally distributed posts are accessible to everyone
        if post.is_globally_distributed():
            return post
        # Community posts accessible to members
        if post.community_id:
            user = await self._get_user(user_id)
            # TODO: Check community membership properly
            return post

    raise ValueError("Post not found")  # Anti-enumeration
```
</details>

---

#### 5.1c: `_check_community_leader(user_id, community_id)`

**What it does**: Checks if the user is the leader of a community by cross-collection lookup.

```python
async def _check_community_leader(self, user_id: str, community_id: str) -> bool:
    try:
        community = await self._get_community(community_id)
        return str(community.leader_id) == user_id
    except Exception:
        return False
```

> **Why return `False` instead of raising?** Because this is a permission check, not a validation. If the community doesn't exist, the user is simply not a leader of it.

---

#### 5.1d: Builder Helpers

These pure Python methods construct embedded documents from request data. No MongoDB involved.

**`_build_author(user, is_leader)`**: Create a denormalized `PostAuthor` from a `User` object.

```python
def _build_author(self, user: User, is_leader: bool = False) -> PostAuthor:
    return PostAuthor(
        user_id=user.id,
        display_name=user.display_name or user.email.split("@")[0],
        avatar=user.avatar_url or "https://example.com/default-avatar.png",
        author_type=AuthorType.LEADER if is_leader else AuthorType.USER,
        is_verified=user.is_verified if hasattr(user, "is_verified") else False
    )
```

> **Note**: `user.display_name` might not exist, so we fall back to the email prefix. Same defensive approach for `avatar_url` and `is_verified`.

**`_build_media_list`, `_build_link_preview`, `_build_poll`, `_build_mentions`**: All follow the same pattern - check for None, then build the embedded objects from dict data.

<details>
<summary>Full Implementation - All Builders</summary>

```python
def _build_media_list(self, media_data: Optional[List[Dict]]) -> List[MediaAttachment]:
    if not media_data:
        return []
    return [
        MediaAttachment(
            media_type=m.get("media_type"),
            media_url=m.get("media_url"),
            thumbnail_url=m.get("thumbnail_url"),
            width=m.get("width"),
            height=m.get("height"),
            duration_seconds=m.get("duration_seconds"),
            size_bytes=m.get("size_bytes")
        )
        for m in media_data
    ]

def _build_link_preview(self, preview_data: Optional[Dict]) -> Optional[LinkPreview]:
    if not preview_data:
        return None
    return LinkPreview(
        url=preview_data.get("url"),
        title=preview_data.get("title"),
        description=preview_data.get("description"),
        image=preview_data.get("image"),
        site_name=preview_data.get("site_name")
    )

def _build_poll(self, poll_data: Optional[Dict]) -> Optional[PollData]:
    if not poll_data:
        return None
    return PollData(
        question=poll_data.get("question"),
        options=[
            PollOption(
                option_id=opt.get("option_id"),
                option_text=opt.get("option_text"),
                vote_count=0
            )
            for opt in poll_data.get("options", [])
        ],
        allows_multiple_votes=poll_data.get("allows_multiple_votes", False),
        ends_at=poll_data.get("ends_at"),
        total_votes=0
    )

def _build_mentions(self, mentions_data: Optional[List[Dict]]) -> List[PostMentions]:
    if not mentions_data:
        return []
    return [
        PostMentions(
            user_id=PydanticObjectId(m.get("user_id")),
            display_name=m.get("display_name")
        )
        for m in mentions_data
    ]
```
</details>

---

### Exercise 5.2: Create Community Post

**Concept**: Cross-collection validation, embedded document construction, conditional status + global distribution logic

#### The Method Signature

```python
async def create_community_post(
    self,
    user_id: str,
    community_id: str,
    post_type: str,
    text_content: str,
    media: Optional[List[Dict]] = None,
    link_preview: Optional[Dict] = None,
    poll: Optional[Dict] = None,
    tags: Optional[List[str]] = None,
    mentions: Optional[List[Dict]] = None,
    is_draft: bool = False,
    request_global_distribution: bool = False
) -> Post:
```

#### Step-by-Step Algorithm

```
1. Validate user exists (cross-collection)
   └── await self._get_user(user_id)

2. Validate community exists (cross-collection)
   └── await self._get_community(community_id)

3. Check community membership
   └── await self._check_community_membership(user_id, community_id)

4. Check if user is community leader
   └── await self._check_community_leader(user_id, community_id)

5. Validate post_type enum
   └── PostType(post_type) - catch ValueError

6. Validate poll/non-poll consistency
   └── Poll type MUST have poll data; non-poll MUST NOT

7. Build Post document:
   └── Use all _build_* helpers
   └── Denormalize: community_id, community_name from community

8. Set status based on is_draft flag:
   └── If draft → PostStatus.DRAFT
   └── If not draft → PostStatus.PUBLISHED + set published_at
       └── If request_global_distribution → set distribution to PENDING

9. await post.insert()

10. Emit Kafka event (Topic.POST, action="created")

11. Return post
```

#### The Conditional Status + Distribution Logic

```python
# Set status
if is_draft:
    post.status = PostStatus.DRAFT
else:
    post.status = PostStatus.PUBLISHED
    post.published_at = utc_now()

    # Handle global distribution request (only on publish)
    if request_global_distribution:
        post.global_distribution.requested = True
        post.global_distribution.status = GlobalDistributionStatus.PENDING
        post.global_distribution.requested_at = utc_now()
```

> **Think about it**: Why can you only request global distribution on publish, not on draft? Because global distribution means "show this on the main feed" - a draft that nobody can see shouldn't be in the global approval queue.

> **Hint Level 1**: Follow the algorithm. The key insight is that you set the global distribution fields BEFORE inserting, so they're part of the initial document.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def create_community_post(
    self, user_id: str, community_id: str, post_type: str, text_content: str,
    media=None, link_preview=None, poll=None, tags=None, mentions=None,
    is_draft: bool = False, request_global_distribution: bool = False
) -> Post:
    user = await self._get_user(user_id)
    community = await self._get_community(community_id)

    if not await self._check_community_membership(user_id, community_id):
        raise ValueError("User is not a member of this community")

    is_leader = await self._check_community_leader(user_id, community_id)

    try:
        post_type_enum = PostType(post_type)
    except ValueError:
        raise ValueError(f"Invalid post type: {post_type}")

    if post_type_enum == PostType.POLL and not poll:
        raise ValueError("Poll posts must have poll data")
    if post_type_enum != PostType.POLL and poll:
        raise ValueError("Only poll posts can have poll data")

    post = Post(
        post_type=post_type_enum,
        author=self._build_author(user, is_leader),
        text_content=text_content,
        media=self._build_media_list(media),
        link_preview=self._build_link_preview(link_preview),
        poll=self._build_poll(poll),
        community_id=community.id,
        community_name=community.name,
        tags=tags or [],
        mentions=self._build_mentions(mentions),
        stats=PostStats(),
        global_distribution=GlobalDistribution()
    )

    if is_draft:
        post.status = PostStatus.DRAFT
    else:
        post.status = PostStatus.PUBLISHED
        post.published_at = utc_now()
        if request_global_distribution:
            post.global_distribution.requested = True
            post.global_distribution.status = GlobalDistributionStatus.PENDING
            post.global_distribution.requested_at = utc_now()

    await post.insert()

    self._kafka.emit(
        topic=Topic.POST,
        action="created",
        entity_id=oid_to_str(post.id),
        data=post.model_dump(mode="json"),
    )
    return post
```
</details>

---

### Exercise 5.3: List Community Posts (Cursor Pagination with `$or` Tiebreaker)

**Concept**: Cursor pagination using `published_at` + `_id` tiebreaker, base64 cursor encoding, leader-only hidden post visibility

#### The Method Signature

```python
async def list_community_posts(
    self,
    user_id: str,
    community_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
    include_hidden: bool = False
) -> Tuple[List[Post], bool]:
```

#### The `$or` Tiebreaker Pattern (Refresher from TASK_03)

In TASK_03 you used cursor pagination with `member_count`/`_id`. Here the sort key is `published_at` instead.

```python
# Why $or tiebreaker?
# Multiple posts can have the same published_at (especially bulk imports).
# If we only paginate on published_at, we'd skip or duplicate posts.
#
# The $or says: give me posts where EITHER:
# - published_at is strictly BEFORE the cursor's timestamp, OR
# - published_at EQUALS the cursor's timestamp AND _id is less than cursor's id
#
# This ensures every post appears exactly once, even with identical timestamps.

query["$or"] = [
    {"published_at": {"$lt": cursor_published_at}},
    {
        "published_at": cursor_published_at,
        "_id": {"$lt": PydanticObjectId(cursor_id)}
    }
]
```

#### New Concept: Base64 Cursor Encoding

Unlike TASK_03/04 where cursors were plain IDs, post cursors encode BOTH `published_at` and `id`:

```python
# Encoding (done by post_utils.py):
cursor_data = {"published_at": "2024-01-15T10:30:00", "id": "abc123"}
cursor = base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()
# → "eyJwdWJsaXNoZWRfYXQiOiAiMjAyNC0wMS0xNVQxMDozMDowMCIsICJpZCI6ICJhYmMxMjMifQ=="

# Decoding:
cursor_data = decode_cursor(cursor)
# → {"published_at": "2024-01-15T10:30:00", "id": "abc123"}
```

#### Leader-Only Hidden Posts

```python
# Leaders can see hidden posts if they request it
if include_hidden and is_leader:
    query["status"] = {"$in": [PostStatus.PUBLISHED.value, PostStatus.HIDDEN.value]}
else:
    query["status"] = PostStatus.PUBLISHED.value
```

> **Note**: We use `.value` (e.g., `PostStatus.PUBLISHED.value` = `"published"`) because MongoDB stores the string value, not the enum object.

> **Hint Level 1**: Build the base query with `community_id` and `deleted_at: None`. Add status filter (with `$in` for leader). Decode cursor and add `$or` tiebreaker. Sort by `[("published_at", -1), ("_id", -1)]`. Use the fetch+has-more pattern.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def list_community_posts(
    self, user_id: str, community_id: str, cursor=None, limit=20, include_hidden=False
) -> Tuple[List[Post], bool]:
    await self._get_community(community_id)

    if not await self._check_community_membership(user_id, community_id):
        raise ValueError("User is not a member of this community")

    is_leader = await self._check_community_leader(user_id, community_id)

    query = {
        "community_id": PydanticObjectId(community_id),
        "deleted_at": None
    }

    if include_hidden and is_leader:
        query["status"] = {"$in": [PostStatus.PUBLISHED.value, PostStatus.HIDDEN.value]}
    else:
        query["status"] = PostStatus.PUBLISHED.value

    if cursor:
        cursor_data = decode_cursor(cursor)
        query["$or"] = [
            {"published_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
            {
                "published_at": datetime.fromisoformat(cursor_data["published_at"]),
                "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
            }
        ]

    limit = min(limit, self.max_page_size)
    posts = await Post.find(query).sort([("published_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    return posts, has_more
```
</details>

---

### Exercise 5.4: Home Feed - THE BIG ONE

**Concept**: `$or` + `$and` + `$in` composition for a feed that combines community posts with globally-distributed posts, plus cursor pagination

This is the **most complex query in the entire course**.

#### The Method Signature

```python
async def get_home_feed(
    self,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20
) -> Tuple[List[Post], bool]:
```

#### The Problem

A user's home feed should show:
1. Posts from communities they belong to
2. Posts with approved global distribution (visible to everyone)

These are two DIFFERENT conditions combined with `$or`. Then cursor pagination ALSO uses `$or`. You can't just add both `$or` clauses to the same query - you need `$and` to combine them.

#### Building the Query Step by Step

**Step 1**: Get the user and their community IDs

```python
user = await self._get_user(user_id)
# TODO: Get actual community memberships from membership collection
community_ids = []  # placeholder
```

**Step 2**: Build the feed filter (without cursor)

```python
query = {
    "status": PostStatus.PUBLISHED.value,
    "deleted_at": None,
    "$or": [
        # Posts from user's communities
        {"community_id": {"$in": [PydanticObjectId(c) for c in community_ids]}},
        # Posts with approved global distribution
        {"global_distribution.status": GlobalDistributionStatus.APPROVED.value}
    ]
}
```

**Step 3**: Add cursor pagination (the tricky part!)

```python
# WITHOUT cursor, query has $or for feed sources
# WITH cursor, we need ANOTHER $or for pagination tiebreaker
# MongoDB doesn't allow two $or at the top level!
# Solution: wrap the whole thing in $and

if cursor:
    cursor_data = decode_cursor(cursor)
    query = {
        "$and": [
            query,  # ← The original feed filter (including its $or)
            {
                "$or": [  # ← The pagination tiebreaker
                    {"published_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                    {
                        "published_at": datetime.fromisoformat(cursor_data["published_at"]),
                        "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                    }
                ]
            }
        ]
    }
```

#### The `$and` + `$or` Pattern Visualized

```
WITHOUT cursor:
{
  status: "published",
  deleted_at: null,
  $or: [
    { community_id: { $in: [comm1, comm2] } },
    { "global_distribution.status": "approved" }
  ]
}

WITH cursor:
{
  $and: [
    {                                            ← Original feed filter
      status: "published",
      deleted_at: null,
      $or: [                                     ← Feed sources
        { community_id: { $in: [comm1, comm2] } },
        { "global_distribution.status": "approved" }
      ]
    },
    {
      $or: [                                     ← Pagination tiebreaker
        { published_at: { $lt: cursor_time } },
        { published_at: cursor_time, _id: { $lt: cursor_id } }
      ]
    }
  ]
}
```

> **Why `$and`?** MongoDB only allows one `$or` per query level. Since both the feed filter and the cursor use `$or`, we need `$and` to combine them at a higher level. Without `$and`, the second `$or` would overwrite the first.

> **Hint Level 1**: Build the query in two stages. First build without cursor (has `$or` for feed sources). Then if cursor exists, wrap the original query in `$and` with the pagination `$or`.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def get_home_feed(self, user_id: str, cursor=None, limit=20) -> Tuple[List[Post], bool]:
    user = await self._get_user(user_id)

    # TODO: Get actual community memberships
    community_ids = []

    query = {
        "status": PostStatus.PUBLISHED.value,
        "deleted_at": None,
        "$or": [
            {"community_id": {"$in": [PydanticObjectId(c) for c in community_ids]}},
            {"global_distribution.status": GlobalDistributionStatus.APPROVED.value}
        ]
    }

    if cursor:
        cursor_data = decode_cursor(cursor)
        query = {
            "$and": [
                query,
                {
                    "$or": [
                        {"published_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                        {
                            "published_at": datetime.fromisoformat(cursor_data["published_at"]),
                            "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                        }
                    ]
                }
            ]
        }

    limit = min(limit, self.max_page_size)
    posts = await Post.find(query).sort([("published_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    return posts, has_more
```
</details>

---

### Exercise 5.5: Single Post Operations (CRUD + Lifecycle)

**Concept**: Optimistic locking, globally-tagged edit guard, 3-tier delete permissions, model helper delegation

#### 5.5a: `update_post(...)` - Optimistic Locking + Global Edit Guard

```
Algorithm:
1. Get post for user (access check)
2. Check ownership: only author can edit (or community leader)
3. Validate version (optimistic locking)
4. Check if globally tagged → block direct edits, require change request
5. Apply partial updates
6. Increment version, save
```

**The globally-tagged guard**:
```python
if post.is_globally_tagged():
    raise ValueError("Cannot directly edit globally-tagged posts. Submit a change request instead.")
```

> **Why block edits on globally-tagged posts?** Because if a post is pending admin approval for global distribution (or already approved), changing its content would bypass the review. The author must submit a change request instead, which goes through admin review.

<details>
<summary>Full Implementation</summary>

```python
async def update_post(
    self, post_id: str, user_id: str, version: int,
    text_content=None, media=None, link_preview=None, tags=None
) -> Post:
    post = await self._get_post_for_user(post_id, user_id)

    if str(post.author.user_id) != user_id:
        if post.community_id:
            is_leader = await self._check_community_leader(user_id, str(post.community_id))
            if not is_leader:
                raise ValueError("Post not found")
        else:
            raise ValueError("Post not found")

    self._validate_version(post, version)

    if post.is_globally_tagged():
        raise ValueError("Cannot directly edit globally-tagged posts. Submit a change request instead.")

    if text_content is not None:
        post.text_content = text_content
    if media is not None:
        post.media = self._build_media_list(media)
    if link_preview is not None:
        post.link_preview = self._build_link_preview(link_preview)
    if tags is not None:
        post.tags = tags

    post.updated_at = utc_now()
    post.version += 1
    await post.save()
    return post
```
</details>

---

#### 5.5b: `delete_post(...)` - 3-Tier Permission Hierarchy

This method has the **most complex permission logic** in the entire course:

```
Permission rules:
├── Globally-distributed posts → ONLY admin can delete
├── Draft posts → ONLY author can delete
└── Published posts → ONLY leader or admin can delete
    (Author CANNOT delete their own published post!)
```

```python
# The layered check:
is_author = str(post.author.user_id) == user_id
is_leader = False
if post.community_id:
    is_leader = await self._check_community_leader(user_id, str(post.community_id))

# Layer 1: Global posts need admin
if post.is_globally_distributed() and not is_admin:
    raise ValueError("Only admins can delete globally-distributed posts")

# Layer 2: Drafts need author
if post.status == PostStatus.DRAFT:
    if not is_author:
        raise ValueError("Post not found")

# Layer 3: Published posts need leader or admin
else:
    if not (is_leader or is_admin):
        raise ValueError("Post not found")
```

**After deletion**: If the post was globally distributed, revoke its distribution.

<details>
<summary>Full Implementation</summary>

```python
async def delete_post(self, post_id: str, user_id: str, version: int, is_admin=False) -> Post:
    post = await self._get_post_for_user(post_id, user_id)
    self._validate_version(post, version)

    is_author = str(post.author.user_id) == user_id
    is_leader = False
    if post.community_id:
        is_leader = await self._check_community_leader(user_id, str(post.community_id))

    if post.is_globally_distributed() and not is_admin:
        raise ValueError("Only admins can delete globally-distributed posts")

    if post.status == PostStatus.DRAFT:
        if not is_author:
            raise ValueError("Post not found")
    else:
        if not (is_leader or is_admin):
            raise ValueError("Post not found")

    await post.soft_delete()

    self._kafka.emit(
        topic=Topic.POST,
        action="deleted",
        entity_id=oid_to_str(post.id),
        data={
            "author_id": oid_to_str(post.author.user_id),
            "community_id": oid_to_str(post.community_id) if post.community_id else None,
            "deleted_by": user_id,
        },
    )

    if post.global_distribution.status == GlobalDistributionStatus.APPROVED:
        post.global_distribution.status = GlobalDistributionStatus.REVOKED
        post.global_distribution.revoked_at = utc_now()
        await post.save()

    return post
```
</details>

---

#### 5.5c: `publish_post(...)` - Draft to Published + Optional Distribution

```python
async def publish_post(self, post_id: str, user_id: str, version: int,
                       request_global_distribution: bool = False) -> Post:
    post = await self._get_post_for_user(post_id, user_id)

    if str(post.author.user_id) != user_id:
        raise ValueError("Post not found")

    self._validate_version(post, version)

    if post.status != PostStatus.DRAFT:
        raise ValueError("Only draft posts can be published")

    await post.publish()  # Model helper: sets PUBLISHED + published_at

    if request_global_distribution and post.can_request_global_distribution():
        await post.request_global_distribution()

    return post
```

---

### Exercise 5.6: Global Distribution Request

**Concept**: Version check + model helper delegation

```python
async def request_global_distribution(self, post_id: str, user_id: str, version: int) -> Post:
    post = await self._get_post_for_user(post_id, user_id)

    if str(post.author.user_id) != user_id:
        raise ValueError("Post not found")

    self._validate_version(post, version)

    if not post.can_request_global_distribution():
        raise ValueError("Cannot request global distribution for this post")

    await post.request_global_distribution()
    return post
```

---

### Exercise 5.7: Change Requests - Cross-Collection CRUD

**Concept**: Working with a second collection (PostChangeRequests), `find_one` for pending check, insert, cursor pagination

#### 5.7a: `create_change_request(...)` - Insert to Second Collection

```
Algorithm:
1. Get post for user (access check)
2. Check permissions: author or leader
3. Check post IS globally tagged (if not, tell them to edit directly)
4. Validate requested changes (only allowed fields)
5. Check no PENDING request already exists (find_one on PostChangeRequest)
6. Create and insert PostChangeRequest
```

**The pending check**:
```python
existing = await PostChangeRequest.find_one({
    "post_id": post.id,
    "status": ChangeRequestStatus.PENDING.value
})
if existing:
    raise ValueError("A pending change request already exists for this post")
```

> **Why only one pending request?** To prevent confusion. If an author submits 3 change requests, the admin wouldn't know which to review first. One at a time keeps the workflow clear.

<details>
<summary>Full Implementation</summary>

```python
async def create_change_request(
    self, post_id: str, user_id: str, requested_changes: Dict[str, Any], reason: str
) -> PostChangeRequest:
    post = await self._get_post_for_user(post_id, user_id)

    is_author = str(post.author.user_id) == user_id
    is_leader = False
    if post.community_id:
        is_leader = await self._check_community_leader(user_id, str(post.community_id))

    if not (is_author or is_leader):
        raise ValueError("Post not found")

    if not post.is_globally_tagged():
        raise ValueError("Post is not globally tagged. Edit directly instead.")

    PostChangeRequest.validate_requested_changes(requested_changes)

    existing = await PostChangeRequest.find_one({
        "post_id": post.id,
        "status": ChangeRequestStatus.PENDING.value
    })
    if existing:
        raise ValueError("A pending change request already exists for this post")

    change_request = PostChangeRequest(
        post_id=post.id,
        author_id=PydanticObjectId(user_id),
        requested_changes=requested_changes,
        reason=reason
    )
    await change_request.insert()
    return change_request
```
</details>

---

#### 5.7b: `list_change_requests(...)` - Cursor Pagination on Second Collection

Same `$or` tiebreaker pattern, but on `PostChangeRequest` documents sorted by `created_at`.

<details>
<summary>Full Implementation</summary>

```python
async def list_change_requests(
    self, post_id: str, user_id: str, cursor=None, limit=20, status_filter=None
) -> Tuple[List[PostChangeRequest], bool]:
    post = await self._get_post_for_user(post_id, user_id)

    query = {"post_id": post.id}
    if status_filter:
        query["status"] = status_filter

    if cursor:
        cursor_data = decode_cursor(cursor)
        query["$or"] = [
            {"created_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
            {
                "created_at": datetime.fromisoformat(cursor_data["published_at"]),
                "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
            }
        ]

    limit = min(limit, self.max_page_size)
    requests = await PostChangeRequest.find(query).sort([("created_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

    has_more = len(requests) > limit
    if has_more:
        requests = requests[:limit]

    return requests, has_more
```
</details>

---

### Exercise 5.8: Moderation - Hide/Unhide/Pin/Unpin

**Concept**: Leader/admin permission checks, `.count()` for pin limits, version-based optimistic locking

#### 5.8a: `hide_post` / `unhide_post`

Both follow the same pattern:
1. Get post (not `_get_post_for_user` - leader may not be "a user" of the post)
2. Check permissions: leader or admin
3. Validate version
4. Call model helper

<details>
<summary>Full Implementation - hide_post</summary>

```python
async def hide_post(self, post_id: str, user_id: str, version: int,
                    reason=None, is_admin=False) -> Post:
    post = await self._get_post(post_id)

    is_leader = False
    if post.community_id:
        is_leader = await self._check_community_leader(user_id, str(post.community_id))

    if not (is_leader or is_admin):
        raise ValueError("Post not found")

    self._validate_version(post, version)
    await post.hide_post(PydanticObjectId(user_id), reason)

    self._kafka.emit(
        topic=Topic.POST,
        action="hidden",
        entity_id=oid_to_str(post.id),
        data={
            "author_id": oid_to_str(post.author.user_id),
            "community_id": oid_to_str(post.community_id) if post.community_id else None,
            "hidden_by": user_id,
            "reason": reason,
        },
    )
    return post
```
</details>

---

#### 5.8b: `pin_post` - The `.count()` Pattern

**New MongoDB Operation**: Using `.count()` to check a limit before inserting/updating.

```python
# Count existing pinned posts in this community
pinned_count = await Post.find({
    "community_id": post.community_id,
    "is_pinned": True,
    "deleted_at": None
}).count()

if pinned_count >= self.max_pinned_posts_per_community:
    raise ValueError(f"Maximum {self.max_pinned_posts_per_community} posts can be pinned in a community")
```

**Index used**: `[("community_id", 1), ("is_pinned", 1), ("status", 1)]` (Index #9)

> **Why count instead of just trying to pin?** Because we need a business rule: max 3 pinned posts per community. Without checking first, we'd need to handle the violation after the fact.

<details>
<summary>Full Implementation - pin_post</summary>

```python
async def pin_post(self, post_id: str, user_id: str, version: int, is_admin=False) -> Post:
    post = await self._get_post(post_id)

    if not post.community_id:
        raise ValueError("Only community posts can be pinned")

    is_leader = await self._check_community_leader(user_id, str(post.community_id))
    if not (is_leader or is_admin):
        raise ValueError("Post not found")

    self._validate_version(post, version)

    pinned_count = await Post.find({
        "community_id": post.community_id,
        "is_pinned": True,
        "deleted_at": None
    }).count()

    if pinned_count >= self.max_pinned_posts_per_community:
        raise ValueError(f"Maximum {self.max_pinned_posts_per_community} posts can be pinned in a community")

    await post.pin_post(PydanticObjectId(user_id))
    return post
```
</details>

---

### Exercise 5.9: Admin Operations

**Concept**: Admin-only post creation with auto-approved distribution, pending queues with cursor pagination, change request approval with field application

#### 5.9a: `create_global_post(admin_id, ...)` - Admin-Only Global Post

```
Key difference from community post:
- community_id = None (no community)
- Status = PUBLISHED immediately
- Global distribution = APPROVED immediately (admin bypass)
- Author type = LEADER (admin posts as leader type)
```

<details>
<summary>Full Implementation</summary>

```python
async def create_global_post(
    self, admin_id: str, post_type: str, text_content: str,
    media=None, link_preview=None, poll=None, tags=None, mentions=None
) -> Post:
    admin = await self._get_user(admin_id)

    try:
        post_type_enum = PostType(post_type)
    except ValueError:
        raise ValueError(f"Invalid post type: {post_type}")

    if post_type_enum == PostType.POLL and not poll:
        raise ValueError("Poll posts must have poll data")
    if post_type_enum != PostType.POLL and poll:
        raise ValueError("Only poll posts can have poll data")

    post = Post(
        post_type=post_type_enum,
        author=self._build_author(admin, is_leader=True),
        text_content=text_content,
        media=self._build_media_list(media),
        link_preview=self._build_link_preview(link_preview),
        poll=self._build_poll(poll),
        community_id=None,
        community_name=None,
        tags=tags or [],
        mentions=self._build_mentions(mentions),
        stats=PostStats(),
        status=PostStatus.PUBLISHED,
        published_at=utc_now(),
        global_distribution=GlobalDistribution(
            requested=True,
            status=GlobalDistributionStatus.APPROVED,
            requested_at=utc_now(),
            reviewed_at=utc_now(),
            reviewed_by=admin.id
        )
    )

    await post.insert()
    return post
```
</details>

---

#### 5.9b: `get_pending_distribution_posts(...)` - Admin Queue

Paginated list of posts awaiting global distribution approval, sorted by `requested_at` ascending (oldest first).

```python
query = {
    "global_distribution.status": GlobalDistributionStatus.PENDING.value,
    "deleted_at": None
}
```

> **Note the sort direction**: Ascending (`1`) not descending (`-1`). We want the admin to see the OLDEST pending request first (FIFO queue).

<details>
<summary>Full Implementation</summary>

```python
async def get_pending_distribution_posts(self, cursor=None, limit=20) -> Tuple[List[Post], bool]:
    query = {
        "global_distribution.status": GlobalDistributionStatus.PENDING.value,
        "deleted_at": None
    }

    if cursor:
        cursor_data = decode_cursor(cursor)
        query["$or"] = [
            {"global_distribution.requested_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
            {
                "global_distribution.requested_at": datetime.fromisoformat(cursor_data["published_at"]),
                "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
            }
        ]

    limit = min(limit, self.max_page_size)
    posts = await Post.find(query).sort([("global_distribution.requested_at", 1), ("_id", 1)]).limit(limit + 1).to_list()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    return posts, has_more
```
</details>

---

#### 5.9c: `approve/reject/revoke_global_distribution` - Model Helper Delegation

These are thin wrappers around model helpers:

```python
async def approve_global_distribution(self, post_id: str, admin_id: str) -> Post:
    post = await self._get_post(post_id)
    await post.approve_global_distribution(PydanticObjectId(admin_id))

    self._kafka.emit(
        topic=Topic.POST,
        action="global_distribution_approved",
        entity_id=oid_to_str(post.id),
        data={
            "author_id": oid_to_str(post.author.user_id),
            "community_id": oid_to_str(post.community_id) if post.community_id else None,
            "admin_id": admin_id,
        },
    )
    return post

async def reject_global_distribution(self, post_id: str, admin_id: str, reason: str) -> Post:
    post = await self._get_post(post_id)
    await post.reject_global_distribution(PydanticObjectId(admin_id), reason)
    return post

async def revoke_global_distribution(self, post_id: str, admin_id: str, reason: str) -> Post:
    post = await self._get_post(post_id)
    await post.revoke_global_distribution(PydanticObjectId(admin_id), reason)
    return post
```

---

#### 5.9d: `approve_change_request(...)` - The Hardest Admin Operation

**What it does**: Approves a change request, captures the original values from the post, applies the changes to the post, and marks the request as applied.

```
Algorithm:
1. Get change request by ID
2. Verify it's pending
3. Get the post
4. Capture original values (BEFORE applying changes)
5. Apply changes to the post (dispatch by field type)
6. Increment version, save post
7. Approve the change request (model helper)
8. Mark as applied with original values (model helper)
9. Return both change request and post
```

**Capturing original values** (for rollback capability):
```python
original_values = {}
for field in change_request.requested_changes.keys():
    if hasattr(post, field):
        value = getattr(post, field)
        if hasattr(value, "model_dump"):
            original_values[field] = value.model_dump()
        elif isinstance(value, list):
            original_values[field] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in value
            ]
        else:
            original_values[field] = value
```

<details>
<summary>Full Implementation</summary>

```python
async def approve_change_request(
    self, request_id: str, admin_id: str, notes=None
) -> Tuple[PostChangeRequest, Post]:
    try:
        change_request = await PostChangeRequest.get(PydanticObjectId(request_id))
    except Exception:
        raise ValueError("Invalid change request ID")

    if not change_request:
        raise ValueError("Change request not found")

    if not change_request.is_pending():
        raise ValueError("Change request is not pending")

    post = await self._get_post(str(change_request.post_id))

    # Capture original values
    original_values = {}
    for field in change_request.requested_changes.keys():
        if hasattr(post, field):
            value = getattr(post, field)
            if hasattr(value, "model_dump"):
                original_values[field] = value.model_dump()
            elif isinstance(value, list):
                original_values[field] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            else:
                original_values[field] = value

    # Apply changes
    for field, value in change_request.requested_changes.items():
        if field == "media":
            post.media = self._build_media_list(value)
        elif field == "link_preview":
            post.link_preview = self._build_link_preview(value)
        elif field == "tags":
            post.tags = value
        elif field == "text_content":
            post.text_content = value

    post.updated_at = utc_now()
    post.version += 1
    await post.save()

    await change_request.approve(PydanticObjectId(admin_id), notes)
    await change_request.mark_applied(original_values)

    return change_request, post
```
</details>

---

## 6. VERIFICATION CHECKLIST

| # | Test | What to Verify |
|---|------|---------------|
| 1 | Create a community post (published) | Post appears in community feed |
| 2 | Create a draft post | Status is DRAFT, not in feed |
| 3 | List community posts | Pagination works, only published visible |
| 4 | List community posts (as leader, include_hidden=True) | Hidden posts also visible |
| 5 | Get home feed | Shows community posts + globally-distributed |
| 6 | Update a post | Text changes, version increments |
| 7 | Update a globally-tagged post | Should fail with "change request" error |
| 8 | Delete a draft (as author) | Succeeds |
| 9 | Delete a published post (as leader) | Succeeds |
| 10 | Delete a globally-distributed post (as non-admin) | Fails |
| 11 | Publish a draft | Status changes to PUBLISHED |
| 12 | Request global distribution | Distribution status changes to PENDING |
| 13 | Create a change request for globally-tagged post | Inserts to post_change_requests |
| 14 | Create second change request (pending exists) | Should fail |
| 15 | Hide a post (as leader) | Status changes to HIDDEN |
| 16 | Pin a post | is_pinned = true |
| 17 | Pin a 4th post (max 3) | Should fail |
| 18 | Create global post (admin) | community_id is null, distribution auto-approved |
| 19 | Approve global distribution | Status changes to APPROVED |
| 20 | Approve change request | Changes applied to post + original values captured |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: The `$and` + `$or` Index Problem

The home feed query combines `$and` with nested `$or`. Run `.explain("executionStats")` on this query:

```javascript
db.posts.find({
  $and: [
    {
      status: "published",
      deleted_at: null,
      $or: [
        { community_id: { $in: [ObjectId("..."), ObjectId("...")] } },
        { "global_distribution.status": "approved" }
      ]
    },
    {
      $or: [
        { published_at: { $lt: ISODate("2024-01-15") } },
        { published_at: ISODate("2024-01-15"), _id: { $lt: ObjectId("...") } }
      ]
    }
  ]
}).sort({ published_at: -1, _id: -1 }).limit(21)
```

**Questions**:
1. Which index does MongoDB choose for this query?
2. How many documents does it examine vs. return?
3. Would adding a compound index on `(status, global_distribution.status, published_at)` help?
4. What's the difference between MongoDB using an index for the `$or` vs. doing a collection scan?

### Challenge 2: Denormalized Author Data Staleness

When a user changes their `display_name` or `avatar_url`, every post they've ever created still has the OLD values in `author.display_name` and `author.avatar`.

**Questions**:
1. How would you detect stale author data? (Hint: compare `post.author.display_name` to `user.display_name`)
2. Design a background job that refreshes denormalized author data. What query would it use to find affected posts?
3. How would you use `updateMany` to batch-update all posts by a specific author?

```javascript
// Example batch update:
db.posts.updateMany(
  { "author.user_id": ObjectId("user123") },
  { $set: {
    "author.display_name": "New Name",
    "author.avatar": "https://new-avatar.png"
  }}
)
```

4. What index supports this `updateMany`? (Check Index #1)

### Challenge 3: Race Condition in Pin Count

The `pin_post` method has a **TOCTOU** (Time-Of-Check-Time-Of-Use) race condition:

```python
# Thread A:                          # Thread B:
pinned_count = 2                     pinned_count = 2
if pinned_count < 3:  # passes      if pinned_count < 3:  # also passes!
    await post.pin_post(...)             await post.pin_post(...)
# Result: 4 pinned posts! Exceeds limit.
```

**Questions**:
1. How would you prevent this with MongoDB's `findOneAndUpdate` + a counter field?
2. Could you use a unique partial index to enforce the limit at the database level?
3. What about using a transaction? (MongoDB 4.0+ multi-document transactions)

---

## 8. WHAT'S NEXT

Congratulations! You've built the **social content engine** - the most complex service in the course.

**Concepts you mastered**:
- `$or` + `$and` composition for complex multi-source queries
- `$in` with ObjectId arrays for community-based filtering
- Cursor pagination with `$or` tiebreaker on `published_at`/`_id`
- Base64-encoded composite cursors
- `.count()` for business rule limits
- Multi-collection CRUD (posts + post_change_requests)
- Cross-collection reads (users, communities)
- Two state machines (post lifecycle + global distribution)
- 3-tier permission hierarchy (author / leader / admin)
- Denormalized author data from User
- Optimistic locking with version validation
- Change request workflow with original value capture

**What comes next**:

**TASK_06: Promotion Service** - The marketing engine. Promotions connect Products to Communities with approval workflows, scheduling, and multi-scope visibility. You'll build:
- Multi-scope approval (global vs. community-level)
- Scheduled activation/deactivation with date queries
- Cross-collection validation (product must exist, community must exist)
- Budget tracking and spend calculations
- Admin approval queues
