# MySQL Analytics Service - Implementation Strategy

## Overview

This document outlines the strategy for building Kafka consumers that flatten domain events into MySQL analytics tables.

**Architecture Pattern:**
```
Kafka Topic → Consumer (flattens data) → DAL (SQL operations) → MySQL Tables
```

---

## Topics & Events Summary

| Topic | Events | Total |
|-------|--------|-------|
| USER | registered, login, account_locked, password_reset_requested, password_reset | 5 |
| SUPPLIER | registered, login | 2 |
| ORDER | created, completed, cancelled | 3 |
| POST | created, deleted, hidden, global_distribution_approved | 4 |
| PRODUCT | created, published, discontinued, out_of_stock, deleted | 5 |
| PROMOTION | created, submitted, approved, rejected, paused, resumed, cancelled, ended | 8 |
| COMMUNITY | created, member_joined, member_left, suspended | 4 |

**Total: 31 events**

---

## Project Structure

```
apps/mysql-service/
├── src/
│   ├── db/
│   │   └── connection.py           # MySQL connection pool
│   ├── dal/                         # Data Access Layer
│   │   ├── user_dal.py
│   │   ├── supplier_dal.py
│   │   ├── order_dal.py
│   │   ├── post_dal.py
│   │   ├── product_dal.py
│   │   ├── promotion_dal.py
│   │   └── community_dal.py
│   ├── consumers/                   # Event consumers (flatten data)
│   │   ├── auth_consumer.py         # USER topic
│   │   ├── supplier_consumer.py     # SUPPLIER topic
│   │   ├── order_consumer.py        # ORDER topic
│   │   ├── post_consumer.py         # POST topic
│   │   ├── product_consumer.py      # PRODUCT topic
│   │   ├── promotion_consumer.py    # PROMOTION topic
│   │   └── community_consumer.py    # COMMUNITY topic
│   └── kafka/
│       └── consumer.py
├── main.py
├── requirements.txt
└── Dockerfile
```

---

## Table Designs (Flattened)

### 1. USER Tables

```sql
-- Users (from user.registered - full entity)
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    role ENUM('consumer', 'leader'),
    status ENUM('pending', 'active', 'suspended', 'deleted'),
    avatar VARCHAR(500),
    bio TEXT,
    phone VARCHAR(50),
    -- Leader business info (flattened)
    business_name VARCHAR(200),
    business_type VARCHAR(50),
    country VARCHAR(2),
    city VARCHAR(100),
    state VARCHAR(100),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User logins (from user.login - summary)
CREATE TABLE user_logins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50),
    ip_address VARCHAR(50),
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User events (generic log)
CREATE TABLE user_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. SUPPLIER Tables

```sql
-- Suppliers (from supplier.registered - full entity)
CREATE TABLE suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    contact_person_name VARCHAR(100),
    contact_person_title VARCHAR(100),
    -- Company info (flattened)
    legal_name VARCHAR(200),
    company_type VARCHAR(50),
    tax_id VARCHAR(50),
    tax_id_country VARCHAR(2),
    -- Address (flattened)
    street_address VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(2),
    -- Business info (flattened)
    industry_category VARCHAR(100),
    description TEXT,
    website VARCHAR(500),
    -- Status
    status VARCHAR(50),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supplier logins
CREATE TABLE supplier_logins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    company_name VARCHAR(200),
    ip_address VARCHAR(50),
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supplier events
CREATE TABLE supplier_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. ORDER Tables

```sql
-- Orders (from order.created - full entity)
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL UNIQUE,
    order_number VARCHAR(50) NOT NULL,
    -- Customer (flattened)
    customer_id VARCHAR(50),
    customer_email VARCHAR(255),
    customer_name VARCHAR(100),
    -- Totals (flattened)
    subtotal_cents INT,
    discount_cents INT,
    shipping_cents INT,
    tax_cents INT,
    total_cents INT,
    currency VARCHAR(3),
    -- Shipping address (flattened)
    shipping_street VARCHAR(200),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_zip VARCHAR(20),
    shipping_country VARCHAR(2),
    -- Status
    status VARCHAR(50),
    item_count INT,
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order items (from order.created - denormalized)
CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    product_id VARCHAR(50),
    product_name VARCHAR(200),
    variant_id VARCHAR(50),
    quantity INT,
    unit_price_cents INT,
    total_cents INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order events
CREATE TABLE order_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. POST Tables

```sql
-- Posts (from post.created - full entity)
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id VARCHAR(50) NOT NULL UNIQUE,
    post_type ENUM('text', 'image', 'video', 'poll', 'link'),
    -- Author (flattened)
    author_id VARCHAR(50),
    author_type ENUM('user', 'community'),
    author_name VARCHAR(100),
    -- Content
    text_content TEXT,
    -- Community
    community_id VARCHAR(50),
    community_name VARCHAR(100),
    -- Status
    status VARCHAR(50),
    -- Stats (flattened)
    likes_count INT DEFAULT 0,
    comments_count INT DEFAULT 0,
    shares_count INT DEFAULT 0,
    views_count INT DEFAULT 0,
    -- Global distribution
    global_status VARCHAR(50),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    published_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Post events
CREATE TABLE post_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    actor_id VARCHAR(50),
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. PRODUCT Tables

```sql
-- Products (from product.created - full entity)
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    supplier_id VARCHAR(50) NOT NULL,
    name VARCHAR(200),
    slug VARCHAR(200),
    category VARCHAR(100),
    subcategory VARCHAR(100),
    base_price_cents INT,
    currency VARCHAR(3),
    description TEXT,
    status VARCHAR(50),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product events
CREATE TABLE product_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    supplier_id VARCHAR(50),
    event_type VARCHAR(100),
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6. PROMOTION Tables

```sql
-- Promotions (from promotion.created - full entity)
CREATE TABLE promotions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    promotion_id VARCHAR(50) NOT NULL UNIQUE,
    promotion_type ENUM('single', 'campaign', 'default'),
    title VARCHAR(200),
    description TEXT,
    -- Supplier (flattened)
    supplier_id VARCHAR(50),
    supplier_name VARCHAR(200),
    -- Visibility
    visibility_type VARCHAR(50),
    -- Schedule (flattened)
    start_date DATETIME,
    end_date DATETIME,
    -- Status
    status VARCHAR(50),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Promotion events
CREATE TABLE promotion_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    promotion_id VARCHAR(50) NOT NULL,
    supplier_id VARCHAR(50),
    event_type VARCHAR(100),
    reviewer_id VARCHAR(50),
    reason TEXT,
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7. COMMUNITY Tables

```sql
-- Communities (from community.created - full entity)
CREATE TABLE communities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    community_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100),
    slug VARCHAR(100),
    description TEXT,
    -- Owner (flattened)
    owner_id VARCHAR(50),
    owner_name VARCHAR(100),
    -- Settings
    visibility VARCHAR(50),
    requires_approval BOOLEAN,
    -- Stats
    member_count INT DEFAULT 0,
    -- Status
    status VARCHAR(50),
    -- Metadata
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Community membership events
CREATE TABLE community_memberships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    community_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    action ENUM('joined', 'left'),
    member_count INT,
    event_id VARCHAR(50),
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Community events
CREATE TABLE community_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    community_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    admin_id VARCHAR(50),
    reason TEXT,
    event_id VARCHAR(50),
    event_data JSON,
    event_timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## DAL Responsibilities

Each DAL handles all SQL operations for its domain:

| DAL | Methods |
|-----|---------|
| **UserDAL** | insert_user, insert_login, insert_event, update_status |
| **SupplierDAL** | insert_supplier, insert_login, insert_event, update_status |
| **OrderDAL** | insert_order, insert_order_items, insert_event, update_status |
| **PostDAL** | insert_post, insert_event, update_status, update_global_status |
| **ProductDAL** | insert_product, insert_event, update_status |
| **PromotionDAL** | insert_promotion, insert_event, update_status |
| **CommunityDAL** | insert_community, insert_membership, insert_event, update_status |

---

## Consumer Responsibilities

Each consumer:
1. Receives event from Kafka
2. Extracts and flattens nested data
3. Calls appropriate DAL method

| Consumer | Topic | Handlers |
|----------|-------|----------|
| **AuthConsumer** | USER | handle_user_registered, handle_user_login, handle_account_locked, handle_password_reset_requested, handle_password_reset |
| **SupplierConsumer** | SUPPLIER | handle_supplier_registered, handle_supplier_login |
| **OrderConsumer** | ORDER | handle_order_created, handle_order_completed, handle_order_cancelled |
| **PostConsumer** | POST | handle_post_created, handle_post_deleted, handle_post_hidden, handle_global_distribution_approved |
| **ProductConsumer** | PRODUCT | handle_product_created, handle_product_published, handle_product_discontinued, handle_product_out_of_stock, handle_product_deleted |
| **PromotionConsumer** | PROMOTION | handle_promotion_created, handle_promotion_submitted, handle_promotion_approved, handle_promotion_rejected, handle_promotion_paused, handle_promotion_resumed, handle_promotion_cancelled, handle_promotion_ended |
| **CommunityConsumer** | COMMUNITY | handle_community_created, handle_member_joined, handle_member_left, handle_community_suspended |

---

## Implementation Order

### Phase 1: Core (Done)
- [x] USER topic (auth_consumer + user_dal)

### Phase 2: Commerce
- [ ] ORDER topic (order_consumer + order_dal)
- [ ] PRODUCT topic (product_consumer + product_dal)
- [ ] PROMOTION topic (promotion_consumer + promotion_dal)

### Phase 3: Social
- [ ] POST topic (post_consumer + post_dal)
- [ ] COMMUNITY topic (community_consumer + community_dal)

### Phase 4: Suppliers
- [ ] SUPPLIER topic (supplier_consumer + supplier_dal)

---

## Key Design Principles

1. **Consumers flatten data** - Extract nested fields into flat columns
2. **DAL handles SQL** - All database operations in DAL layer
3. **Full entity on create** - Store complete data on creation events
4. **Summary on updates** - Store minimal data on status change events
5. **Generic event table** - Each domain has an events table for audit/analytics
6. **Idempotency** - Use event_id to prevent duplicate processing
