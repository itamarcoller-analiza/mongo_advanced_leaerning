# TASK 02: Supplier Authentication Service

## 1. MISSION BRIEFING

Suppliers are the **commerce engine** of the platform. While Users browse, like, and share - Suppliers stock the shelves. They are business entities (LLCs, corporations, sole proprietors) that list products, run promotions, and fulfill orders.

Suppliers are deliberately **separate from Users**. They cannot browse feeds, join communities, or follow leaders. They have their own authentication system, their own verification workflow, and their own set of capabilities.

### What You Will Build
The `SupplierAuthService` class - handling supplier registration, login with dual tokens, email verification, password reset, and document submission for business verification.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| Cross-collection queries | Checking email uniqueness across **both** `suppliers` AND `users` |
| Deep nested document construction | Building 3-level deep embedded objects |
| Multiple required embedded documents | Constructing `contact_info` + `company_info` + `business_info` + `verification` |
| Array field validation in queries | Checking `additional_emails` array |
| Get by ID + status-based update | Document submission workflow |
| Verification status queries | Querying `verification.verification_status` |

### How This Differs From TASK_01 (User)

| Aspect | User (TASK_01) | Supplier (TASK_02) |
|--------|---------------|-------------------|
| Password rules | 8+ chars, upper+lower+digit | **10+ chars, upper+lower+digit+special** |
| Token strategy | Single verification/reset | **Dual tokens: access (30m) + refresh (7d)** |
| Registration fields | 3 fields (email, password, name) | **18 fields** across 5 embedded objects |
| Email check scope | Users only | **Suppliers + Users** (cross-collection) |
| Login response | User data only | **Tokens + supplier data** |
| Extra workflow | None | **Document submission for verification** |
| Status checks on login | `deleted_at`, `status == SUSPENDED` | `deleted_at`, `status == DELETED`, **`status == SUSPENDED`** |
| Token payload key | `user_id` | `supplier_id` |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Supplier email check crosses into the Users collection
- MongoDB running locally
- Familiarity with Beanie ODM patterns from TASK_01

### Files You MUST Read Before Coding

#### Step 1: The Model (the data)
```
shared/models/supplier.py
```
This is a MUCH larger model than User. Pay attention to:
- 8 embedded document classes (lines 59-233) before the main `Supplier` class
- The `Supplier` class has 14 top-level fields (line 237)
- 7 indexes (line 298) - notably the `tax_id` and `verification_status` indexes
- Helper methods include `is_verified()`, `can_create_product()`, `can_create_promotion()`

#### Step 2: The Schema (the API contract)
```
apps/backend-service/src/schemas/supplier_auth.py
```
Notice the registration request has **18 fields** - far more than User's 3.

#### Step 3: The Route (who calls you)
```
apps/backend-service/src/routes/supplier_auth.py
```
Key differences from User routes:
- Line 50-53: Registration returns `next_steps` list to guide the supplier
- Line 96: Login returns the full `LoginSupplierResponse` (tokens + supplier data)
- Line 229: `submit-documents` endpoint has a TODO for authentication

#### Step 4: The Utilities (same as TASK_01)
```
apps/backend-service/src/utils/datetime_utils.py    → utc_now()
apps/backend-service/src/utils/serialization.py     → oid_to_str()
apps/backend-service/src/kafka/producer.py          → KafkaProducer.emit()
apps/backend-service/src/kafka/topics.py            → Topic.SUPPLIER
```

---

## 3. MODEL DEEP DIVE

### The Supplier Document Structure

A Supplier document in MongoDB is significantly larger than a User document. Here's the full shape:

```json
{
  "_id": ObjectId("..."),
  "password_hash": "$2b$12$...",

  "contact_info": {
    "primary_email": "supplier@acme.com",
    "additional_emails": ["orders@acme.com", "support@acme.com"],
    "primary_phone": "+1-555-0100",
    "additional_phones": ["+1-555-0101"],
    "fax": null,
    "contact_person_name": "John Doe",
    "contact_person_title": "Sales Director",
    "contact_person_email": "john@acme.com",
    "contact_person_phone": "+1-555-0102"
  },

  "company_info": {
    "legal_name": "Acme Corporation",
    "dba_name": "Acme Goods",
    "company_type": "corporation",
    "tax_id": "12-3456789",
    "tax_id_country": "US",
    "registration_number": null,
    "registration_date": null,
    "registration_state": null,
    "business_address": {
      "street_address_1": "100 Commerce Blvd",
      "street_address_2": "Suite 400",
      "city": "New York",
      "state": "NY",
      "zip_code": "10001",
      "country": "US"
    },
    "shipping_address": null,
    "billing_address": null
  },

  "business_info": {
    "industry_category": "electronics",
    "industry_tags": [],
    "website": "https://acme.com",
    "logo": null,
    "description": "Leading electronics manufacturer...",
    "facebook_url": null,
    "instagram_handle": null,
    "twitter_handle": null,
    "linkedin_url": null,
    "business_hours": null,
    "timezone": null,
    "support_email": null,
    "support_phone": null
  },

  "verification": {
    "verification_status": "pending",
    "verified_at": null,
    "verified_by": null,
    "rejected_at": null,
    "rejected_by": null,
    "rejection_reason": null,
    "submitted_documents": [],
    "terms_accepted": true,
    "terms_accepted_at": "2025-01-15T10:30:00Z",
    "privacy_policy_accepted": true
  },

  "banking_info": null,

  "permissions": {
    "can_create_products": true,
    "can_create_promotions": true,
    "can_access_analytics": true,
    "max_products": 1000,
    "max_active_promotions": 50,
    "max_images_per_product": 10
  },

  "stats": {
    "product_count": 0,
    "active_product_count": 0,
    "promotion_count": 0,
    "active_promotion_count": 0,
    "total_sales_cents": 0,
    "total_orders": 0,
    "average_rating": 0.0,
    "total_reviews": 0
  },

  "security": {
    "last_login_at": null,
    "last_login_ip": null,
    "failed_login_attempts": 0,
    "locked_until": null,
    "password_changed_at": "2025-01-15T10:30:00Z"
  },

  "product_ids": [],
  "status": "active",
  "deleted_at": null,
  "version": 1,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Embedded Documents Hierarchy

```
Supplier (Document → stored in "suppliers" collection)
├── password_hash (str)
├── contact_info (SupplierContactInfo)
│   ├── primary_email (EmailStr)              ← LOGIN KEY
│   ├── additional_emails (List[EmailStr])    ← CHECKED FOR EMAIL UNIQUENESS
│   ├── primary_phone (str)
│   ├── additional_phones (List[str])
│   ├── fax (Optional[str])
│   ├── contact_person_name (Optional[str])   ← WHO TO REACH
│   ├── contact_person_title (Optional[str])
│   ├── contact_person_email (Optional[EmailStr])
│   └── contact_person_phone (Optional[str])
├── company_info (CompanyInfo)
│   ├── legal_name (str)                      ← OFFICIAL COMPANY NAME
│   ├── dba_name (Optional[str])              ← "DOING BUSINESS AS"
│   ├── company_type (CompanyType enum)
│   ├── tax_id (str)                          ← HAS ITS OWN INDEX
│   ├── tax_id_country (str)
│   ├── registration_number, date, state
│   ├── business_address (CompanyAddress)      ← REQUIRED
│   │   ├── street_address_1 (str)
│   │   ├── street_address_2 (Optional[str])   ← User had single "street"
│   │   ├── city, state, zip_code, country
│   ├── shipping_address (Optional[CompanyAddress])
│   └── billing_address (Optional[CompanyAddress])
├── business_info (BusinessInfo)
│   ├── industry_category (IndustryCategory enum)  ← HAS INDEX
│   ├── industry_tags (List[str])
│   ├── website, logo, description
│   ├── facebook_url, instagram_handle, twitter_handle, linkedin_url
│   ├── business_hours, timezone
│   └── support_email, support_phone
├── verification (VerificationInfo)
│   ├── verification_status (VerificationStatus: "pending"|"verified"|"rejected")
│   ├── verified_at, verified_by
│   ├── rejected_at, rejected_by, rejection_reason
│   ├── submitted_documents (List[str])        ← POPULATED IN EXERCISE 5.7
│   ├── terms_accepted (bool)
│   ├── terms_accepted_at (Optional[datetime])
│   └── privacy_policy_accepted (bool)
├── banking_info (Optional[BankingInfo])       ← ADDED LATER, NOT IN REGISTRATION
├── permissions (SupplierPermissions)
├── stats (SupplierStats)
├── security (SecurityInfo)                    ← SAME PATTERN AS USER
├── product_ids (List[PydanticObjectId])       ← POPULATED BY PRODUCT SERVICE LATER
├── status (SupplierStatus: "active"|"suspended"|"deleted")
├── deleted_at, version, created_at, updated_at
```

### Index Analysis

| Index | Fields | Purpose | Your Methods Using It |
|-------|--------|---------|----------------------|
| Email lookup | `contact_info.primary_email` | Login, email check | `is_email_available()`, `login()`, `request_password_reset()` |
| Verification + status | `verification.verification_status` + `status` | Admin review queue | Not in this task (admin panel) |
| Industry + status | `business_info.industry_category` + `status` | Supplier discovery | Not in this task |
| Business location | `company_info.business_address.country` + `state` + `city` | Geo lookup | Not in this task |
| Top sellers | `stats.total_sales_cents` (desc) + `status` | Leaderboard | Not in this task |
| Soft delete | `deleted_at` | Filter deleted | Implicit in queries |
| Tax ID | `company_info.tax_id` | Compliance lookup | Not in this task |

> **Key insight:** Notice `company_info.business_address.country` - that's a **3-level deep** nested field in an index. MongoDB supports dot notation at any nesting depth.

### Helper Methods Already Available

```python
supplier.is_active()                          # status == ACTIVE and not deleted
supplier.is_verified()                        # verification_status == VERIFIED
supplier.can_create_product()                 # active + verified + within limits
supplier.can_create_promotion()               # active + verified + within limits
supplier.is_account_locked()                  # locked_until > now
supplier.get_primary_email()                  # returns primary email
supplier.get_all_emails()                     # [primary] + additional
supplier.get_display_name()                   # dba_name or legal_name
await supplier.record_successful_login(ip)    # updates security fields + save()
await supplier.increment_failed_login()       # counter + lock at 5 + save()
await supplier.lock_account(minutes=30)       # sets locked_until + save()
await supplier.verify_supplier(verified_by)   # sets VERIFIED + timestamp
await supplier.reject_supplier(by, reason)    # sets REJECTED + reason
await supplier.soft_delete()                  # sets deleted_at + DELETED status
```

---

## 4. THE SERVICE CONTRACT

### Class Setup

```python
class SupplierAuthService:
    def __init__(self):
        self.password_min_length = 10          # Stricter: 10 vs User's 8
        self.password_max_length = 128
        self.max_failed_attempts = 5
        self.lock_duration_minutes = 30
        self._kafka = get_kafka_producer()
        # Pattern now requires special char (!@#$%^&*) - User doesn't
        self.password_pattern = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).+$'
        )
```

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `generate_verification_token(supplier_id, email)` | None | `str` (JWT) |
| 2 | `generate_reset_token(supplier_id, email)` | None | `str` (JWT) |
| 3 | `verify_token(token, token_type)` | None | `Dict` (payload) |
| 4 | `generate_access_token(supplier)` | None | `str` (JWT) |
| 5 | `generate_refresh_token(supplier)` | None | `str` (JWT) |
| 6 | `hash_password(password)` | None | `str` |
| 7 | `verify_password(password, hash)` | None | `bool` |
| 8 | `validate_password(password, email)` | None | `None` (raises) |
| 9 | `is_email_available(email)` | `find_one` x4 (2 collections!) | `bool` |
| 10 | `register_supplier(18 params...)` | `insert` | `Dict` |
| 11 | `login(email, password, ip)` | `find_one` + `save` | `Dict` |
| 12 | `verify_email(token)` | `get` + `save` | `Dict` |
| 13 | `request_password_reset(email)` | `find_one` | `Optional[str]` |
| 14 | `reset_password(token, new_password)` | `get` + `save` | `Dict` |
| 15 | `submit_verification_documents(supplier_id, documents)` | `get` + `save` | `Dict` |

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Utility Foundation - Stricter Rules & Dual Tokens

**Concept:** Password validation with special character requirement + dual JWT token strategy
**Difficulty:** Warm-up
**What's new from TASK_01:** Special character requirement in password, access/refresh token pair

#### Implement these 8 methods:

**5.1.1 through 5.1.3 - Token utilities (same pattern as TASK_01, different values)**

- `generate_verification_token(supplier_id, email)` → payload key is `"supplier_id"` (not `"user_id"`), type is `"supplier_email_verification"`, 6h expiry
- `generate_reset_token(supplier_id, email)` → type is `"supplier_password_reset"`, 1h expiry
- `verify_token(token, token_type)` → identical pattern to TASK_01

**5.1.4 - `generate_access_token(self, supplier: Supplier) -> str`** *(NEW)*

This is the first of the **dual token strategy**. Access tokens are short-lived and carry permissions.

Requirements:
- Payload must contain:
  - `sub`: `str(supplier.id)` - the subject (who this token is for)
  - `email`: `supplier.contact_info.primary_email`
  - `company_name`: `supplier.company_info.legal_name`
  - `type`: `"supplier_access"`
  - `verification_status`: `supplier.verification.verification_status.value`
  - `status`: `supplier.status.value`
  - `iat`: `int(utc_now().timestamp())` - issued at (epoch seconds)
  - `exp`: `int((utc_now() + timedelta(minutes=30)).timestamp())` - 30 minute expiry
- Return `jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)`

**5.1.5 - `generate_refresh_token(self, supplier: Supplier) -> str`** *(NEW)*

The refresh token is long-lived but carries minimal data (security principle: less data = less risk if stolen).

Requirements:
- Payload must contain:
  - `sub`: `str(supplier.id)`
  - `type`: `"supplier_refresh"`
  - `iat`: `int(utc_now().timestamp())`
  - `exp`: `int((utc_now() + timedelta(days=7)).timestamp())` - **7 day** expiry
- Return encoded JWT

> **Why dual tokens?** The access token (30 min) is sent with every API request. If stolen, damage is limited to 30 minutes. The refresh token (7 days) is stored securely and only used to get new access tokens. This separation limits the blast radius of token theft.

**5.1.6 through 5.1.8 - Password utilities (stricter than TASK_01)**

- `hash_password(password)` → identical to TASK_01
- `verify_password(password, hash)` → identical to TASK_01
- `validate_password(password, email)` → **DIFFERENT from TASK_01:**
  - Min length is `10` (not 8)
  - Pattern requires special character `(!@#$%^&*)` in addition to upper+lower+digit
  - Error message: `"Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character (!@#$%^&*)"`
  - Same email username check

#### Verify Exercise 5.1

```python
svc = SupplierAuthService()

# Password: must have special char
svc.validate_password("MyPass123!", "test@acme.com")  # OK
# svc.validate_password("MyPass123", "test@acme.com")  # Raises - no special char
# svc.validate_password("Short1!", "t@a.com")          # Raises - only 7 chars (need 10)

# Dual tokens should have different expiry and type
from shared.models.supplier import Supplier  # mock needed for this test
```

---

### Exercise 5.2: Cross-Collection Email Check

**Concept:** Querying TWO different collections in a single method
**Difficulty:** Easy-Medium
**What's new from TASK_01:** You now query **both** the `suppliers` collection AND the `users` collection. This is a cross-collection uniqueness check.

#### Implement: `is_email_available(self, email: str) -> bool`

**Business Rules:**
1. Normalize email (lowercase, strip)
2. Check suppliers - primary email: `Supplier.find_one({"contact_info.primary_email": email})`
3. Check suppliers - additional emails: `Supplier.find_one({"contact_info.additional_emails": email})`
4. Check users - primary email: `User.find_one({"contact_info.primary_email": email})`
5. Return `False` if ANY check finds a match, `True` otherwise

**The MongoDB Queries:**
```
Query 1: suppliers.findOne({"contact_info.primary_email": email})
Query 2: suppliers.findOne({"contact_info.additional_emails": email})
Query 3: users.findOne({"contact_info.primary_email": email})   ← CROSS-COLLECTION
```

> **Why cross-collection?** Imagine a supplier registers with `john@acme.com`, and a user also registers with `john@acme.com`. When `john@acme.com` tries to log in as a supplier, we find the supplier. When they try to log in as a user, we find the user. Same email, two accounts. This causes confusion and potential security issues. By checking both collections, we ensure global email uniqueness.

**Import required:**
```python
from shared.models.user import User  # Needed for cross-collection check
```

**Error handling:**
- Wrap in try/except
- Re-raise as `Exception(f"Failed to check email availability: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This is the same `find_one` pattern from TASK_01, just called three times on two different model classes. Beanie routes each query to the correct MongoDB collection based on the model's `Settings.name`.

`Supplier.find_one(...)` queries the `suppliers` collection.
`User.find_one(...)` queries the `users` collection.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
async def is_email_available(self, email: str) -> bool:
    try:
        email = email.lower().strip()

        # Check suppliers (primary)
        supplier = await Supplier.find_one({"contact_info.primary_email": email})
        if supplier:
            return False

        # Check suppliers (additional)
        supplier = await Supplier.find_one({"contact_info.additional_emails": email})
        if supplier:
            return False

        # Check users (cross-collection)
        from shared.models.user import User
        user = await User.find_one({"contact_info.primary_email": email})
        if user:
            return False

        return True
    except Exception as e:
        raise Exception(f"Failed to check email availability: {str(e)}")
```

</details>

<details>
<summary><b>Hint Level 3</b> - Complete solution</summary>

The Hint Level 2 IS the complete solution for this method. The key learning point is the cross-collection pattern: using different Beanie model classes to query different MongoDB collections within the same method.

</details>

#### Verify Exercise 5.2

After completing TASK_01, you should have users in the `users` collection:
```bash
# This email was registered as a User in TASK_01
# Supplier email check should also catch it:
# await svc.is_email_available("consumer@example.com")  → False (found in users)
# await svc.is_email_available("brand-new@acme.com")    → True  (not in either)
```

#### Cross-Collection Checkpoint

**Question:** How does Beanie know which MongoDB collection to query?

<details>
<summary>Answer</summary>

Each Beanie `Document` class has an inner `Settings` class with a `name` attribute:
- `User.Settings.name = "users"` → queries the `users` collection
- `Supplier.Settings.name = "suppliers"` → queries the `suppliers` collection

When you call `User.find_one(...)`, Beanie translates it to `db.users.findOne(...)`. When you call `Supplier.find_one(...)`, it becomes `db.suppliers.findOne(...)`. Same syntax, different collections.

</details>

---

### Exercise 5.3: Register Supplier - The Big Build

**Concept:** Constructing a document with 5 required embedded objects at multiple nesting depths
**Difficulty:** Medium-High
**What's new from TASK_01:** User registration took 3 parameters. Supplier registration takes **18**. You must build 4 embedded objects and wire them together.

#### Implement: `register_supplier(self, primary_email, phone, contact_person_name, contact_person_title, legal_name, company_type, tax_id, tax_id_country, street_address, city, state, zip_code, country, industry_category, description, website, password, terms_accepted, privacy_policy_accepted) -> Dict[str, Any]`

**Business Rules (implement in this exact order):**

1. **Normalize inputs:**
   - `primary_email.lower().strip()`
   - `contact_person_name.strip()`
   - `legal_name.strip()`

2. **Validate terms acceptance:**
   - If `not terms_accepted` → `ValueError("You must accept the Terms of Service to register")`
   - If `not privacy_policy_accepted` → `ValueError("You must accept the Privacy Policy to register")`

3. **Check email availability:**
   - Use `self.is_email_available(primary_email)`
   - If not available → `ValueError("Email already in use")`

4. **Validate password:**
   - `self.validate_password(password, primary_email)`

5. **Validate company type:**
   - Must be one of: `["corporation", "llc", "partnership", "sole_proprietorship"]`
   - If not → `ValueError(f"Invalid company type. Must be one of: {', '.join(valid_types)}")`

6. **Validate country codes:**
   - Both `tax_id_country` and `country` must be exactly 2 characters
   - If not → `ValueError("Country codes must be 2-letter ISO codes")`

7. **Build the document** (inside → out):

```
Step A: Build CompanyAddress
    └── street_address_1, city, state (default "N/A"), zip_code, country

Step B: Build SupplierContactInfo
    └── primary_email, primary_phone, contact_person_name, title, email

Step C: Build CompanyInfo
    └── legal_name, company_type, tax_id, tax_id_country, business_address (from A)

Step D: Build BusinessInfo
    └── industry_category, description, website

Step E: Build VerificationInfo
    └── terms_accepted=True, terms_accepted_at=utc_now(), privacy_policy_accepted=True

Step F: Build Supplier
    └── password_hash, contact_info (B), company_info (C), business_info (D), verification (E)
```

8. **Insert the document:**
   - `await supplier.insert()`

9. **Emit Kafka event:**
   - topic=`Topic.SUPPLIER`, action=`"registered"`, data=full supplier dump

10. **Generate verification token**

11. **Return result:**
```python
{
    "supplier": {
        "id": supplier_id,
        "email": supplier.contact_info.primary_email,
        "company_name": supplier.company_info.legal_name,
        "verification_status": supplier.verification.verification_status.value,
        "status": supplier.status.value
    },
    "verification_token": verification_token
}
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The construction pattern is the same as TASK_01's `register_leader`, but with MORE embedded objects. Build each embedded object as a separate variable (address, contact_info, company_info, business_info, verification), then assemble the Supplier from all of them.

Pay attention to `SupplierContactInfo` - it takes `contact_person_email=primary_email` (the contact person's email defaults to the supplier's primary email).

For `website`: the schema validates it as `HttpUrl`, so convert it with `str(website) if website else None`.

</details>

<details>
<summary><b>Hint Level 2</b> - The document construction</summary>

```python
supplier = Supplier(
    password_hash=self.hash_password(password),
    contact_info=SupplierContactInfo(
        primary_email=primary_email,
        primary_phone=phone,
        contact_person_name=contact_person_name,
        contact_person_title=contact_person_title,
        contact_person_email=primary_email  # defaults to primary email
    ),
    company_info=CompanyInfo(
        legal_name=legal_name,
        company_type=company_type,
        tax_id=tax_id,
        tax_id_country=tax_id_country,
        business_address=CompanyAddress(
            street_address_1=street_address,
            city=city,
            state=state or "N/A",
            zip_code=zip_code,
            country=country
        )
    ),
    business_info=BusinessInfo(
        industry_category=industry_category,
        description=description.strip(),
        website=str(website) if website else None
    ),
    verification=VerificationInfo(
        terms_accepted=True,
        terms_accepted_at=utc_now(),
        privacy_policy_accepted=True
    )
)
```

</details>

#### Verify Exercise 5.3

```bash
curl -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "sales@acme-electronics.com",
    "phone": "+1-555-0100",
    "contact_person_name": "John Doe",
    "contact_person_title": "Sales Director",
    "legal_name": "Acme Electronics Inc",
    "company_type": "corporation",
    "tax_id": "12-3456789",
    "tax_id_country": "US",
    "street_address": "100 Commerce Blvd",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "US",
    "industry_category": "electronics",
    "description": "Leading electronics manufacturer specializing in consumer gadgets and smart home devices.",
    "website": "https://acme-electronics.com",
    "password": "SecurePass1!",
    "terms_accepted": true,
    "privacy_policy_accepted": true
  }'
```

**Expected response (201 Created):**
```json
{
  "supplier": {
    "id": "<object-id>",
    "email": "sales@acme-electronics.com",
    "company_name": "Acme Electronics Inc",
    "verification_status": "pending",
    "status": "active"
  },
  "message": "Registration successful. Verification email sent to sales@acme-electronics.com",
  "next_steps": [
    "Verify your email address",
    "Upload business verification documents",
    "Wait for admin approval (2-5 business days)"
  ]
}
```

**Test terms rejection (400):**
```bash
curl -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "test@acme.com",
    "phone": "+1-555-0100",
    "contact_person_name": "Jane",
    "legal_name": "Test Corp",
    "company_type": "llc",
    "tax_id": "99-9999999",
    "tax_id_country": "US",
    "street_address": "1 Main St",
    "city": "LA",
    "zip_code": "90001",
    "country": "US",
    "industry_category": "fashion",
    "description": "A test company for fashion products and accessories.",
    "password": "SecurePass1!",
    "terms_accepted": false,
    "privacy_policy_accepted": true
  }'
```

**Test cross-collection email rejection (use an email from TASK_01):**
```bash
curl -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "consumer@example.com",
    "phone": "+1-555-0100",
    "contact_person_name": "Duplicate",
    "legal_name": "Dupe Corp",
    "company_type": "llc",
    "tax_id": "88-8888888",
    "tax_id_country": "US",
    "street_address": "1 Main St",
    "city": "LA",
    "zip_code": "90001",
    "country": "US",
    "industry_category": "other",
    "description": "This should fail because email exists in users collection.",
    "password": "SecurePass1!",
    "terms_accepted": true,
    "privacy_policy_accepted": true
  }'
```
Should return 400: "Email already in use"

**Verify the nested structure in MongoDB shell:**
```javascript
db.suppliers.findOne(
  {"contact_info.primary_email": "sales@acme-electronics.com"},
  {
    "company_info.legal_name": 1,
    "company_info.business_address": 1,
    "business_info.industry_category": 1,
    "verification.verification_status": 1,
    "verification.terms_accepted": 1
  }
)
```

---

### Exercise 5.4: Login with Dual Tokens

**Concept:** `find_one` + security validation + generating access/refresh token pair
**Difficulty:** Medium-High
**What's new from TASK_01:** The login returns TWO tokens plus supplier data. Also checks for `status == DELETED` separately from `deleted_at`.

#### Implement: `login(self, email: str, password: str, ip_address: str) -> Dict[str, Any]`

**Phases (same structure as TASK_01 login, with additions):**

#### Phase 1: Find the supplier
- Normalize email
- `Supplier.find_one({"contact_info.primary_email": email})`
- Not found → `ValueError("Invalid email or password")`

#### Phase 2: Check account status (THREE checks, not two)
In order:
1. `supplier.deleted_at is not None` → `ValueError("Account no longer exists")`
2. `supplier.status == SupplierStatus.DELETED` → `ValueError("Account has been deleted")`
3. `supplier.status == SupplierStatus.SUSPENDED` → `ValueError("Account suspended. Contact support.")`

> **Why two deletion checks?** This is defense-in-depth. `deleted_at` is the soft delete marker. `status == DELETED` is the status enum. They should always be in sync, but if they're not (e.g., a bug or manual DB edit), both checks catch it.

#### Phase 3: Check account lock
- Same pattern as TASK_01: check `locked_until`, reset if expired

#### Phase 4: Verify password
- Same pattern as TASK_01: increment failed attempts, lock at 5
- **No Kafka event emitted for supplier account lock** (unlike User in TASK_01)

#### Phase 5: Record successful login + emit event
- `await supplier.record_successful_login(ip_address)`
- Emit Kafka: topic=`Topic.SUPPLIER`, action=`"login"`, data includes `company_name`

#### Phase 6: Generate DUAL tokens + return *(NEW)*
```python
access_token = self.generate_access_token(supplier)
refresh_token = self.generate_refresh_token(supplier)

return {
    "access_token": access_token,
    "refresh_token": refresh_token,
    "supplier": {
        "id": supplier_id,
        "email": supplier.contact_info.primary_email,
        "company_name": supplier.company_info.legal_name,
        "verification_status": supplier.verification.verification_status.value,
        "status": supplier.status.value
    }
}
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The login flow is nearly identical to TASK_01's login. The differences are:
1. Query `Supplier` instead of `User`
2. Three status checks instead of two
3. No Kafka event on account lock (optional simplification)
4. Generate access_token + refresh_token instead of just returning user data
5. The returned dict includes both tokens and a `supplier` key (not `user`)

</details>

<details>
<summary><b>Hint Level 2</b> - Return structure</summary>

The route (`LoginSupplierResponse`) expects:
```python
{
    "access_token": "eyJ...",         # from generate_access_token()
    "refresh_token": "eyJ...",        # from generate_refresh_token()
    "supplier": {                     # SupplierResponse fields
        "id": "...",
        "email": "...",
        "company_name": "...",
        "verification_status": "pending",
        "status": "active"
    }
}
```

The response schema adds `token_type: "bearer"` and `expires_in: 1800` as defaults - you don't need to include them.

</details>

#### Verify Exercise 5.4

```bash
curl -X POST http://localhost:8000/supplier/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@acme-electronics.com",
    "password": "SecurePass1!"
  }'
```

**Expected (200 OK):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "supplier": {
    "id": "<object-id>",
    "email": "sales@acme-electronics.com",
    "company_name": "Acme Electronics Inc",
    "verification_status": "pending",
    "status": "active"
  }
}
```

**Decode the access token to verify its payload:**
```bash
# Copy the access_token value and decode it:
echo "<access_token>" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```
You should see: `sub`, `email`, `company_name`, `type: "supplier_access"`, `verification_status`, `status`, `iat`, `exp`

**Decode the refresh token:**
```bash
echo "<refresh_token>" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```
You should see only: `sub`, `type: "supplier_refresh"`, `iat`, `exp` (minimal data - security principle)

---

### Exercise 5.5: Email Verification - Suppliers Stay Pending

**Concept:** `Supplier.get(ObjectId)` + save - simpler than User because no auto-activation
**Difficulty:** Easy-Medium
**What's new from TASK_01:** No status change on verification. Suppliers stay at whatever status they have - they need admin approval separately.

#### Implement: `verify_email(self, token: str) -> Dict[str, Any]`

**Business Rules:**
1. Verify the token: `self.verify_token(token, "supplier_email_verification")`
   - Note: token type is `"supplier_email_verification"` (not `"email_verification"`)
   - Payload key is `"supplier_id"` (not `"user_id"`)
2. Get supplier by ID: `Supplier.get(ObjectId(supplier_id))`
   - Not found → `ValueError("Supplier not found")`
3. Save the supplier (to update `updated_at` timestamp)
4. Return result:

```python
{
    "id": str(supplier.id),
    "email": supplier.contact_info.primary_email,
    "email_verified": True,
    "verification_status": supplier.verification.verification_status.value
}
```

> **Note:** The Supplier model doesn't have an `email_verified` field on `contact_info` like User does. We return `email_verified: True` in the response to satisfy the schema, but we're not persisting it to a field. This is a simplification - in production you'd add the field to the model.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This is simpler than TASK_01's verify_email because there's no conditional status change. Just verify the token, fetch the supplier, save it, and return.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
async def verify_email(self, token: str) -> Dict[str, Any]:
    try:
        payload = self.verify_token(token, "supplier_email_verification")
        supplier_id = payload.get("supplier_id")

        supplier = await Supplier.get(ObjectId(supplier_id))
        if not supplier:
            raise ValueError("Supplier not found")

        await supplier.save()

        return {
            "id": str(supplier.id),
            "email": supplier.contact_info.primary_email,
            "email_verified": True,
            "verification_status": supplier.verification.verification_status.value
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to verify email: {str(e)}")
```

</details>

#### Verify Exercise 5.5

```bash
# Register a fresh supplier and capture the token:
RESPONSE=$(curl -s -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "verify@supplier-test.com",
    "phone": "+1-555-9999",
    "contact_person_name": "Test Verify",
    "legal_name": "Verify Test Corp",
    "company_type": "llc",
    "tax_id": "77-7777777",
    "tax_id_country": "US",
    "street_address": "1 Test St",
    "city": "Chicago",
    "zip_code": "60601",
    "country": "US",
    "industry_category": "other",
    "description": "A test company to verify the email verification flow works properly.",
    "password": "VerifyTest1!",
    "terms_accepted": true,
    "privacy_policy_accepted": true
  }')

TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['supplier']['verification_token'])" 2>/dev/null || echo $RESPONSE | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('verification_token',''))")

curl -X POST http://localhost:8000/supplier/verify-email \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"
```

**Expected (200 OK):**
```json
{
  "id": "<object-id>",
  "email": "verify@supplier-test.com",
  "email_verified": true,
  "verification_status": "pending"
}
```

Note: `verification_status` stays `"pending"` - email verification doesn't change it.

---

### Exercise 5.6: Password Reset Flow

**Concept:** Combining patterns from TASK_01, applied to a different collection
**Difficulty:** Medium
**What's reinforced:** `find_one` → token → `get` by ID → multi-field update

#### Implement TWO methods:

**5.6.1 - `request_password_reset(self, email: str) -> Optional[str]`**

Requirements:
1. Normalize email
2. `Supplier.find_one({"contact_info.primary_email": email})`
3. Not found → return `None`
4. Generate reset token using `self.generate_reset_token(str(supplier.id), email)`
5. Return the token

**5.6.2 - `reset_password(self, token: str, new_password: str) -> Dict[str, Any]`**

Requirements:
1. Verify token: `self.verify_token(token, "supplier_password_reset")`
2. Extract `supplier_id` and `email` from payload
3. Get supplier: `Supplier.get(ObjectId(supplier_id))`
4. Validate new password: `self.validate_password(new_password, email)`
5. Update four fields:
   - `supplier.password_hash` = new hash
   - `supplier.security.password_changed_at` = `utc_now()`
   - `supplier.security.failed_login_attempts` = `0`
   - `supplier.security.locked_until` = `None`
6. Save
7. Return `{"message": "Password reset successful"}`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

These are almost character-for-character identical to TASK_01's password reset methods. The only differences: use `Supplier` instead of `User`, use `"supplier_password_reset"` as the token type, and extract `"supplier_id"` from the payload instead of `"user_id"`.

</details>

#### Verify Exercise 5.6

```bash
# Request reset
curl -X POST http://localhost:8000/supplier/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "sales@acme-electronics.com"}'

# Reset (you'd need to capture the token from direct service call)
curl -X POST http://localhost:8000/supplier/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<paste-reset-token>",
    "new_password": "NewSecure1Pass!"
  }'

# Login with new password
curl -X POST http://localhost:8000/supplier/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@acme-electronics.com",
    "password": "NewSecure1Pass!"
  }'
```

---

### Exercise 5.7: Document Submission - Verification Workflow

**Concept:** Get by ID + status-based validation + updating an array field + status transition
**Difficulty:** Medium
**What's new from TASK_01:** This exercise has NO equivalent in TASK_01. It's the first time you'll implement a **workflow step** - the supplier submits documents, and their verification status changes.

#### Implement: `submit_verification_documents(self, supplier_id: str, documents: list) -> Dict[str, Any]`

**Business Rules:**
1. Get supplier by ID: `Supplier.get(ObjectId(supplier_id))`
   - Not found → `ValueError("Supplier not found")`

2. **Status gate:** Check that supplier is still pending
   - If `supplier.verification.verification_status != VerificationStatus.PENDING` → `ValueError("Documents already submitted or supplier already verified")`

3. **Validate required documents:**
   - Three document types are required: `"business_license"`, `"tax_document"`, `"identity_verification"`
   - Extract `document_type` from each dict in the `documents` list
   - Find which required types are missing
   - If any missing → `ValueError(f"Missing required documents: {', '.join(missing)}")`

4. **Update the supplier:**
   - `supplier.verification.submitted_documents = documents`
   - `supplier.updated_at = utc_now()`

5. Save the supplier

6. **Emit Kafka event:**
   - topic=`Topic.SUPPLIER`, action=`"documents_submitted"`
   - data: `company_name`, `document_count`, `verification_status`

7. Return:
```python
{
    "message": "Verification documents submitted successfully. Your application is under review."
}
```

> **Design note:** The `VerificationStatus` enum has three states: `PENDING`, `VERIFIED`, `REJECTED`. There is intentionally no `UNDER_REVIEW` status. The way to check if documents have been submitted is: `verification_status == PENDING AND len(submitted_documents) > 0`. This is a common pattern - use the data to infer state rather than adding a status for every permutation.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This follows the pattern: get by ID → validate preconditions → mutate fields → save. The new element is checking a list of dicts for required values and updating an array field.

</details>

<details>
<summary><b>Hint Level 2</b> - The validation logic</summary>

```python
# Validate required documents
required_types = ["business_license", "tax_document", "identity_verification"]
submitted_types = [doc.get("document_type") for doc in documents]

missing = [t for t in required_types if t not in submitted_types]
if missing:
    raise ValueError(f"Missing required documents: {', '.join(missing)}")
```

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def submit_verification_documents(self, supplier_id, documents):
    try:
        supplier = await Supplier.get(ObjectId(supplier_id))
        if not supplier:
            raise ValueError("Supplier not found")

        if supplier.verification.verification_status != VerificationStatus.PENDING:
            raise ValueError("Documents already submitted or supplier already verified")

        required_types = ["business_license", "tax_document", "identity_verification"]
        submitted_types = [doc.get("document_type") for doc in documents]
        missing = [t for t in required_types if t not in submitted_types]
        if missing:
            raise ValueError(f"Missing required documents: {', '.join(missing)}")

        supplier.verification.submitted_documents = documents
        supplier.updated_at = utc_now()
        await supplier.save()

        self._kafka.emit(
            topic=Topic.SUPPLIER,
            action="documents_submitted",
            entity_id=supplier_id,
            data={
                "company_name": supplier.company_info.legal_name,
                "document_count": len(documents),
                "verification_status": supplier.verification.verification_status.value,
            },
        )

        return {
            "message": "Verification documents submitted successfully. Your application is under review."
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to submit documents: {str(e)}")
```

</details>

#### Verify Exercise 5.7

> **Note:** The route currently uses a placeholder `supplier_id`. For testing, you can call the service directly, or temporarily hardcode the supplier ID from MongoDB.

```bash
# First, find your supplier's ID:
# db.suppliers.findOne({"contact_info.primary_email": "sales@acme-electronics.com"}, {"_id": 1})

# Then test via service call or modified route:
# await svc.submit_verification_documents(
#     supplier_id="<id-from-above>",
#     documents=[
#         {"document_type": "business_license", "file_url": "https://storage.example.com/license.pdf"},
#         {"document_type": "tax_document", "file_url": "https://storage.example.com/tax.pdf"},
#         {"document_type": "identity_verification", "file_url": "https://storage.example.com/id.pdf"}
#     ]
# )
```

**Verify in MongoDB shell:**
```javascript
db.suppliers.findOne(
  {"contact_info.primary_email": "sales@acme-electronics.com"},
  {"verification": 1}
)
// verification.submitted_documents should be an array of 3 document objects
// verification.verification_status should still be "pending"
```

**Test missing documents (should fail):**
```python
# Only 2 documents - missing identity_verification
# await svc.submit_verification_documents(supplier_id, [
#     {"document_type": "business_license", "file_url": "..."},
#     {"document_type": "tax_document", "file_url": "..."}
# ])
# → ValueError: "Missing required documents: identity_verification"
```

**Test double submission (should fail):**
```python
# After first successful submission, try again:
# await svc.submit_verification_documents(supplier_id, [...])
# → ValueError: "Documents already submitted or supplier already verified"
# WAIT: This will actually pass since status is still PENDING.
# The guard only checks verification_status != PENDING
# This is fine - documents get overwritten. Think about whether
# this is desired behavior. (See Advanced Challenge B)
```

---

## 6. VERIFICATION CHECKLIST

Before moving to TASK_03, verify:

### Functional Checks
- [ ] **Register supplier** - creates document with all 5 embedded objects correctly nested
- [ ] **Terms rejection** - registration fails without terms acceptance
- [ ] **Cross-collection email check** - email registered as User (TASK_01) is rejected for supplier
- [ ] **Password validation** - rejects passwords without special characters
- [ ] **Login returns dual tokens** - both `access_token` and `refresh_token` present
- [ ] **Access token** has full payload (sub, email, company_name, type, verification_status)
- [ ] **Refresh token** has minimal payload (sub, type only)
- [ ] **Login security** - wrong password increments counter, locks at 5
- [ ] **Three status checks** - deleted_at, DELETED status, SUSPENDED status all caught
- [ ] **Email verification** - returns verified:true but verification_status stays "pending"
- [ ] **Password reset** - changes password, resets security fields
- [ ] **Document submission** - stores documents array, validates required types
- [ ] **Document submission guard** - rejects if not in PENDING status

### Database Checks
- [ ] `db.suppliers.countDocuments()` - correct count
- [ ] `db.suppliers.getIndexes()` - shows all 7 indexes
- [ ] Supplier document has complete `company_info.business_address` nesting
- [ ] Supplier document has `verification.terms_accepted: true` and `terms_accepted_at` set
- [ ] After login: `security.last_login_at` updated
- [ ] After document submission: `verification.submitted_documents` is populated array

### Code Quality Checks
- [ ] Cross-collection import: `from shared.models.user import User`
- [ ] All token types use `"supplier_"` prefix
- [ ] All payload keys use `"supplier_id"` (not `"user_id"`)
- [ ] Kafka events use `Topic.SUPPLIER`
- [ ] Password min length is 10 (not 8)
- [ ] Password pattern requires `!@#$%^&*`

---

## 7. ADVANCED CHALLENGES

### Challenge A: Deep Index Analysis

Run this in MongoDB shell:
```javascript
// This query hits the 3-level deep business address index
db.suppliers.find({
  "company_info.business_address.country": "US",
  "company_info.business_address.state": "NY",
  "company_info.business_address.city": "New York"
}).explain("executionStats")
```

Questions:
1. Does it use the compound index? (Check `winningPlan.stage`)
2. What happens if you query ONLY by city (skipping country and state)?
```javascript
db.suppliers.find({
  "company_info.business_address.city": "New York"
}).explain("executionStats")
```
Does it still use the index?

<details>
<summary>Answer</summary>

No! Compound indexes follow the **left prefix rule**. The index is `(country, state, city)`. You can query:
- `country` alone ✓
- `country + state` ✓
- `country + state + city` ✓
- `city` alone ✗ (can't skip the prefix - full collection scan)
- `state + city` ✗ (can't skip `country`)

This is one of the most important MongoDB index concepts. The field ORDER in a compound index matters.

</details>

### Challenge B: Double Submission Problem

In Exercise 5.7, we check `verification_status != PENDING` to guard against resubmission. But if the status is still `PENDING` after the first submission, the guard doesn't catch a second submission - it just overwrites the documents.

Design a solution:
1. What additional check would prevent double submission while keeping `PENDING` status?
2. How would you implement it with a single query?

<details>
<summary>Answer</summary>

Check if `submitted_documents` is already non-empty:

```python
if supplier.verification.verification_status != VerificationStatus.PENDING:
    raise ValueError("Supplier already verified or rejected")

if len(supplier.verification.submitted_documents) > 0:
    raise ValueError("Documents already submitted. Contact support to update.")
```

Or combine into one query at the database level:
```python
supplier = await Supplier.find_one({
    "_id": ObjectId(supplier_id),
    "verification.verification_status": VerificationStatus.PENDING.value,
    "verification.submitted_documents": {"$size": 0}
})
if not supplier:
    raise ValueError("Supplier not found or documents already submitted")
```

The second approach is atomic - no race condition between reading and checking.

</details>

### Challenge C: Supplier vs User - Why Two Collections?

The architecture document explicitly states suppliers are separate from users. But both have email, password, login, and security fields. Why not put them in the same collection with a `type` field?

Think about:
1. What happens to queries when you have mixed documents? (Hint: index selectivity)
2. What happens to validation when some fields are required for suppliers but don't exist for users?
3. How does the `product_ids` array on Supplier affect query patterns?
4. What about the verification workflow - how would it coexist with user's simple email verification?

<details>
<summary>Answer</summary>

**Performance:** A single collection with mixed types means every query needs a `type` filter. The index `(type, contact_info.primary_email)` is less selective than `(contact_info.primary_email)` alone. With separate collections, each index is specialized.

**Schema flexibility:** MongoDB is schemaless, but Beanie enforces schemas per model. A single collection would need complex conditional validation: "if type=supplier, require company_info". Separate models keep validation clean.

**Index overhead:** Suppliers have indexes on `company_info.tax_id`, `business_info.industry_category`, `stats.total_sales_cents`. Users have indexes on `role + status + follower_count`. In a shared collection, ALL these indexes exist on ALL documents, wasting memory on indexes that only apply to half the documents.

**Operational independence:** Suppliers can be backed up, migrated, or sharded independently. Different read/write patterns can be optimized per collection.

**The trade-off:** Cross-collection email uniqueness requires multiple queries (as you implemented in Exercise 5.2). This is the cost of separation.

</details>

---

## 8. WHAT'S NEXT

You've now built authentication for both sides of the platform - Users and Suppliers. You understand:
- Cross-collection querying
- Complex nested document construction
- Dual token authentication strategy
- Verification workflow patterns
- Why entities are separated into different collections

**TASK 03: Community Service** is where things get truly interesting. You'll move beyond authentication into **relationship management**:
- Array operations: `$addToSet` to join, `$pull` to leave
- Cursor-based pagination with keyset patterns
- Denormalized data (storing owner info inside the community)
- Multi-filter discovery queries (category + tags + country + featured)
- Moderation workflows (suspend, verify, feature)

Communities are where Users and Suppliers intersect - leaders create communities, consumers join them, and suppliers promote products within them. The queries get substantially more complex.
