# TASK 01: User Authentication Service

## 1. MISSION BRIEFING

You are building the **authentication backbone** of a Social Commerce Platform - a system where celebrities create branded communities and consumers discover and buy products without leaving the ecosystem.

Every single action on the platform starts with a **User**. Registration, login, email verification, password reset - these are the gates through which every consumer and leader enters.

### What You Will Build
The `AuthService` class - the service layer that handles all user authentication operations by writing MongoDB queries through Beanie ODM.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| `find_one()` with nested field match | Querying `contact_info.primary_email` |
| `find_one()` with array field match | Checking `contact_info.additional_emails` |
| `Document.get()` by ObjectId | Fetching user by `_id` |
| `document.insert()` | Creating new user documents |
| `document.save()` | Updating existing documents |
| Embedded document construction | Building `ContactInfo`, `UserProfile`, `CelebrityBusinessInfo` |
| Index awareness | Understanding which queries hit indexes |

---

## 2. BEFORE YOU START

### Prerequisites
- MongoDB running locally (via Docker)
- Project dependencies installed
- Basic understanding of Python async/await
- No previous tasks required (this is Task 01)

### Files You MUST Read Before Coding

Read these files in this exact order. **Do not skip any.** Understanding the data flow is critical.

#### Step 1: The Model (the data)
```
shared/models/user.py
```
This is your **data contract with MongoDB**. Every field, every embedded document, every index - read it line by line. Pay special attention to:
- The `User` class (line 166) - this is what gets stored in MongoDB
- The `Settings.indexes` (line 211) - these determine which queries are fast
- The helper methods (line 244+) - these are already written FOR you

#### Step 2: The Schema (the API contract)
```
apps/backend-service/src/schemas/auth.py
```
This defines **what the route sends you** (Request schemas) and **what you must return** (Response schemas). Your service sits between the route and the database.

#### Step 3: The Route (who calls you)
```
apps/backend-service/src/routes/auth.py
```
This is the HTTP layer. It receives requests, calls YOUR service methods, and formats responses. Notice:
- Line 28-33: The route calls `auth_service.register_consumer()` and expects a dict back
- Line 115-118: The route calls `auth_service.login()` with email, password, and ip_address
- The route handles HTTP status codes - **your service throws ValueError for business errors**

#### Step 4: The Utilities (your tools)
```
apps/backend-service/src/utils/datetime_utils.py    → utc_now()
apps/backend-service/src/utils/serialization.py     → oid_to_str()
apps/backend-service/src/kafka/producer.py          → KafkaProducer.emit()
apps/backend-service/src/kafka/topics.py            → Topic.USER
```

### The Data Flow (understand this before writing any code)

```
HTTP Request
    │
    ▼
┌─────────┐   Validates input      ┌───────────┐
│  Route   │ ──────────────────────▶│  Schema   │
│ auth.py  │   (Pydantic)          └───────────┘
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────┐
│              AuthService (YOU WRITE THIS)     │
│                                              │
│  1. Receives clean, validated data           │
│  2. Applies business rules                   │
│  3. Executes MongoDB queries via Beanie      │
│  4. Emits Kafka events                       │
│  5. Returns dict (route formats response)    │
│                                              │
│  Throws ValueError → route returns 400/401   │
│  Throws Exception  → route returns 500       │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────┐
│ MongoDB  │  (via Beanie ODM)
│  users   │
│collection│
└──────────┘
```

---

## 3. MODEL DEEP DIVE

### The User Document Structure

When a User is saved to MongoDB, it looks like this in the database:

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "password_hash": "$2b$12$LJ3m4ys...",
  "contact_info": {
    "primary_email": "jane@example.com",
    "additional_emails": ["jane.work@company.com"],
    "phone": "+1234567890",
    "phone_verified": false,
    "email_verified": true
  },
  "role": "consumer",
  "profile": {
    "display_name": "Jane Smith",
    "avatar": "https://cdn.example.com/avatars/default.jpg",
    "bio": null,
    "date_of_birth": null,
    "celebrity_business_info": null
  },
  "permissions": {
    "can_post": true,
    "can_comment": true,
    "can_manage_communities": false,
    "max_communities_owned": 5,
    "can_create_promotions": false
  },
  "stats": {
    "following_count": 0,
    "follower_count": 0,
    "communities_owned": 0,
    "total_orders": 0,
    "total_spent_cents": 0
  },
  "security": {
    "last_login_at": null,
    "last_login_ip": null,
    "failed_login_attempts": 0,
    "locked_until": null,
    "password_changed_at": "2025-01-15T10:30:00Z"
  },
  "status": "pending",
  "deleted_at": null,
  "version": 1,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Embedded Documents Hierarchy

```
User (Document - stored in "users" collection)
├── password_hash (str)
├── contact_info (ContactInfo)
│   ├── primary_email (EmailStr)          ← LOGIN KEY
│   ├── additional_emails (List[EmailStr]) ← ALSO CHECKED FOR UNIQUENESS
│   ├── phone (Optional[str])
│   ├── phone_verified (bool)
│   └── email_verified (bool)             ← FLIPPED ON VERIFICATION
├── role (UserRole: "consumer" | "leader")
├── profile (UserProfile)
│   ├── display_name (str)
│   ├── avatar (str)
│   ├── bio (Optional[str])
│   ├── date_of_birth (Optional[datetime])
│   └── celebrity_business_info (Optional[CelebrityBusinessInfo])  ← LEADERS ONLY
│       ├── business_name (str)
│       ├── business_type (BusinessType enum)
│       ├── tax_id (Optional[str])
│       ├── address (BusinessAddress)
│       │   ├── street, city, state, zip_code, country
│       ├── business_email, business_phone
│       ├── website, instagram_handle, twitter_handle, tiktok_handle, youtube_channel
│       └── agency_name, agent_name, agent_email, agent_phone
├── permissions (UserPermissions)
├── stats (UserStats)
├── security (SecurityInfo)
│   ├── last_login_at (Optional[datetime])
│   ├── last_login_ip (Optional[str])
│   ├── failed_login_attempts (int)        ← INCREMENTED ON BAD PASSWORD
│   ├── locked_until (Optional[datetime])  ← SET AFTER 5 FAILURES
│   └── password_changed_at (datetime)
├── status (UserStatus: "pending" | "active" | "suspended" | "deleted")
├── deleted_at (Optional[datetime])         ← SOFT DELETE MARKER
├── version (int)                           ← OPTIMISTIC LOCKING
├── created_at (datetime)
└── updated_at (datetime)                   ← AUTO-UPDATED ON save()
```

### Index Analysis

The model defines these indexes (line 211-233 of `user.py`):

| Index | Fields | Purpose | Your Methods Using It |
|-------|--------|---------|----------------------|
| Email lookup | `contact_info.primary_email` | Fast login queries | `is_email_available()`, `login()`, `request_password_reset()` |
| Leaderboard | `role` + `status` + `stats.follower_count` (desc) | Find top leaders | Not in this task (used in Community task) |
| Additional emails | `contact_info.additional_emails` | Email uniqueness check | `is_email_available()` |
| Business location | `address.country` + `state` + `city` | Find leaders by location | Not in this task |
| Soft delete | `deleted_at` | Filter deleted users | Implicit in many queries |
| Security | `security.locked_until` | Find locked accounts | `login()` lock check |

> **Key insight:** When you query `{"contact_info.primary_email": "jane@example.com"}`, MongoDB uses the first index. This is an O(log n) lookup, not a full collection scan. Always think about which index your query uses.

### Helper Methods Already Available

The model gives you these methods FOR FREE (you call them, you don't implement them):

```python
user.is_active()                    # status == ACTIVE and not soft-deleted
user.is_leader()                    # role == LEADER
user.is_consumer()                  # role == CONSUMER
user.is_account_locked()            # locked_until > now
user.get_primary_email()            # returns primary email
user.get_all_emails()               # returns [primary] + additional
await user.record_successful_login(ip)  # updates security fields + save()
await user.increment_failed_login()     # increments counter, locks at 5 + save()
await user.lock_account(minutes=30)     # sets locked_until + save()
await user.soft_delete()                # sets deleted_at + status + save()
```

---

## 4. THE SERVICE CONTRACT

Here is every method you must implement, with its complete contract.

### Class Setup

```python
class AuthService:
    def __init__(self):
        self.password_min_length = 8
        self.password_max_length = 128
        self.max_failed_attempts = 5
        self.lock_duration_minutes = 30
        self._kafka = get_kafka_producer()
        self.password_pattern = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$')
```

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `generate_verification_token(user_id, email)` | None | `str` (JWT) |
| 2 | `generate_reset_token(user_id, email)` | None | `str` (JWT) |
| 3 | `verify_token(token, token_type)` | None | `Dict` (payload) |
| 4 | `hash_password(password)` | None | `str` (bcrypt hash) |
| 5 | `verify_password(password, password_hash)` | None | `bool` |
| 6 | `validate_password(password, email)` | None | `None` (raises ValueError) |
| 7 | `is_email_available(email)` | `find_one` x2 | `bool` |
| 8 | `register_consumer(email, password, display_name)` | `insert` | `Dict` |
| 9 | `register_leader(email, password, display_name, ...)` | `insert` | `Dict` |
| 10 | `login(email, password, ip_address)` | `find_one` + `save` | `Dict` |
| 11 | `verify_email(token)` | `get` + `save` | `Dict` |
| 12 | `request_password_reset(email)` | `find_one` | `Optional[str]` |
| 13 | `reset_password(token, new_password)` | `get` + `save` | `Dict` |

---

## 5. IMPLEMENTATION EXERCISES

> **Rule:** Implement each exercise completely and verify it works before moving to the next. Each exercise builds on the previous one.

---

### Exercise 5.1: Utility Foundation (No MongoDB)

**Concept:** Pure Python logic - bcrypt hashing, JWT tokens, regex validation
**Difficulty:** Warm-up
**Why this matters:** Every authentication flow depends on these utilities. Get them right first.

#### Implement these 6 methods:

**5.1.1 - `generate_verification_token(self, user_id: str, email: str) -> str`**

Create a JWT token for email verification.

Requirements:
- Payload must contain: `user_id`, `email`, `type` (set to `"email_verification"`), `exp` (6 hours from now)
- Use `JWT_SECRET` and `JWT_ALGORITHM` constants defined at module level
- Use `utc_now()` from datetime_utils for the current time

**5.1.2 - `generate_reset_token(self, user_id: str, email: str) -> str`**

Create a JWT token for password reset.

Requirements:
- Same as verification token but: `type` = `"password_reset"`, `exp` = 1 hour from now

**5.1.3 - `verify_token(self, token: str, token_type: str) -> Dict[str, Any]`**

Decode and validate a JWT token.

Requirements:
- Decode the token using `jwt.decode()` with `JWT_SECRET` and `[JWT_ALGORITHM]`
- Verify the `type` field in the payload matches `token_type` parameter
- Return the decoded payload dict
- Raise `ValueError("Invalid token type")` if type doesn't match
- Raise `ValueError("Token has expired")` for `jwt.ExpiredSignatureError`
- Raise `ValueError("Invalid token")` for `jwt.InvalidTokenError`

**5.1.4 - `hash_password(self, password: str) -> str`**

Hash a password using bcrypt.

Requirements:
- Generate a salt with `bcrypt.gensalt(rounds=12)`
- Hash using `bcrypt.hashpw()` - encode password to UTF-8 before hashing
- Return the hash as a string (decode from bytes)

**5.1.5 - `verify_password(self, password: str, password_hash: str) -> bool`**

Verify a password against its hash.

Requirements:
- Use `bcrypt.checkpw()` - encode both password and hash to UTF-8
- Return the boolean result

**5.1.6 - `validate_password(self, password: str, email: str) -> None`**

Validate password meets security requirements.

Requirements:
- Check length: must be between `self.password_min_length` (8) and `self.password_max_length` (128)
- Check pattern: must match `self.password_pattern` (at least 1 uppercase, 1 lowercase, 1 digit)
- Check email leak: password cannot contain the email username (part before `@`, case-insensitive)
- Raise `ValueError` with descriptive message for each failure
- Return `None` if password is valid (no return value needed)

#### Verify Exercise 5.1

Test in Python shell:
```python
auth = AuthService()

# Test password hashing
hashed = auth.hash_password("MyPass123")
assert auth.verify_password("MyPass123", hashed) == True
assert auth.verify_password("WrongPass", hashed) == False

# Test password validation
auth.validate_password("MyPass123", "user@example.com")  # Should pass
# auth.validate_password("short", "user@example.com")    # Should raise ValueError
# auth.validate_password("nouppercase1", "u@e.com")      # Should raise ValueError

# Test token generation
token = auth.generate_verification_token("user123", "test@example.com")
payload = auth.verify_token(token, "email_verification")
assert payload["user_id"] == "user123"
assert payload["email"] == "test@example.com"
```

---

### Exercise 5.2: Your First MongoDB Query - Email Availability

**Concept:** `find_one()` with nested field match + array field match
**Difficulty:** Easy
**Why this matters:** Before creating any user, we must ensure email uniqueness. This is your first real MongoDB query.

#### Implement: `is_email_available(self, email: str) -> bool`

**Business Rules:**
1. Normalize the email: lowercase and strip whitespace
2. Check if the email is used as ANY user's **primary email**
3. Check if the email is used as ANY user's **additional email**
4. Return `True` only if neither check finds a match

**The MongoDB Queries You Need:**

Query 1 - Check primary email:
```
Find ONE document in the users collection where
the nested field contact_info.primary_email equals the given email
```

Query 2 - Check additional emails:
```
Find ONE document in the users collection where
the array field contact_info.additional_emails contains the given email
```

**Error handling:**
- Wrap in try/except
- Re-raise any exception as `Exception(f"Failed to check email availability: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Beanie provides `ModelClass.find_one(filter_dict)` which maps directly to MongoDB's `findOne()`. For nested fields, use dot notation in the filter key. For array fields, MongoDB automatically checks if the value exists anywhere in the array.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Nested field query (dot notation):
user = await User.find_one({"contact_info.primary_email": email})

# Array field query (automatic $in-like behavior):
user = await User.find_one({"contact_info.additional_emails": email})
```

MongoDB automatically searches arrays when you query a field that contains an array. You don't need `$in` or `$elemMatch` for simple equality matches.

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def is_email_available(self, email: str) -> bool:
    try:
        email = email.lower().strip()

        # Check primary email (uses index: contact_info.primary_email)
        user = await User.find_one({"contact_info.primary_email": email})
        if user:
            return False

        # Check additional emails (uses index: contact_info.additional_emails)
        user = await User.find_one({"contact_info.additional_emails": email})
        if user:
            return False

        return True
    except Exception as e:
        raise Exception(f"Failed to check email availability: {str(e)}")
```

</details>

#### Verify Exercise 5.2

With an empty database, this should return `True`:
```bash
# You can test this via the register endpoint later,
# or test directly in a Python shell:
# await auth_service.is_email_available("new@example.com")  → True
```

#### Index Checkpoint

**Question:** Which indexes from the User model support the two queries in this method?

<details>
<summary>Answer</summary>

1. `contact_info.primary_email` index (line 213) - supports the primary email lookup
2. `contact_info.additional_emails` index (line 219) - supports the additional emails lookup

Both queries are O(log n) thanks to these indexes. Without them, MongoDB would scan every document in the collection.

</details>

---

### Exercise 5.3: Your First Write - Register Consumer

**Concept:** Document construction with embedded objects + `insert()`
**Difficulty:** Easy-Medium
**Why this matters:** This is how users enter the platform. You'll build a complete `User` document from scratch and persist it to MongoDB.

#### Implement: `register_consumer(self, email: str, password: str, display_name: str) -> Dict[str, Any]`

**Business Rules (implement in this order):**
1. Normalize inputs: `email.lower().strip()`, `display_name.strip()`
2. Check email availability using your `is_email_available()` method
   - If not available → raise `ValueError("Email already in use")`
3. Validate password using your `validate_password()` method
   - It raises ValueError internally if invalid
4. Build the User document:
   - `password_hash`: hash the password
   - `contact_info`: create `ContactInfo` with `primary_email=email`
   - `profile`: create `UserProfile` with `display_name=display_name`
   - All other fields use their defaults (role=consumer, status=pending, etc.)
5. Insert the document into MongoDB
6. Emit a Kafka event (topic: `Topic.USER`, action: `"registered"`)
7. Generate a verification token
8. Return the result dict

**The MongoDB Operation:**

```
INSERT a new User document into the "users" collection
```

**Return format** (the route expects exactly this structure):
```python
{
    "user": {
        "id": "string (the MongoDB ObjectId as string)",
        "email": "the primary email",
        "display_name": "the display name",
        "role": "consumer",
        "status": "pending"
    },
    "verification_token": "the JWT token string"
}
```

**Error handling:**
- `ValueError` → re-raise as-is
- Any other exception → raise `Exception(f"Failed to register consumer: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

In Beanie, you construct a document by instantiating the model class, then call `await document.insert()` to persist it. The `id` field is auto-generated by MongoDB after insert.

Use `oid_to_str(user.id)` to convert the ObjectId to a string for the response.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Document construction:
user = User(
    password_hash=self.hash_password(password),
    contact_info=ContactInfo(primary_email=email),
    profile=UserProfile(display_name=display_name)
    # role, permissions, stats, security all use defaults from the model
)

# Insert:
await user.insert()

# After insert, user.id is populated by MongoDB
user_id = oid_to_str(user.id)  # "507f1f77bcf86cd799439011"
```

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def register_consumer(self, email, password, display_name):
    try:
        email = email.lower().strip()
        display_name = display_name.strip()

        if not await self.is_email_available(email):
            raise ValueError("Email already in use")

        self.validate_password(password, email)

        user = User(
            password_hash=self.hash_password(password),
            contact_info=ContactInfo(primary_email=email),
            profile=UserProfile(display_name=display_name)
        )
        await user.insert()

        user_id = oid_to_str(user.id)

        self._kafka.emit(
            topic=Topic.USER,
            action="registered",
            entity_id=user_id,
            data=user.model_dump(mode="json"),
        )

        verification_token = self.generate_verification_token(user_id, email)

        return {
            "user": {
                "id": user_id,
                "email": user.contact_info.primary_email,
                "display_name": user.profile.display_name,
                "role": user.role.value,
                "status": user.status.value
            },
            "verification_token": verification_token
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to register consumer: {str(e)}")
```

</details>

#### Verify Exercise 5.3

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass",
    "display_name": "Test Consumer"
  }'
```

**Expected response (201 Created):**
```json
{
  "user": {
    "id": "<some-object-id>",
    "email": "consumer@example.com",
    "display_name": "Test Consumer",
    "role": "consumer",
    "status": "pending",
    "avatar": null,
    "permissions": null
  },
  "message": "Registration successful. Verification email sent to consumer@example.com",
  "verification_token": "<jwt-token>"
}
```

**Test duplicate email (400 Bad Request):**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass",
    "display_name": "Duplicate User"
  }'
```

**Verify in MongoDB shell:**
```javascript
db.users.findOne({"contact_info.primary_email": "consumer@example.com"})
```
You should see the full document with all default fields populated.

---

### Exercise 5.4: Complex Embedded Documents - Register Leader

**Concept:** Building deeply nested embedded documents + `insert()`
**Difficulty:** Medium
**Why this matters:** Leaders are the heart of the platform - they create communities, curate products, and drive engagement. Their registration requires business information, which means you'll build a 4-level deep document structure.

#### Implement: `register_leader(self, email, password, display_name, company_name, business_type, country, city, zip_code, website=None, state=None, street_address=None) -> Dict[str, Any]`

**Business Rules (implement in this order):**
1. Normalize inputs: email lowercase + strip, display_name strip
2. Check email availability → `ValueError("Email already in use")`
3. Validate password
4. Validate business_type - must be one of: `"personal_brand"`, `"company"`, `"agency"`
   - If not → raise `ValueError("Invalid business type")`
5. Build the nested document structure:
   - `BusinessAddress` → embedded in `CelebrityBusinessInfo` → embedded in `UserProfile` → embedded in `User`
   - State defaults to `"N/A"` if not provided
6. Create User with `role=UserRole.LEADER`
7. Insert, emit Kafka event, generate token
8. Return result with business_info in the user dict

**The Nesting Depth:**

```
User
└── profile: UserProfile
    └── celebrity_business_info: CelebrityBusinessInfo
        ├── business_name: "Acme Inc"
        ├── business_type: "company"
        ├── website: "https://acme.com"
        └── address: BusinessAddress
            ├── street: "123 Main St"
            ├── city: "Los Angeles"
            ├── state: "CA"
            ├── zip_code: "90001"
            └── country: "US"
```

**Return format:**
```python
{
    "user": {
        "id": "string",
        "email": "string",
        "display_name": "string",
        "role": "leader",
        "status": "pending",
        "business_info": {
            "company_name": "string",
            "business_type": "string"
        }
    },
    "verification_token": "string"
}
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Build from the inside out: first `BusinessAddress`, then `CelebrityBusinessInfo` (which contains the address), then `UserProfile` (which contains the business info), then `User` (which contains the profile). Set `role=UserRole.LEADER` on the User.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
celebrity_business_info = CelebrityBusinessInfo(
    business_name=company_name,
    business_type=business_type,
    address=BusinessAddress(
        street=street_address,
        city=city,
        state=state or "N/A",
        zip_code=zip_code,
        country=country
    ),
    website=website
)

user = User(
    password_hash=self.hash_password(password),
    contact_info=ContactInfo(primary_email=email),
    profile=UserProfile(
        display_name=display_name,
        celebrity_business_info=celebrity_business_info
    ),
    role=UserRole.LEADER
)
```

</details>

#### Verify Exercise 5.4

```bash
curl -X POST http://localhost:8000/auth/register/leader \
  -H "Content-Type: application/json" \
  -d '{
    "email": "leader@example.com",
    "password": "LeaderPass1",
    "display_name": "Famous Leader",
    "company_name": "Leader Brand Inc",
    "business_type": "personal_brand",
    "country": "US",
    "city": "Los Angeles",
    "zip_code": "90001",
    "state": "CA",
    "website": "https://famous-leader.com"
  }'
```

**Expected response (201 Created):**
```json
{
  "user": {
    "id": "<object-id>",
    "email": "leader@example.com",
    "display_name": "Famous Leader",
    "role": "leader",
    "status": "pending",
    "avatar": null,
    "permissions": null
  },
  "message": "Leader registration submitted. Verification email sent to leader@example.com. Your application will be reviewed by our team.",
  "verification_token": "<jwt-token>"
}
```

**Verify the nested structure in MongoDB shell:**
```javascript
db.users.findOne(
  {"contact_info.primary_email": "leader@example.com"},
  {"profile.celebrity_business_info": 1}
)
```

You should see the complete `celebrity_business_info` with the nested `address` object.

---

### Exercise 5.5: The Login Flow - Find, Validate, Update

**Concept:** `find_one()` with conditional reads + multiple `save()` paths
**Difficulty:** Medium-High
**Why this matters:** Login is the most complex authentication operation. It combines reading, validating, and conditionally writing back to the database - all in a single method. This is the "find → check → act" pattern you'll use everywhere.

#### Implement: `login(self, email: str, password: str, ip_address: str) -> Dict[str, Any]`

**This is the most important method in this task.** It has 6 distinct phases:

#### Phase 1: Find the user
- Normalize email (lowercase, strip)
- Query: find one user by `contact_info.primary_email`
- If not found → raise `ValueError("Invalid email or password")`

> **Security note:** We say "Invalid email or password" (not "Email not found") to prevent email enumeration attacks.

#### Phase 2: Check account status
In this exact order:
1. If `user.deleted_at is not None` → raise `ValueError("Account no longer exists")`
2. If `user.status == UserStatus.SUSPENDED` → raise `ValueError("Account suspended. Contact support.")`

#### Phase 3: Check account lock
- If `user.security.locked_until` is not None:
  - If lock is still active (`utc_now() < user.security.locked_until`):
    - Calculate remaining minutes: `int((locked_until - utc_now()).total_seconds() / 60)`
    - Raise `ValueError(f"Account locked. Try again in {remaining} minutes")`
  - If lock has expired:
    - Reset: `locked_until = None`, `failed_login_attempts = 0`
    - `await user.save()`

#### Phase 4: Verify password
- Use `self.verify_password(password, user.password_hash)`
- If password is WRONG:
  - Increment `user.security.failed_login_attempts += 1`
  - If attempts >= `self.max_failed_attempts` (5):
    - Set `user.security.locked_until` to now + lock_duration_minutes
    - `await user.save()`
    - Emit Kafka event: topic=`Topic.USER`, action=`"account_locked"`
    - Raise `ValueError(f"Too many failed attempts. Account locked for {self.lock_duration_minutes} minutes")`
  - Otherwise:
    - `await user.save()` (to persist the incremented counter)
    - Raise `ValueError("Invalid email or password")`

#### Phase 5: Record successful login
- Call `await user.record_successful_login(ip_address)` (model helper method)
- Emit Kafka event: topic=`Topic.USER`, action=`"login"`

#### Phase 6: Return user data
```python
{
    "id": user_id,
    "email": user.contact_info.primary_email,
    "display_name": user.profile.display_name,
    "avatar": user.profile.avatar,
    "role": user.role.value,
    "status": user.status.value,
    "permissions": {
        "can_post": user.permissions.can_post,
        "can_comment": user.permissions.can_comment,
        "can_manage_communities": user.permissions.can_manage_communities,
        "can_create_promotions": user.permissions.can_create_promotions
    }
}
```

**Error handling:**
- `ValueError` → re-raise
- Any other → raise `Exception(f"Failed to login: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The key MongoDB operation is the initial `find_one`. Everything after that is Python logic operating on the returned document object. When you modify fields on the user object and call `save()`, Beanie sends an update to MongoDB replacing the document.

The `record_successful_login()` helper method on the model already handles resetting `failed_login_attempts` and updating `last_login_at`/`last_login_ip` + calling `save()`.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Phase 1: Find
user = await User.find_one({"contact_info.primary_email": email})
if not user:
    raise ValueError("Invalid email or password")

# Phase 3: Lock check
if user.security.locked_until:
    if utc_now() < user.security.locked_until:
        # Still locked...
    else:
        # Expired - reset and save
        user.security.locked_until = None
        user.security.failed_login_attempts = 0
        await user.save()

# Phase 4: Wrong password
if not self.verify_password(password, user.password_hash):
    user.security.failed_login_attempts += 1
    if user.security.failed_login_attempts >= self.max_failed_attempts:
        user.security.locked_until = utc_now() + timedelta(minutes=self.lock_duration_minutes)
        await user.save()
        # emit event...
        raise ValueError(...)
    await user.save()
    raise ValueError("Invalid email or password")
```

</details>

#### Verify Exercise 5.5

**Successful login** (use the consumer you registered in 5.3):
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass"
  }'
```

**Expected (200 OK):**
```json
{
  "user": {
    "id": "<object-id>",
    "email": "consumer@example.com",
    "display_name": "Test Consumer",
    "role": "consumer",
    "status": "pending",
    "avatar": "https://cdn.example.com/avatars/default.jpg",
    "permissions": {
      "can_post": true,
      "can_comment": true,
      "can_manage_communities": false,
      "can_create_promotions": false
    }
  }
}
```

**Wrong password (401):**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "WrongPassword1"
  }'
```

**Account locking test - send 5 wrong passwords:**
```bash
for i in {1..5}; do
  curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "consumer@example.com", "password": "Wrong'$i'Pass"}' | python3 -m json.tool
  echo "---"
done
```
The 5th attempt should return `429 Too Many Requests` with the lock message.

**Verify lock in MongoDB shell:**
```javascript
db.users.findOne(
  {"contact_info.primary_email": "consumer@example.com"},
  {"security": 1}
)
// security.locked_until should be set ~30 minutes in the future
// security.failed_login_attempts should be 5
```

---

### Exercise 5.6: Get By ID - Email Verification

**Concept:** `Document.get(ObjectId)` - fetching by `_id` vs querying by field
**Difficulty:** Medium
**Why this matters:** Login finds users by email (field query). Verification finds users by their ID embedded in the JWT token. These are fundamentally different MongoDB operations.

#### Implement: `verify_email(self, token: str) -> Dict[str, Any]`

**Business Rules:**
1. Verify the token using `self.verify_token(token, "email_verification")`
   - This returns a payload dict with `user_id` and `email`
2. Get the user by ID using `User.get(ObjectId(user_id))`
   - If not found → raise `ValueError("User not found")`
3. Set `user.contact_info.email_verified = True`
4. **Conditional status change:** If user is a CONSUMER, auto-activate them (`user.status = UserStatus.ACTIVE`)
   - Leaders stay PENDING (they need admin approval)
5. Save the user
6. Emit Kafka event: topic=`Topic.USER`, action=`"email_verified"`
7. Return result dict

**The MongoDB Operations:**

```
Operation 1: GET by _id  →  User.get(ObjectId("507f1f77bcf86cd799439011"))
Operation 2: SAVE        →  Updates the document in place
```

**Return format:**
```python
{
    "id": "string",
    "email": "string",
    "email_verified": True,
    "status": "active"  # or "pending" for leaders
}
```

**Key Distinction:**
```
find_one({"contact_info.primary_email": "x"})  ← Field query (uses index)
User.get(ObjectId("507f..."))                   ← _id lookup (uses primary key, always fastest)
```

`User.get()` is Beanie's wrapper around `find_one({"_id": ObjectId(...)})`. The `_id` field has a unique index by default in every MongoDB collection - you never need to define it.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

You need `from bson import ObjectId` to convert the string user_id from the token payload into a proper ObjectId for the query. `User.get()` expects an ObjectId, not a string.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
payload = self.verify_token(token, "email_verification")
user_id = payload.get("user_id")

user = await User.get(ObjectId(user_id))
if not user:
    raise ValueError("User not found")

user.contact_info.email_verified = True

if user.role == UserRole.CONSUMER:
    user.status = UserStatus.ACTIVE

await user.save()
```

</details>

#### Verify Exercise 5.6

Use the verification token from registration (Exercise 5.3):
```bash
# First, register a fresh user and capture the token:
RESPONSE=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "verify.me@example.com",
    "password": "VerifyMe1Pass",
    "display_name": "Verify Test"
  }')

TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['verification_token'])")

# Now verify:
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"
```

**Expected (200 OK):**
```json
{
  "id": "<object-id>",
  "email": "verify.me@example.com",
  "email_verified": true,
  "status": "active"
}
```

**Verify in MongoDB shell:**
```javascript
db.users.findOne(
  {"contact_info.primary_email": "verify.me@example.com"},
  {"contact_info.email_verified": 1, "status": 1}
)
// email_verified: true, status: "active"
```

---

### Exercise 5.7: Complete the Flow - Password Reset

**Concept:** Combining `find_one` + token generation + `get` by ID + multi-field update
**Difficulty:** Medium
**Why this matters:** Password reset touches every concept from previous exercises. It's your integration test.

#### Implement TWO methods:

**5.7.1 - `request_password_reset(self, email: str) -> Optional[str]`**

Request a password reset. Returns a reset token if the user exists, `None` otherwise.

**Business Rules:**
1. Normalize email (lowercase, strip)
2. Find user by primary email
3. If not found → return `None` (don't reveal whether email exists)
4. Emit Kafka event: topic=`Topic.USER`, action=`"password_reset_requested"`
5. Generate and return a reset token

**Security note:** The route always returns "If the email exists, a reset link has been sent" regardless of whether we found a user. This prevents email enumeration.

**5.7.2 - `reset_password(self, token: str, new_password: str) -> Dict[str, Any]`**

Complete the password reset using the token.

**Business Rules:**
1. Verify the token: `self.verify_token(token, "password_reset")`
2. Extract `user_id` and `email` from payload
3. Get user by ID: `User.get(ObjectId(user_id))`
   - If not found → raise `ValueError("User not found")`
4. Validate the new password: `self.validate_password(new_password, email)`
5. Update FOUR fields:
   - `user.password_hash` = hash of new password
   - `user.security.password_changed_at` = `utc_now()`
   - `user.security.failed_login_attempts` = `0`
   - `user.security.locked_until` = `None`
6. Save the user
7. Emit Kafka event: topic=`Topic.USER`, action=`"password_reset"`
8. Return `{"message": "Password reset successful"}`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

`request_password_reset` is essentially: find_one → if found, generate token. `reset_password` is: verify token → get by id → update fields → save. Both are combinations of patterns you've already implemented.

</details>

#### Verify Exercise 5.7

```bash
# Step 1: Request reset
curl -X POST http://localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "consumer@example.com"}'
# Response: {"message": "If the email exists, a password reset link has been sent"}

# Step 2: Use the token (in production this comes from email)
# For testing, call request_password_reset directly and use the token:

# Step 3: Reset with new password
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<paste-reset-token-here>",
    "new_password": "MyNewSecure1Pass"
  }'
# Response: {"message": "Password reset successful"}

# Step 4: Login with new password should work
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MyNewSecure1Pass"
  }'
# Response: 200 OK with user data
```

---

## 6. VERIFICATION CHECKLIST

Before moving to TASK_02, verify that ALL of the following pass:

### Functional Checks
- [ ] **Register consumer** - creates document with correct defaults
- [ ] **Register leader** - creates document with full `celebrity_business_info` nesting
- [ ] **Duplicate email rejected** - second registration with same email fails with 400
- [ ] **Login success** - returns user data with permissions
- [ ] **Login wrong password** - returns 401, increments `failed_login_attempts` in DB
- [ ] **Login account lock** - 5 wrong attempts locks account, returns 429
- [ ] **Login lock expiry** - after lock expires, user can attempt login again (failed_attempts resets)
- [ ] **Email verification** - flips `email_verified` to `true`, consumers become `active`
- [ ] **Leader verification** - flips `email_verified` to `true`, leaders stay `pending`
- [ ] **Password reset request** - returns token for existing user, `None` for non-existent
- [ ] **Password reset complete** - changes password, resets security fields

### Database Checks (MongoDB shell)
- [ ] `db.users.countDocuments()` - shows correct number of users created
- [ ] `db.users.getIndexes()` - shows all 6 indexes defined in model
- [ ] Consumer document has `role: "consumer"` and no `celebrity_business_info`
- [ ] Leader document has `role: "leader"` and full `celebrity_business_info` object
- [ ] After login: `security.last_login_at` is updated, `security.last_login_ip` is set
- [ ] After failed login: `security.failed_login_attempts` is incremented

### Code Quality Checks
- [ ] All methods have try/except error handling
- [ ] ValueError used for business logic errors (not generic Exception)
- [ ] Email normalized (lowercase, stripped) before every query
- [ ] Kafka events emitted for: register, login, account_locked, email_verified, password_reset_requested, password_reset
- [ ] No raw MongoDB queries - all operations use Beanie ODM

---

## 7. ADVANCED CHALLENGES

These are optional exercises that deepen your understanding. Attempt them after completing the main exercises.

### Challenge A: Query Execution Analysis

Open the MongoDB shell and run:
```javascript
db.users.find({"contact_info.primary_email": "consumer@example.com"}).explain("executionStats")
```

Answer these questions:
1. What is the `winningPlan.stage`? (Should be `IXSCAN`, not `COLLSCAN`)
2. How many `totalDocsExamined`? (Should be 1, not the total collection size)
3. What index was used? (Should be `contact_info.primary_email_1`)

Now try a query that does NOT have an index:
```javascript
db.users.find({"profile.display_name": "Test Consumer"}).explain("executionStats")
```

Compare:
- What's the `winningPlan.stage` now? (Should be `COLLSCAN` - full collection scan)
- How many `totalDocsExamined`? (Should be ALL documents)

**Takeaway:** Indexes are the difference between O(log n) and O(n) queries. Every query you write in this course should hit an index.

### Challenge B: Unique Index Behavior

The `contact_info.primary_email` index should ideally be unique. Currently it's a regular index. What happens if two users somehow get the same primary email?

Try this in MongoDB shell:
```javascript
// Insert a document directly (bypassing application logic)
db.users.insertOne({
  "contact_info": {"primary_email": "duplicate@test.com", "additional_emails": [], "email_verified": false},
  "password_hash": "fake",
  "role": "consumer",
  "status": "pending",
  "profile": {"display_name": "Dupe 1", "avatar": ""},
  "permissions": {},
  "stats": {},
  "security": {"failed_login_attempts": 0},
  "version": 1
})
// Insert another with the same email
db.users.insertOne({
  "contact_info": {"primary_email": "duplicate@test.com", "additional_emails": [], "email_verified": false},
  "password_hash": "fake",
  "role": "consumer",
  "status": "pending",
  "profile": {"display_name": "Dupe 2", "avatar": ""},
  "permissions": {},
  "stats": {},
  "security": {"failed_login_attempts": 0},
  "version": 1
})
```

Does MongoDB reject the second insert? Why or why not?

**Reflection:** How does the application currently prevent duplicates? (Answer: via `is_email_available()` check before insert). What's the weakness of this approach? (Answer: race condition - two requests could check simultaneously, both see the email is available, and both insert. A unique index would be the true safeguard.)

### Challenge C: The Soft Delete Gap

Look at the login method. When a user is soft-deleted (`deleted_at is not None`), we reject the login. But we find the user first with:
```python
User.find_one({"contact_info.primary_email": email})
```

This query does NOT filter by `deleted_at`. So we find deleted users, then check in Python. Is this efficient?

How would you change the query to filter deleted users at the database level?

<details>
<summary>Answer</summary>

```python
user = await User.find_one({
    "contact_info.primary_email": email,
    "deleted_at": None
})
```

This uses the `deleted_at` index and prevents loading deleted user documents into memory. However, the current approach has a UX benefit: we can show the specific error "Account no longer exists" instead of the generic "Invalid email or password". It's a tradeoff between efficiency and user experience.

</details>

---

## 8. WHAT'S NEXT

You've completed the foundation. You now understand:
- `find_one()` for field-based lookups
- `Document.get()` for `_id` lookups
- `document.insert()` for creating documents
- `document.save()` for updating documents
- Embedded document construction
- Which indexes support which queries

**TASK 02: Supplier Authentication** will build on these concepts with:
- Array field queries (`$elemMatch`)
- Deeper nesting (contact person, multiple addresses)
- Dual token strategy (access + refresh)
- Document submission workflows
- Stricter validation (10-char passwords, special characters required)

The patterns you learned here - find → validate → act → emit - will repeat in every service you build. Master them now.
