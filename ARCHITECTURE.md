# Social Commerce Platform - Architecture Documentation

> **Purpose:** Enable developers to understand the system's design philosophy, domain model, and architectural decisions.

---

## Table of Contents

1. [Business Purpose](#1-business-purpose)
2. [Domain Model](#2-domain-model)
3. [System Layers](#3-system-layers)
4. [Core Entities Deep Dive](#4-core-entities-deep-dive)
5. [Data Flow Patterns](#5-data-flow-patterns)
6. [Architectural Principles](#6-architectural-principles)
7. [Design Decisions & Rationale](#7-design-decisions--rationale)
8. [Event-Driven Architecture](#8-event-driven-architecture)

---

## 1. Business Purpose

### 1.1 What Problem Does This System Solve?

Traditional e-commerce separates **social engagement** from **purchasing**. Users discover products on social media, then leave to buy elsewhere. This platform merges both:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   TRADITIONAL MODEL                    THIS PLATFORM                        │
│   ═════════════════                    ═════════════                        │
│                                                                             │
│   Social Media ──► Discovery           ┌─────────────────────────────┐      │
│        │                               │                             │      │
│        │ (user leaves)                 │   UNIFIED EXPERIENCE        │      │
│        ▼                               │                             │      │
│   E-commerce ──► Purchase              │   Discovery + Engagement    │      │
│                                        │         +                   │      │
│   ✗ Lost attribution                   │      Purchase               │      │
│   ✗ Broken experience                  │         +                   │      │
│   ✗ No community                       │     Community               │      │
│                                        │                             │      │
│                                        │   ✓ Full attribution        │      │
│                                        │   ✓ Seamless experience     │      │
│                                        │   ✓ Engaged communities     │      │
│                                        └─────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 The Stakeholder Ecosystem

Four distinct user types interact within the platform:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAKEHOLDER ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ┌───────────┐                                  │
│                              │   ADMIN   │                                  │
│                              │           │                                  │
│                              │ Moderates │                                  │
│                              │ Verifies  │                                  │
│                              │ Approves  │                                  │
│                              └─────┬─────┘                                  │
│                                    │                                        │
│            ┌───────────────────────┼───────────────────────┐                │
│            │                       │                       │                │
│            ▼                       ▼                       ▼                │
│     ┌───────────┐           ┌───────────┐           ┌───────────┐          │
│     │  LEADER   │           │ CONSUMER  │           │ SUPPLIER  │          │
│     │           │           │           │           │           │          │
│     │ Creates   │◄─────────►│ Joins     │◄─────────►│ Lists     │          │
│     │ communities│  engages  │ communities│ purchases │ products  │          │
│     │           │           │           │           │           │          │
│     │ Curates   │           │ Discovers │           │ Creates   │          │
│     │ content   │           │ products  │           │ promotions│          │
│     └───────────┘           └───────────┘           └───────────┘          │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  LEADER: Influencer/celebrity who builds audience through communities       │
│  CONSUMER: End user who joins communities and makes purchases               │
│  SUPPLIER: Business that sells products through the platform                │
│  ADMIN: Platform staff who maintains quality and trust                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Value Proposition by Stakeholder

| Stakeholder | What They Get | What They Give |
|-------------|---------------|----------------|
| **Consumer** | Curated products from trusted leaders, community belonging | Purchases, engagement, attention |
| **Leader** | Monetization of influence, direct audience relationship | Content curation, community management |
| **Supplier** | Access to engaged audiences, trusted distribution | Products, promotions, fulfillment |
| **Admin** | Platform health metrics, revenue | Moderation, quality control |

---

## 2. Domain Model

### 2.1 Core Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOMAIN MODEL                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│      ┌──────────┐                                      ┌──────────┐         │
│      │   USER   │                                      │ SUPPLIER │         │
│      │          │                                      │          │         │
│      │ Consumer │                                      │ Business │         │
│      │    or    │                                      │ account  │         │
│      │  Leader  │                                      │          │         │
│      └────┬─────┘                                      └────┬─────┘         │
│           │                                                 │               │
│           │ creates/joins                                   │ creates       │
│           │                                                 │               │
│           ▼                                                 ▼               │
│      ┌──────────┐         contains              ┌──────────────────┐        │
│      │COMMUNITY │◄──────────────────────────────│     PRODUCT      │        │
│      │          │         promotions            │                  │        │
│      │  Group   │                               │  Item for sale   │        │
│      │  around  │                               │  with variants   │        │
│      │  leader  │                               │  and inventory   │        │
│      └────┬─────┘                               └────────┬─────────┘        │
│           │                                              │                  │
│           │ hosts                                        │ featured in     │
│           ▼                                              ▼                  │
│      ┌──────────┐                               ┌──────────────────┐        │
│      │   POST   │                               │    PROMOTION     │        │
│      │          │                               │                  │        │
│      │  Social  │                               │    Marketing     │        │
│      │  content │                               │    campaign      │        │
│      │          │                               │    with deals    │        │
│      └────┬─────┘                               └────────┬─────────┘        │
│           │                                              │                  │
│           │ aggregated into                              │ drives          │
│           ▼                                              ▼                  │
│      ┌──────────┐                               ┌──────────────────┐        │
│      │   FEED   │ ◄─────────────────────────────│      ORDER       │        │
│      │          │        attribution            │                  │        │
│      │ Timeline │                               │    Purchase      │        │
│      │   view   │                               │    transaction   │        │
│      └──────────┘                               └──────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Entity Purpose Summary

| Entity | Business Purpose | Key Characteristics |
|--------|------------------|---------------------|
| **User** | Platform participant (consumer or leader role) | Has profile, permissions, activity stats |
| **Supplier** | Business selling products | Separate from users, requires verification |
| **Community** | Gathering place around a leader's brand | Has members, rules, content policies |
| **Product** | Item available for purchase | Has variants, inventory, pricing |
| **Promotion** | Marketing campaign for products | Time-bound, requires approval, tracks performance |
| **Post** | Social content in communities | Can request global visibility |
| **Feed** | Aggregated timeline view | Optimized for fast retrieval |
| **Order** | Purchase transaction | Captures product state at purchase time |

### 2.3 Entity Lifecycle States

Each major entity follows a predictable lifecycle:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENTITY LIFECYCLES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER LIFECYCLE                                                             │
│  ══════════════                                                             │
│                                                                             │
│  ┌─────────┐    verify    ┌────────┐    suspend    ┌───────────┐            │
│  │ PENDING │─────────────►│ ACTIVE │──────────────►│ SUSPENDED │            │
│  └─────────┘              └────────┘               └───────────┘            │
│       │                        │                         │                  │
│       │                        │ delete                  │ delete           │
│       │                        ▼                         ▼                  │
│       └───────────────────►┌─────────┐◄──────────────────┘                  │
│            delete          │ DELETED │                                      │
│                            └─────────┘                                      │
│                                                                             │
│                                                                             │
│  PROMOTION LIFECYCLE                                                        │
│  ═══════════════════                                                        │
│                                                                             │
│  ┌───────┐  submit   ┌─────────────────┐  approve  ┌───────────┐            │
│  │ DRAFT │──────────►│ PENDING_APPROVAL│──────────►│ SCHEDULED │            │
│  └───────┘           └─────────────────┘           └─────┬─────┘            │
│                              │                           │                  │
│                              │ reject                    │ start date       │
│                              ▼                           ▼                  │
│                       ┌──────────┐               ┌────────────┐             │
│                       │ REJECTED │               │   ACTIVE   │◄────┐       │
│                       └──────────┘               └──────┬─────┘     │       │
│                                                         │           │       │
│                              ┌───────────────┬──────────┴───┐       │       │
│                              │               │              │       │       │
│                              ▼               ▼              ▼       │       │
│                        ┌──────────┐    ┌────────┐    ┌───────┐     │       │
│                        │ CANCELLED│    │ PAUSED │────│ ENDED │     │       │
│                        └──────────┘    └────────┘    └───────┘     │       │
│                                              │                      │       │
│                                              └──────────────────────┘       │
│                                                    resume                   │
│                                                                             │
│                                                                             │
│  ORDER LIFECYCLE                                                            │
│  ═══════════════                                                            │
│                                                                             │
│  ┌─────────┐  payment  ┌───────────┐  process  ┌────────────┐               │
│  │ PENDING │──────────►│ CONFIRMED │──────────►│ PROCESSING │               │
│  └─────────┘           └───────────┘           └──────┬─────┘               │
│       │                                               │                     │
│       │ cancel                                        │ ship                │
│       ▼                                               ▼                     │
│  ┌───────────┐                                 ┌─────────┐                  │
│  │ CANCELLED │                                 │ SHIPPED │                  │
│  └───────────┘                                 └────┬────┘                  │
│                                                     │                       │
│                                                     │ deliver               │
│                                                     ▼                       │
│                                               ┌───────────┐                 │
│                                               │ DELIVERED │                 │
│                                               └───────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. System Layers

### 3.1 Layered Architecture

The system follows a strict layered architecture where each layer has a single responsibility:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM LAYERS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   EXTERNAL                                                                  │
│   ════════                                                                  │
│   Web apps, mobile apps, third-party integrations                           │
│                                                                             │
│         │                                                                   │
│         │ HTTP/JSON                                                         │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         ROUTES LAYER                                 │   │
│  │                                                                      │   │
│  │  RESPONSIBILITY: HTTP protocol handling                              │   │
│  │                                                                      │   │
│  │  • Receive HTTP requests                                             │   │
│  │  • Validate request format (via schemas)                             │   │
│  │  • Extract authentication context                                    │   │
│  │  • Delegate to services                                              │   │
│  │  • Format HTTP responses                                             │   │
│  │  • Handle HTTP-specific errors (status codes)                        │   │
│  │                                                                      │   │
│  │  DOES NOT: Contain business logic, access database directly          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │ Method calls                                                      │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        SCHEMAS LAYER                                 │   │
│  │                                                                      │   │
│  │  RESPONSIBILITY: Data structure contracts                            │   │
│  │                                                                      │   │
│  │  • Define request data structures                                    │   │
│  │  • Define response data structures                                   │   │
│  │  • Validate field types and constraints                              │   │
│  │  • Transform data between layers                                     │   │
│  │                                                                      │   │
│  │  DOES NOT: Contain business logic, know about database               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │ Validated data                                                    │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       SERVICES LAYER                                 │   │
│  │                                                                      │   │
│  │  RESPONSIBILITY: Business logic and orchestration                    │   │
│  │                                                                      │   │
│  │  • Enforce business rules                                            │   │
│  │  • Validate business constraints                                     │   │
│  │  • Orchestrate multi-entity operations                               │   │
│  │  • Manage transactions                                               │   │
│  │  • Coordinate with external services                                 │   │
│  │                                                                      │   │
│  │  DOES NOT: Know about HTTP, format responses                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │ Domain operations                                                 │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        MODELS LAYER                                  │   │
│  │                                                                      │   │
│  │  RESPONSIBILITY: Data persistence and domain representation          │   │
│  │                                                                      │   │
│  │  • Define document structure                                         │   │
│  │  • Encapsulate entity-level logic                                    │   │
│  │  • Manage persistence operations                                     │   │
│  │  • Define indexes for query optimization                             │   │
│  │                                                                      │   │
│  │  DOES NOT: Know about HTTP, contain cross-entity logic               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │ Database operations                                               │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       DATABASE LAYER                                 │   │
│  │                                                                      │   │
│  │  RESPONSIBILITY: Data storage and retrieval                          │   │
│  │                                                                      │   │
│  │  • Manage database connections                                       │   │
│  │  • Execute queries                                                   │   │
│  │  • Handle connection pooling                                         │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Communication Rules

| From Layer | Can Call | Cannot Call |
|------------|----------|-------------|
| Routes | Schemas, Services | Models directly, Database |
| Schemas | (passive - data only) | - |
| Services | Models, Utils, Other Services | Routes, Schemas |
| Models | Database, Utils | Routes, Services, Schemas |
| Utils | (stateless helpers) | Any layer with state |

### 3.3 Why This Separation Matters

| Benefit | How It's Achieved |
|---------|-------------------|
| **Testability** | Services can be tested without HTTP; Models without services |
| **Maintainability** | Changes to HTTP don't affect business logic |
| **Reusability** | Services can be called from background jobs, CLI tools |
| **Clarity** | Each file has a single, clear purpose |

---

## 4. Core Entities Deep Dive

### 4.1 User Entity

**Business Purpose:** Represents any human participant on the platform (excluding suppliers who are businesses).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            USER ENTITY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IDENTITY                                                                   │
│  ════════                                                                   │
│  Who is this person? How do they authenticate?                              │
│                                                                             │
│  ROLE                                                                       │
│  ════                                                                       │
│  • CONSUMER: Regular user who browses, joins, purchases                     │
│  • LEADER: Influencer who creates communities, curates content              │
│                                                                             │
│  PROFILE                                                                    │
│  ═══════                                                                    │
│  Public-facing information: display name, avatar, bio                       │
│  Leaders have additional business info (for monetization)                   │
│                                                                             │
│  PERMISSIONS                                                                │
│  ═══════════                                                                │
│  What can this user do?                                                     │
│  • Can they post? Comment? Create communities?                              │
│  • What are their limits? (max communities, etc.)                           │
│                                                                             │
│  STATISTICS                                                                 │
│  ══════════                                                                 │
│  Aggregated activity data (followers, orders, spending)                     │
│  Pre-computed for fast display                                              │
│                                                                             │
│  SECURITY                                                                   │
│  ════════                                                                   │
│  Login tracking, failed attempts, account locking                           │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  KEY RELATIONSHIPS:                                                         │
│                                                                             │
│    User ───owns───► Community (if leader)                                   │
│    User ───member of───► Community (multiple)                               │
│    User ───creates───► Post                                                 │
│    User ───places───► Order                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Supplier Entity

**Business Purpose:** Represents a business that sells products on the platform. Intentionally separate from User because businesses have fundamentally different needs (verification, banking, tax info).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUPPLIER ENTITY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHY SEPARATE FROM USER?                                                    │
│  ═══════════════════════                                                    │
│                                                                             │
│  Users are people. Suppliers are businesses.                                │
│                                                                             │
│  • Different verification requirements (business license, tax ID)           │
│  • Different data needs (banking info, fulfillment addresses)               │
│  • Different permission model (product limits, promotion limits)            │
│  • Different lifecycle (verification workflow)                              │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  COMPANY INFORMATION                                                        │
│  ═══════════════════                                                        │
│  Legal name, tax ID, registration details                                   │
│                                                                             │
│  VERIFICATION STATUS                                                        │
│  ═══════════════════                                                        │
│  Suppliers must be verified before they can sell                            │
│  Admin reviews documentation, approves/rejects                              │
│                                                                             │
│  BANKING INFORMATION                                                        │
│  ═══════════════════                                                        │
│  How do they receive payments? (payout details)                             │
│                                                                             │
│  BUSINESS METRICS                                                           │
│  ════════════════                                                           │
│  Products listed, orders fulfilled, revenue, ratings                        │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  KEY RELATIONSHIPS:                                                         │
│                                                                             │
│    Supplier ───creates───► Product (multiple)                               │
│    Supplier ───creates───► Promotion (multiple)                             │
│    Supplier ───fulfills───► Order (via products)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Community Entity

**Business Purpose:** A branded space where a leader gathers their audience. The primary unit of social organization on the platform.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMMUNITY ENTITY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CORE CONCEPT                                                               │
│  ════════════                                                               │
│                                                                             │
│  Communities are the "gathering places" of the platform.                    │
│  Unlike a generic social feed, each community has:                          │
│                                                                             │
│  • A single owner (the leader who created it)                               │
│  • A defined purpose and rules                                              │
│  • Membership (who belongs)                                                 │
│  • Content policies (who can post, moderation rules)                        │
│  • Visibility settings (public vs private)                                  │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  IDENTITY & BRANDING                                                        │
│  ═══════════════════                                                        │
│  Name, description, purpose statement, visual branding                      │
│                                                                             │
│  MEMBERSHIP                                                                 │
│  ══════════                                                                 │
│  • Who is a member?                                                         │
│  • Is it public (anyone joins) or private (approval needed)?                │
│  • Are there restrictions? (age, location, member cap)                      │
│                                                                             │
│  CONTENT SETTINGS                                                           │
│  ════════════════                                                           │
│  • Can members post or only the leader?                                     │
│  • Is moderation required before posts appear?                              │
│                                                                             │
│  RULES                                                                      │
│  ═════                                                                      │
│  Community guidelines that members must follow                              │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  KEY RELATIONSHIPS:                                                         │
│                                                                             │
│    Community ───owned by───► User (leader)                                  │
│    Community ───has members───► User (multiple)                             │
│    Community ───contains───► Post (multiple)                                │
│    Community ───hosts───► Promotion (supplier promotions shown here)        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Product Entity

**Business Purpose:** Something a supplier sells. Designed to handle real-world complexity: variants (size/color), inventory at multiple locations, detailed specifications.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRODUCT ENTITY                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COMPLEXITY HANDLED                                                         │
│  ═════════════════                                                          │
│                                                                             │
│  Real products are complex. A "T-Shirt" isn't one thing—it's:               │
│  • Small Red, Medium Red, Large Red                                         │
│  • Small Blue, Medium Blue, Large Blue                                      │
│  Each with different stock levels, maybe different prices.                  │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  CORE IDENTITY                                                              │
│  ═════════════                                                              │
│  Name, description, category, brand, condition (new/used)                   │
│                                                                             │
│  VARIANTS                                                                   │
│  ════════                                                                   │
│  Different versions of the same product                                     │
│  Each variant has: SKU, price, inventory, attributes (size: M, color: Red)  │
│                                                                             │
│  INVENTORY                                                                  │
│  ═════════                                                                  │
│  Stock can exist at multiple locations                                      │
│  Each location: quantity available, quantity reserved (for pending orders)  │
│                                                                             │
│  MEDIA                                                                      │
│  ═════                                                                      │
│  Primary image, gallery images, video                                       │
│                                                                             │
│  SHIPPING                                                                   │
│  ════════                                                                   │
│  Where does it ship from? Where can it ship to? Cost? Time?                 │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  KEY RELATIONSHIPS:                                                         │
│                                                                             │
│    Product ───owned by───► Supplier                                         │
│    Product ───featured in───► Promotion                                     │
│    Product ───purchased via───► Order                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Promotion Entity

**Business Purpose:** A marketing campaign that features products with special offers. The bridge between suppliers (who want sales) and communities (where audiences gather).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROMOTION ENTITY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHY PROMOTIONS EXIST                                                       │
│  ════════════════════                                                       │
│                                                                             │
│  Suppliers want to reach audiences. Communities have audiences.             │
│  Promotions are the mechanism that connects them:                           │
│                                                                             │
│     Supplier ──creates──► Promotion ──shown in──► Community                 │
│                                │                                            │
│                                └──► Global Feed (if approved)               │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  PROMOTION TYPES                                                            │
│  ═══════════════                                                            │
│                                                                             │
│  CAMPAIGN: Multiple products (2-3) grouped together                         │
│            "Valentine's Day Collection"                                     │
│                                                                             │
│  SINGLE: One product highlighted with a special offer                       │
│          "Flash Sale: 30% off Running Shoes"                                │
│                                                                             │
│  DEFAULT: Always-on product listing (no special discount)                   │
│           "Available in our store"                                          │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  VISIBILITY                                                                 │
│  ══════════                                                                 │
│                                                                             │
│  Where does this promotion appear?                                          │
│  • Global: Everyone on the platform sees it (requires admin approval)       │
│  • Communities: Only in specific communities (requires leader approval)     │
│  • Both: Appears everywhere (requires both approvals)                       │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  APPROVAL WORKFLOW                                                          │
│  ═════════════════                                                          │
│                                                                             │
│  Promotions don't go live immediately. They must be approved:               │
│                                                                             │
│  1. Supplier creates promotion (DRAFT)                                      │
│  2. Supplier submits for approval (PENDING)                                 │
│  3. Admin approves global visibility (if requested)                         │
│  4. Leaders approve community visibility (if requested)                     │
│  5. All approvals complete → SCHEDULED or ACTIVE                            │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  SCHEDULING                                                                 │
│  ══════════                                                                 │
│                                                                             │
│  Promotions have a time window:                                             │
│  • Start date: When it becomes visible                                      │
│  • End date: When it automatically ends                                     │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  PERFORMANCE TRACKING                                                       │
│  ════════════════════                                                       │
│                                                                             │
│  Every promotion tracks its effectiveness:                                  │
│  • Impressions: How many times shown                                        │
│  • Clicks: How many times clicked                                           │
│  • Conversions: How many purchases resulted                                 │
│  • Revenue: Total sales attributed                                          │
│                                                                             │
│  Tracked per-community so leaders see their audience's engagement.          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 Post & Feed Entities

**Business Purpose:** Posts are social content. The Feed is an optimized view for displaying content quickly.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POST & FEED ENTITIES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POST                                                                       │
│  ════                                                                       │
│  Social content created by community members or leaders.                    │
│                                                                             │
│  Types: Text, Image, Video, Link, Poll                                      │
│                                                                             │
│  Posts live within communities by default.                                  │
│  Authors can request "global distribution" to appear on the main feed.      │
│  This requires admin approval (quality control).                            │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  FEED ITEM                                                                  │
│  ═════════                                                                  │
│                                                                             │
│  WHY A SEPARATE ENTITY?                                                     │
│                                                                             │
│  Loading a feed is the most common operation. It must be FAST.              │
│                                                                             │
│  If we stored only Posts:                                                   │
│  • Loading feed = query Posts + filter + sort + join author data            │
│  • Slow, especially for large communities                                   │
│                                                                             │
│  Feed Items solve this:                                                     │
│  • Pre-computed "references" to content                                     │
│  • Contains preview data (title, author name, thumbnail)                    │
│  • No joins needed for display                                              │
│  • Click on item → fetch full Post                                          │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  FEED TYPES                                                                 │
│  ══════════                                                                 │
│                                                                             │
│  COMMUNITY FEED: Posts within a specific community                          │
│  GLOBAL FEED: Admin-approved posts visible to everyone                      │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  GLOBAL DISTRIBUTION WORKFLOW                                               │
│  ════════════════════════════                                               │
│                                                                             │
│  1. Member creates post in community                                        │
│  2. Post appears in community feed                                          │
│  3. Author requests global distribution                                     │
│  4. Request enters admin queue                                              │
│  5. Admin approves → Post appears in global feed                            │
│     Admin rejects → Post stays community-only                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.7 Order Entity

**Business Purpose:** A purchase transaction. Captures everything needed for fulfillment, customer service, and analytics.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORDER ENTITY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CORE CONCEPT                                                               │
│  ════════════                                                               │
│                                                                             │
│  An order is a snapshot of a purchase at a moment in time.                  │
│                                                                             │
│  Why "snapshot"? Products change. Prices change. Names change.              │
│  But when a customer bought "Red Shoes for $99", that's what they bought.   │
│  The order must preserve this forever (for receipts, disputes, analytics).  │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  CUSTOMER INFORMATION                                                       │
│  ════════════════════                                                       │
│  Who placed this order? (copied from user at order time)                    │
│                                                                             │
│  ORDER ITEMS                                                                │
│  ═══════════                                                                │
│  What was purchased?                                                        │
│  Each item contains a PRODUCT SNAPSHOT:                                     │
│  • Product name, price, image at purchase time                              │
│  • Quantity ordered                                                         │
│  • Individual fulfillment status                                            │
│                                                                             │
│  TOTALS                                                                     │
│  ══════                                                                     │
│  Subtotal, tax, shipping, discounts, final total                            │
│                                                                             │
│  SHIPPING ADDRESS                                                           │
│  ════════════════                                                           │
│  Where does it go? (copied at order time, immutable)                        │
│                                                                             │
│  PAYMENT INFORMATION                                                        │
│  ═══════════════════                                                        │
│  How was it paid? Status of payment, transaction references                 │
│                                                                             │
│  TIMELINE                                                                   │
│  ════════                                                                   │
│  History of all status changes with timestamps                              │
│  "Created at X, Confirmed at Y, Shipped at Z"                               │
│                                                                             │
│  ATTRIBUTION                                                                │
│  ═══════════                                                                │
│  How did the customer find this product?                                    │
│  • Which promotion? Which community?                                        │
│  • UTM parameters for marketing tracking                                    │
│                                                                             │
│  This is critical for proving value to leaders and suppliers.               │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│  FULFILLMENT                                                                │
│  ═══════════                                                                │
│                                                                             │
│  Orders can contain items from DIFFERENT suppliers.                         │
│  Each item is fulfilled independently:                                      │
│                                                                             │
│    Order #123                                                               │
│    ├── Item A (Supplier X) → Shipped                                        │
│    ├── Item B (Supplier X) → Shipped                                        │
│    └── Item C (Supplier Y) → Processing                                     │
│                                                                             │
│  Order status reflects the "worst" item status.                             │
│  (If one item is pending, order shows as partially fulfilled)               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Flow Patterns

### 5.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  REGISTRATION                                                               │
│  ════════════                                                               │
│                                                                             │
│    User                     System                      Database            │
│      │                        │                            │                │
│      │  Provide credentials   │                            │                │
│      │───────────────────────►│                            │                │
│      │                        │                            │                │
│      │                        │  Check email uniqueness    │                │
│      │                        │───────────────────────────►│                │
│      │                        │◄───────────────────────────│                │
│      │                        │                            │                │
│      │                        │  Hash password             │                │
│      │                        │  (one-way, secure)         │                │
│      │                        │                            │                │
│      │                        │  Create user (PENDING)     │                │
│      │                        │───────────────────────────►│                │
│      │                        │                            │                │
│      │                        │  Create verification token │                │
│      │                        │───────────────────────────►│                │
│      │                        │                            │                │
│      │  Return user + token   │                            │                │
│      │◄───────────────────────│                            │                │
│      │                        │                            │                │
│                                                                             │
│                                                                             │
│  LOGIN                                                                      │
│  ═════                                                                      │
│                                                                             │
│    User                     System                      Database            │
│      │                        │                            │                │
│      │  Provide credentials   │                            │                │
│      │───────────────────────►│                            │                │
│      │                        │                            │                │
│      │                        │  Look up by email          │                │
│      │                        │───────────────────────────►│                │
│      │                        │◄───────────────────────────│                │
│      │                        │                            │                │
│      │                        │  Check: active? not locked?│                │
│      │                        │                            │                │
│      │                        │  Verify password hash      │                │
│      │                        │                            │                │
│      │                        │ ┌─────────────────────────┐│                │
│      │                        │ │ SUCCESS:                ││                │
│      │                        │ │ • Reset failed attempts ││                │
│      │                        │ │ • Record login time/IP  ││                │
│      │                        │ │ • Generate JWT token    ││                │
│      │                        │ └─────────────────────────┘│                │
│      │                        │                            │                │
│      │                        │ ┌─────────────────────────┐│                │
│      │                        │ │ FAILURE:                ││                │
│      │                        │ │ • Increment attempts    ││                │
│      │                        │ │ • Lock if threshold met ││                │
│      │                        │ └─────────────────────────┘│                │
│      │                        │                            │                │
│      │  Return token + user   │                            │                │
│      │◄───────────────────────│                            │                │
│                                                                             │
│                                                                             │
│  AUTHENTICATED REQUEST                                                      │
│  ═════════════════════                                                      │
│                                                                             │
│    Client                   System                      Database            │
│      │                        │                            │                │
│      │  Request + JWT token   │                            │                │
│      │───────────────────────►│                            │                │
│      │                        │                            │                │
│      │                        │  Verify token signature    │                │
│      │                        │  Check not expired         │                │
│      │                        │                            │                │
│      │                        │  Load user from token ID   │                │
│      │                        │───────────────────────────►│                │
│      │                        │◄───────────────────────────│                │
│      │                        │                            │                │
│      │                        │  Verify user still active  │                │
│      │                        │                            │                │
│      │                        │  Process request with      │                │
│      │                        │  authenticated user        │                │
│      │                        │                            │                │
│      │  Response              │                            │                │
│      │◄───────────────────────│                            │                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Purchase Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PURCHASE FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    Consumer          Platform           Product          Payment            │
│       │                 │                  │                │               │
│       │  Place order    │                  │                │               │
│       │────────────────►│                  │                │               │
│       │                 │                  │                │               │
│       │                 │  Validate user   │                │               │
│       │                 │  (active, not    │                │               │
│       │                 │   suspended)     │                │               │
│       │                 │                  │                │               │
│       │                 │  For each item:  │                │               │
│       │                 │  ─────────────── │                │               │
│       │                 │                  │                │               │
│       │                 │  Check exists    │                │               │
│       │                 │─────────────────►│                │               │
│       │                 │                  │                │               │
│       │                 │  Reserve stock   │                │               │
│       │                 │─────────────────►│                │               │
│       │                 │  (prevents       │                │               │
│       │                 │   overselling)   │                │               │
│       │                 │                  │                │               │
│       │                 │  Capture product │                │               │
│       │                 │  snapshot        │                │               │
│       │                 │◄─────────────────│                │               │
│       │                 │                  │                │               │
│       │                 │  Calculate totals│                │               │
│       │                 │  (items + tax +  │                │               │
│       │                 │   shipping)      │                │               │
│       │                 │                  │                │               │
│       │                 │  Process payment │                │               │
│       │                 │─────────────────────────────────►│               │
│       │                 │                  │                │               │
│       │                 │◄─────────────────────────────────│               │
│       │                 │  Payment result  │                │               │
│       │                 │                  │                │               │
│       │                 │ ┌──────────────────────────────┐ │               │
│       │                 │ │ If payment fails:            │ │               │
│       │                 │ │ • Release reserved stock     │ │               │
│       │                 │ │ • Return error to user       │ │               │
│       │                 │ └──────────────────────────────┘ │               │
│       │                 │                  │                │               │
│       │                 │ ┌──────────────────────────────┐ │               │
│       │                 │ │ If payment succeeds:         │ │               │
│       │                 │ │ • Create order (CONFIRMED)   │ │               │
│       │                 │ │ • Record attribution         │ │               │
│       │                 │ │ • Update user stats          │ │               │
│       │                 │ │ • Update promotion stats     │ │               │
│       │                 │ └──────────────────────────────┘ │               │
│       │                 │                  │                │               │
│       │  Order confirmed│                  │                │               │
│       │◄────────────────│                  │                │               │
│                                                                             │
│                                                                             │
│  POST-ORDER: FULFILLMENT                                                    │
│  ═══════════════════════                                                    │
│                                                                             │
│  Each supplier independently:                                               │
│  1. Sees order items for their products                                     │
│  2. Processes (prepares shipment)                                           │
│  3. Ships (provides tracking)                                               │
│  4. Marks delivered                                                         │
│                                                                             │
│  Order status aggregates item statuses.                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Promotion Approval Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PROMOTION APPROVAL FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    Supplier             Platform              Admin              Leader     │
│       │                    │                    │                   │       │
│       │  Create promotion  │                    │                   │       │
│       │   (DRAFT)          │                    │                   │       │
│       │───────────────────►│                    │                   │       │
│       │                    │                    │                   │       │
│       │                    │  Validate:         │                   │       │
│       │                    │  • Supplier        │                   │       │
│       │                    │    verified        │                   │       │
│       │                    │  • Products exist  │                   │       │
│       │                    │  • Products owned  │                   │       │
│       │                    │                    │                   │       │
│       │  Promotion created │                    │                   │       │
│       │◄───────────────────│                    │                   │       │
│       │                    │                    │                   │       │
│       │  Submit for        │                    │                   │       │
│       │  approval          │                    │                   │       │
│       │───────────────────►│                    │                   │       │
│       │                    │                    │                   │       │
│       │                    │  Status: PENDING   │                   │       │
│       │                    │                    │                   │       │
│       │                    │  If global         │                   │       │
│       │                    │  visibility:       │                   │       │
│       │                    │─────────────────►  │                   │       │
│       │                    │  Queue for admin   │                   │       │
│       │                    │                    │                   │       │
│       │                    │                    │  Review &         │       │
│       │                    │                    │  Approve/Reject   │       │
│       │                    │◄───────────────────│                   │       │
│       │                    │                    │                   │       │
│       │                    │  If community      │                   │       │
│       │                    │  visibility:       │                   │       │
│       │                    │────────────────────────────────────►   │       │
│       │                    │  Queue for leader  │                   │       │
│       │                    │                    │                   │       │
│       │                    │                    │    Review &       │       │
│       │                    │                    │    Approve/Reject │       │
│       │                    │◄────────────────────────────────────   │       │
│       │                    │                    │                   │       │
│       │                    │ ┌────────────────────────────────────┐ │       │
│       │                    │ │ When all required approvals done:  │ │       │
│       │                    │ │                                    │ │       │
│       │                    │ │ If start_date in future:           │ │       │
│       │                    │ │   Status → SCHEDULED               │ │       │
│       │                    │ │                                    │ │       │
│       │                    │ │ If start_date now or past:         │ │       │
│       │                    │ │   Status → ACTIVE                  │ │       │
│       │                    │ │   Record first_activated_at        │ │       │
│       │                    │ │   (immutable - marks "sent")       │ │       │
│       │                    │ └────────────────────────────────────┘ │       │
│       │                    │                    │                   │       │
│       │  Promotion active  │                    │                   │       │
│       │◄───────────────────│                    │                   │       │
│                                                                             │
│                                                                             │
│  KEY INSIGHT: first_activated_at                                            │
│  ═══════════════════════════════                                            │
│                                                                             │
│  Once a promotion goes ACTIVE, first_activated_at is set and NEVER changes. │
│  This is the "point of no return" - the promotion has been "sent" to users. │
│                                                                             │
│  Even if paused and resumed, this timestamp remains.                        │
│  Used for analytics: "When did users first see this?"                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Architectural Principles

### 6.1 Data Integrity Patterns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA INTEGRITY PATTERNS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│  OPTIMISTIC LOCKING                                                         │
│  ══════════════════                                                         │
│                                                                             │
│  PROBLEM: Two users edit the same document simultaneously.                  │
│           Last write wins, first user's changes are lost.                   │
│                                                                             │
│  SOLUTION: Every document has a version number.                             │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │                                                                 │      │
│    │   User A reads document (version: 5)                            │      │
│    │   User B reads document (version: 5)                            │      │
│    │                                                                 │      │
│    │   User A submits update with version 5                          │      │
│    │   System: version matches → accept, set version to 6            │      │
│    │                                                                 │      │
│    │   User B submits update with version 5                          │      │
│    │   System: expected 6, got 5 → REJECT (stale data)               │      │
│    │   User B must reload and retry                                  │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  APPLIED TO: User, Supplier, Product, Promotion, Post, Community, Order     │
│                                                                             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│                                                                             │
│  SOFT DELETE                                                                │
│  ═══════════                                                                │
│                                                                             │
│  PROBLEM: Deleting data loses audit trail, breaks references,               │
│           makes compliance difficult.                                       │
│                                                                             │
│  SOLUTION: Never physically delete. Mark as deleted instead.                │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │                                                                 │      │
│    │   Document {                                                    │      │
│    │     ...data...                                                  │      │
│    │     status: "active" | "deleted"                                │      │
│    │     deleted_at: null | timestamp                                │      │
│    │   }                                                             │      │
│    │                                                                 │      │
│    │   All queries automatically filter: deleted_at = null           │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  BENEFITS:                                                                  │
│  • Audit trail preserved                                                    │
│  • Can "undelete" if needed                                                 │
│  • References remain valid (can show "deleted user" instead of error)       │
│  • Compliance with data retention requirements                              │
│                                                                             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│                                                                             │
│  IMMUTABLE SNAPSHOTS                                                        │
│  ═══════════════════                                                        │
│                                                                             │
│  PROBLEM: Product price changes. What did the customer actually pay?        │
│           Product name changes. What did they actually order?               │
│                                                                             │
│  SOLUTION: Capture state at significant moments. Never modify.              │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │                                                                 │      │
│    │   Order Item {                                                  │      │
│    │     product_snapshot: {                                         │      │
│    │       product_id: "abc123"                                      │      │
│    │       product_name: "Red Running Shoes"  ← Name AT PURCHASE     │      │
│    │       original_price: 9999               ← Price AT PURCHASE    │      │
│    │       image_url: "..."                   ← Image AT PURCHASE    │      │
│    │       snapshot_at: "2024-02-05T10:30:00Z"                       │      │
│    │     }                                                           │      │
│    │     quantity: 2                                                 │      │
│    │     unit_price: 9999                                            │      │
│    │   }                                                             │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  USED IN:                                                                   │
│  • Orders: What did customer buy?                                           │
│  • Promotions: What products were featured?                                 │
│                                                                             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                             │
│                                                                             │
│  DENORMALIZED STATISTICS                                                    │
│  ════════════════════════                                                   │
│                                                                             │
│  PROBLEM: "How many followers does this user have?"                         │
│           Counting every time = slow, expensive at scale.                   │
│                                                                             │
│  SOLUTION: Store pre-computed counts. Update on change.                     │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │                                                                 │      │
│    │   User {                                                        │      │
│    │     ...                                                         │      │
│    │     stats: {                                                    │      │
│    │       follower_count: 50000     ← Pre-computed                  │      │
│    │       following_count: 150      ← Pre-computed                  │      │
│    │       total_orders: 45          ← Pre-computed                  │      │
│    │     }                                                           │      │
│    │   }                                                             │      │
│    │                                                                 │      │
│    │   When someone follows: follower_count += 1                     │      │
│    │   No need to count on every read!                               │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  TRADEOFF: Slight complexity on writes for fast reads.                      │
│  Worth it because reads vastly outnumber writes.                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Status State Machine Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STATUS STATE MACHINE PATTERN                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRINCIPLE                                                                  │
│  ═════════                                                                  │
│                                                                             │
│  Every entity with a lifecycle uses explicit status states.                 │
│  Transitions between states are validated—not all paths are allowed.        │
│                                                                             │
│                                                                             │
│  WHY STATE MACHINES?                                                        │
│  ═══════════════════                                                        │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │                                                                 │      │
│    │  WITHOUT state machine:                                         │      │
│    │                                                                 │      │
│    │    order.status = "shipped"  ← Can set anything, anytime!       │      │
│    │    order.status = "pending"  ← Wait, it was already shipped?    │      │
│    │                                                                 │      │
│    │  WITH state machine:                                            │      │
│    │                                                                 │      │
│    │    order.ship()  ← Only works if status allows shipping         │      │
│    │                  ← Validates preconditions                       │      │
│    │                  ← Records the transition                        │      │
│    │                                                                 │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│                                                                             │
│  VALID TRANSITIONS ARE EXPLICIT                                             │
│  ══════════════════════════════                                             │
│                                                                             │
│  Each entity defines what transitions are legal:                            │
│                                                                             │
│    PROMOTION:                                                               │
│    • DRAFT → PENDING_APPROVAL (submit)                                      │
│    • PENDING_APPROVAL → SCHEDULED (approve with future date)                │
│    • PENDING_APPROVAL → ACTIVE (approve with past/current date)             │
│    • PENDING_APPROVAL → REJECTED (reject)                                   │
│    • SCHEDULED → ACTIVE (start date reached)                                │
│    • ACTIVE → PAUSED (pause)                                                │
│    • PAUSED → ACTIVE (resume)                                               │
│    • ACTIVE → ENDED (end date reached)                                      │
│    • Any → CANCELLED (cancel)                                               │
│                                                                             │
│    INVALID: ENDED → ACTIVE (can't restart ended promotion)                  │
│    INVALID: REJECTED → ACTIVE (must resubmit)                               │
│                                                                             │
│                                                                             │
│  BENEFITS                                                                   │
│  ════════                                                                   │
│                                                                             │
│  • Prevents invalid states (can't ship an unconfirmed order)                │
│  • Documents the lifecycle visually                                         │
│  • Enables audit trail (record each transition)                             │
│  • Simplifies debugging (state is always known and valid)                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Embedding vs Referencing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   EMBEDDING VS REFERENCING                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MongoDB allows two ways to relate data:                                    │
│                                                                             │
│                                                                             │
│  EMBEDDING (data inside document)                                           │
│  ═════════════════════════════════                                          │
│                                                                             │
│    User {                                                                   │
│      name: "John"                                                           │
│      profile: {           ◄── Embedded                                      │
│        bio: "..."                                                           │
│        avatar: "..."                                                        │
│      }                                                                      │
│      stats: {             ◄── Embedded                                      │
│        followers: 5000                                                      │
│      }                                                                      │
│    }                                                                        │
│                                                                             │
│    WHEN TO USE:                                                             │
│    • Data always accessed together (user + profile)                         │
│    • Data "belongs to" parent (profile IS part of user)                     │
│    • Data doesn't grow unboundedly                                          │
│    • Atomic updates needed (update user + stats together)                   │
│                                                                             │
│                                                                             │
│  REFERENCING (ID pointing to another document)                              │
│  ═════════════════════════════════════════════                              │
│                                                                             │
│    Post {                                                                   │
│      author_id: "user123"  ◄── Reference                                    │
│      community_id: "comm456"  ◄── Reference                                 │
│      content: "..."                                                         │
│    }                                                                        │
│                                                                             │
│    WHEN TO USE:                                                             │
│    • Data accessed independently (load post without user)                   │
│    • Many-to-many relationships (user in many communities)                  │
│    • Data grows unboundedly (community has unlimited posts)                 │
│    • Different access patterns (posts queried separately)                   │
│                                                                             │
│                                                                             │
│  THIS SYSTEM'S APPROACH                                                     │
│  ══════════════════════                                                     │
│                                                                             │
│    EMBEDDED:                                                                │
│    • User ← profile, permissions, stats, security                           │
│    • Product ← variants, images, shipping info                              │
│    • Order ← items with product snapshots                                   │
│    • Promotion ← products with snapshots, approval records                  │
│                                                                             │
│    REFERENCED:                                                              │
│    • Post → author (user_id), community (community_id)                      │
│    • Community → owner (user_id), members (user_id[])                       │
│    • Order → customer (user_id)                                             │
│    • Product → supplier (supplier_id)                                       │
│                                                                             │
│    HYBRID (reference + denormalized copy):                                  │
│    • Post.author: { user_id, display_name, avatar }                         │
│      Why? Display name shown with every post, avoid lookup                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Design Decisions & Rationale

### 7.1 Why Separate Supplier from User?

| Consideration | User | Supplier |
|---------------|------|----------|
| **Identity** | Person | Business |
| **Verification** | Email only | Business documents, tax ID |
| **Banking** | Not needed | Required for payouts |
| **Permissions** | Post, comment, buy | List products, create promotions |
| **Lifecycle** | Sign up → Active | Sign up → Verification → Active |

**Decision:** Keep them separate. Avoids complex conditionals ("if user is supplier...") throughout codebase.

### 7.2 Why FeedItem Separate from Post?

**Problem:** Loading a feed with 50 posts requires:
1. Query posts
2. For each post, get author info
3. Sort, filter, paginate

At scale, this becomes slow.

**Solution:** FeedItem is a denormalized "card" for fast display:
- Contains preview data (title, author name, thumbnail)
- No joins needed
- Clicking loads full Post

**Tradeoff:** Slight data duplication, but massive read performance improvement.

### 7.3 Why Approval Workflow for Promotions?

**Business Need:** Quality control. Not every promotion should reach users.

**Global promotions** affect everyone → Admin approval required
**Community promotions** affect leader's audience → Leader approval required

This protects:
- Consumers from spam
- Leaders from unwanted content in their communities
- Platform reputation

### 7.4 Why Immutable first_activated_at?

**Scenario:** Supplier creates promotion, it goes active, then pauses it, then resumes.

**Question:** For analytics, when did users "first see" this promotion?

**Answer:** The first time it went active. Not when resumed.

`first_activated_at` captures this moment and never changes, even through pause/resume cycles.

### 7.5 Why Store Product Snapshots in Orders?

**Scenario:** Customer buys "Red Shoes" for $99. Next week, supplier changes name to "Crimson Running Shoes" and price to $129.

**Question:** What did the customer actually buy?

**Without snapshot:** Order shows "Crimson Running Shoes, $129" — wrong!
**With snapshot:** Order shows "Red Shoes, $99" — correct, forever.

Essential for:
- Customer receipts
- Dispute resolution
- Historical analytics
- Legal compliance

---

## 8. Event-Driven Architecture

### 8.1 Why Events?

The platform needs to:
- Build read-optimized views (feeds, cards, order histories)
- Track analytics (revenue, user lifecycle, conversion funnels)
- Maintain audit trails

**Synchronous approach problems:**
- Service coupling (every write must update all dependent views)
- Performance degradation as views multiply
- Difficult to add new analytics without touching core services

**Event-driven solution:**
- Services emit domain events on state changes
- Consumers build read models independently
- New consumers can be added without modifying producers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EVENT-DRIVEN DATA FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    WRITE PATH                           READ PATH                           │
│    ══════════                           ═════════                           │
│                                                                             │
│    API Request                          Client Query                        │
│         │                                    │                              │
│         ▼                                    ▼                              │
│    ┌─────────┐                         ┌─────────────┐                      │
│    │ Service │                         │ Read Models │ ◄── Fast, denormalized│
│    └────┬────┘                         └─────────────┘                      │
│         │                                    ▲                              │
│         ▼                                    │                              │
│    ┌──────────────────────┐                  │                              │
│    │ ATOMIC TRANSACTION   │                  │                              │
│    │                      │                  │                              │
│    │  Entity + Outbox     │                  │                              │
│    └──────────┬───────────┘                  │                              │
│               │                              │                              │
│               │ (async)                      │                              │
│               ▼                              │                              │
│    ┌──────────────────────┐                  │                              │
│    │   Outbox Publisher   │                  │                              │
│    └──────────┬───────────┘                  │                              │
│               │                              │                              │
│               ▼                              │                              │
│    ┌──────────────────────┐                  │                              │
│    │       KAFKA          │                  │                              │
│    │                      │                  │                              │
│    │   Domain Events      │                  │                              │
│    └──────────┬───────────┘                  │                              │
│               │                              │                              │
│               ▼                              │                              │
│    ┌──────────────────────┐                  │                              │
│    │     Consumers        │ ─────────────────┘                              │
│    │                      │                                                 │
│    │  Projections         │ ──► user_cards, feed_items, order_summaries     │
│    │  Analytics           │ ──► daily metrics, funnels, revenue             │
│    └──────────────────────┘                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Transactional Outbox Pattern

**Problem:** How to reliably publish events after a database write?

**Naive approach (dual write):**
1. Update database
2. Publish to Kafka ← **If this fails, event is lost**

**Outbox pattern:**
1. Update entity + insert outbox record in **same transaction**
2. Background worker polls outbox and publishes to Kafka
3. Mark outbox record as published

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TRANSACTIONAL OUTBOX                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SERVICE                                                                    │
│   ═══════                                                                    │
│                                                                             │
│   async def verify_user(user_id, session):                                   │
│       # Single atomic transaction                                            │
│       user.status = "active"                                                 │
│       user.version += 1                                                      │
│       await user.save(session=session)                                       │
│                                                                             │
│       outbox_record = OutboxRecord(                                          │
│           event_type="user.verified",                                        │
│           entity_id=user_id,                                                 │
│           payload={...}                                                      │
│       )                                                                      │
│       await outbox_record.insert(session=session)                            │
│                                                                             │
│       # Both writes succeed or both fail                                     │
│                                                                             │
│                                                                             │
│   OUTBOX PUBLISHER (Background Worker)                                       │
│   ════════════════════════════════════                                       │
│                                                                             │
│   while running:                                                             │
│       records = fetch_pending()      # Lock records for processing           │
│       for record in records:                                                 │
│           kafka.publish(record)      # At-least-once delivery               │
│           mark_published(record)                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Domain Events

Each entity emits events on state changes. Events are named `{entity}.{action}`:

| Entity | Events |
|--------|--------|
| **User** | `user.created`, `user.verified`, `user.profile_updated`, `user.suspended`, `user.deleted` |
| **Supplier** | `supplier.created`, `supplier.submitted`, `supplier.verified`, `supplier.rejected` |
| **Community** | `community.created`, `community.updated`, `community.member_joined`, `community.deleted` |
| **Product** | `product.created`, `product.published`, `product.inventory_updated`, `product.deleted` |
| **Promotion** | `promotion.created`, `promotion.activated`, `promotion.ended` |
| **Post** | `post.created`, `post.published`, `post.global_approved`, `post.deleted` |
| **Order** | `order.created`, `order.payment_succeeded`, `order.confirmed`, `order.shipped`, `order.delivered` |

### 8.4 Projections (Read Models)

Consumers build denormalized read models for fast queries:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROJECTIONS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   COLLECTION          │  BUILT FROM              │  OPTIMIZED FOR            │
│   ════════════════════│══════════════════════════│═══════════════════════════│
│                       │                          │                           │
│   user_cards          │  user.* events           │  Profile card display     │
│                       │                          │  Follower counts          │
│                       │                          │                           │
│   feed_items          │  post.* + promotion.*    │  Feed pagination          │
│                       │  events                  │  Global/community feeds   │
│                       │                          │                           │
│   order_summaries     │  order.* events          │  Customer order history   │
│                       │                          │  Supplier fulfillment     │
│                       │                          │                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Idempotency:** Each projection tracks `entity_version`. Events with version ≤ stored version are skipped (handles duplicates and out-of-order delivery).

### 8.5 Analytics

Consumers aggregate events into daily metrics:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ANALYTICS                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   COLLECTION               │  METRICS                                        │
│   ═════════════════════════│═════════════════════════════════════════════════│
│                            │                                                 │
│   analytics_user_lifecycle │  Daily registrations, verifications             │
│                            │  Suspensions, deletions, login stats            │
│                            │                                                 │
│   analytics_order_funnel   │  Orders created → Payment → Confirmed →         │
│                            │  Shipped → Delivered (conversion rates)         │
│                            │                                                 │
│   analytics_revenue        │  Daily gross/net revenue                        │
│                            │  Revenue by community, by promotion             │
│                            │                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.6 Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       KAFKA INFRASTRUCTURE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   COMPONENT                │  CONFIGURATION                                  │
│   ═════════════════════════│═════════════════════════════════════════════════│
│                            │                                                 │
│   Kafka Broker             │  Confluent (KRaft mode, no Zookeeper)           │
│                            │  Auto-create topics enabled                     │
│                            │  Default 3 partitions                           │
│                            │                                                 │
│   Topics                   │  sc.domain.{entity} - Domain events             │
│                            │  Partitioned by entity_id                       │
│                            │                                                 │
│   Consumer Groups          │  sc-proj-{name} - Projection consumers          │
│                            │  sc-analytics-{name} - Analytics consumers      │
│                            │                                                 │
│   Delivery Guarantee       │  At-least-once (idempotent consumers)           │
│                            │  Manual offset commit after processing          │
│                            │                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture prioritizes:

1. **Clarity** — Each layer, each entity has one clear purpose
2. **Data Integrity** — Optimistic locking, soft delete, immutable snapshots
3. **Performance** — Denormalized stats, feed items, strategic embedding
4. **Business Alignment** — Domain model mirrors real-world stakeholder relationships
5. **Maintainability** — Consistent patterns, explicit state machines, clear separation

When extending this system, follow the established patterns:
- New entity? Define its lifecycle states
- New feature? Determine which layer owns which responsibility
- New relationship? Decide embed vs reference based on access patterns
- New statistic? Denormalize if read-heavy
