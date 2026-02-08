#!/bin/bash

# ============================================================================
# Order API Test Script (curl)
# ============================================================================

BASE_URL="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test data (will be populated during tests)
USER_ID=""
USER_EMAIL=""
SUPPLIER_ID=""
PRODUCT_ID=""
ORDER_ID=""
ORDER_NUMBER=""

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    ORDER API TEST SCRIPT${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

TIMESTAMP=$(date +%s)

# ============================================================================
# SETUP: Register User
# ============================================================================
echo -e "${YELLOW}=== SETUP: Register User ===${NC}"

USER_RESPONSE=$(curl -s -X POST "$BASE_URL/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"order_test_${TIMESTAMP}@example.com\",
    \"password\": \"OrderTest#Pass123!\",
    \"display_name\": \"Order Test User\",
    \"terms_accepted\": true,
    \"privacy_policy_accepted\": true
  }")

echo "Register Response:"
echo "$USER_RESPONSE" | jq .

USER_ID=$(echo "$USER_RESPONSE" | jq -r '.user.id')
USER_EMAIL="order_test_${TIMESTAMP}@example.com"

if [ "$USER_ID" == "null" ] || [ -z "$USER_ID" ]; then
  echo -e "${RED}Failed to register user. Aborting.${NC}"
  exit 1
fi

echo -e "${GREEN}User ID: $USER_ID${NC}"
echo ""

# ============================================================================
# SETUP: Register Supplier
# ============================================================================
echo -e "${YELLOW}=== SETUP: Register Supplier ===${NC}"

SUPPLIER_RESPONSE=$(curl -s -X POST "$BASE_URL/supplier/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"primary_email\": \"order_supplier_${TIMESTAMP}@supplier.com\",
    \"phone\": \"+1-555-0199\",
    \"contact_person_name\": \"Order Test Supplier\",
    \"contact_person_title\": \"Sales Manager\",
    \"legal_name\": \"Order Test Supplier ${TIMESTAMP}\",
    \"company_type\": \"corporation\",
    \"tax_id\": \"88-${TIMESTAMP: -7}\",
    \"tax_id_country\": \"US\",
    \"street_address\": \"789 Order Street\",
    \"city\": \"Los Angeles\",
    \"state\": \"CA\",
    \"zip_code\": \"90001\",
    \"country\": \"US\",
    \"industry_category\": \"electronics\",
    \"description\": \"Test supplier for order testing\",
    \"website\": \"https://order-test-supplier.com\",
    \"password\": \"OrderSupplier#Pass123!\",
    \"terms_accepted\": true,
    \"privacy_policy_accepted\": true
  }")

echo "Register Response:"
echo "$SUPPLIER_RESPONSE" | jq .

SUPPLIER_ID=$(echo "$SUPPLIER_RESPONSE" | jq -r '.supplier.id')

if [ "$SUPPLIER_ID" == "null" ] || [ -z "$SUPPLIER_ID" ]; then
  echo -e "${RED}Failed to register supplier. Aborting.${NC}"
  exit 1
fi

echo -e "${GREEN}Supplier ID: $SUPPLIER_ID${NC}"
echo ""

# ============================================================================
# SETUP: Verify Supplier in MongoDB (bypass for testing)
# ============================================================================
echo -e "${YELLOW}=== SETUP: Verify Supplier in MongoDB ===${NC}"

docker exec social_commerce_mongodb mongosh --quiet --eval "
db = db.getSiblingDB('social_commerce');
db.suppliers.updateOne(
  { _id: ObjectId('$SUPPLIER_ID') },
  {
    \$set: {
      'verification.verification_status': 'verified',
      'verification.verified_at': new Date()
    }
  }
);
print('Supplier verified');
"

echo -e "${GREEN}Supplier verified in database${NC}"
echo ""

# ============================================================================
# SETUP: Create Product
# ============================================================================
echo -e "${YELLOW}=== SETUP: Create Product ===${NC}"

PRODUCT_RESPONSE=$(curl -s -X POST "$BASE_URL/products" \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"name\": \"Order Test Widget ${TIMESTAMP}\",
    \"short_description\": \"Test product for order testing\",
    \"category\": \"electronics\",
    \"condition\": \"new\",
    \"base_price_cents\": 2999,
    \"currency\": \"USD\",
    \"base_sku\": \"ORDER-WIDGET-${TIMESTAMP}\",
    \"tags\": [\"test\", \"order\"],
    \"images\": [
      {
        \"url\": \"https://example.com/images/widget.jpg\",
        \"alt_text\": \"Order Test Widget\",
        \"order\": 0,
        \"is_primary\": true
      }
    ],
    \"shipping\": {
      \"free_shipping\": false,
      \"shipping_cost_cents\": 599,
      \"ships_from_country\": \"US\",
      \"ships_to_countries\": [\"US\", \"CA\"],
      \"estimated_delivery_days\": 5
    },
    \"stock_locations\": [
      {
        \"location_id\": \"warehouse-main\",
        \"location_name\": \"Main Warehouse\",
        \"city\": \"Los Angeles\",
        \"zip_code\": \"90001\",
        \"country\": \"US\",
        \"quantity\": 100,
        \"reserved\": 0
      }
    ]
  }")

echo "Product Response:"
echo "$PRODUCT_RESPONSE" | jq .

PRODUCT_ID=$(echo "$PRODUCT_RESPONSE" | jq -r '.id')

if [ "$PRODUCT_ID" == "null" ] || [ -z "$PRODUCT_ID" ]; then
  echo -e "${RED}Failed to create product. Aborting.${NC}"
  exit 1
fi

echo -e "${GREEN}Product ID: $PRODUCT_ID${NC}"
echo ""

# ============================================================================
# SETUP: Activate Product in MongoDB
# ============================================================================
echo -e "${YELLOW}=== SETUP: Activate Product in MongoDB ===${NC}"

docker exec social_commerce_mongodb mongosh --quiet --eval "
db = db.getSiblingDB('social_commerce');
db.products.updateOne(
  { _id: ObjectId('$PRODUCT_ID') },
  {
    \$set: {
      'status': 'active',
      'base_price_cents': 2999,
      'stock_locations': [{
        'location_id': 'warehouse-main',
        'location_name': 'Main Warehouse',
        'city': 'Los Angeles',
        'zip_code': '90001',
        'country': 'US',
        'quantity': 100,
        'reserved': 0
      }]
    }
  }
);
print('Product activated');
"

echo -e "${GREEN}Product activated in database${NC}"
echo ""

# ============================================================================
# 1. CREATE ORDER
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}1. CREATE ORDER${NC}"
echo -e "${BLUE}============================================${NC}"

IDEMPOTENCY_KEY="order-${TIMESTAMP}-001"

CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d "{
    \"items\": [
      {
        \"product_id\": \"$PRODUCT_ID\",
        \"quantity\": 2
      }
    ],
    \"shipping_address\": {
      \"recipient_name\": \"John Doe\",
      \"phone\": \"555-123-4567\",
      \"street_address_1\": \"123 Main Street\",
      \"street_address_2\": \"Apt 4B\",
      \"city\": \"New York\",
      \"state\": \"NY\",
      \"zip_code\": \"10001\",
      \"country\": \"US\",
      \"delivery_notes\": \"Leave at door\"
    },
    \"payment_info\": {
      \"payment_method\": \"credit_card\",
      \"payment_provider\": \"stripe\",
      \"card_last4\": \"4242\",
      \"card_brand\": \"Visa\"
    }
  }")

echo "Create Response:"
echo "$CREATE_RESPONSE" | jq .

ORDER_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
ORDER_NUMBER=$(echo "$CREATE_RESPONSE" | jq -r '.order_number')

if [ "$ORDER_ID" == "null" ] || [ -z "$ORDER_ID" ]; then
  echo -e "${RED}Failed to create order. Check error above.${NC}"
  exit 1
fi

echo -e "${GREEN}Order ID: $ORDER_ID${NC}"
echo -e "${GREEN}Order Number: $ORDER_NUMBER${NC}"
echo ""

# ============================================================================
# 2. TEST IDEMPOTENCY (same key returns same order)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}2. TEST IDEMPOTENCY${NC}"
echo -e "${BLUE}============================================${NC}"

IDEM_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d "{
    \"items\": [
      {
        \"product_id\": \"$PRODUCT_ID\",
        \"quantity\": 2
      }
    ],
    \"shipping_address\": {
      \"recipient_name\": \"John Doe\",
      \"phone\": \"555-123-4567\",
      \"street_address_1\": \"123 Main Street\",
      \"city\": \"New York\",
      \"state\": \"NY\",
      \"zip_code\": \"10001\",
      \"country\": \"US\"
    },
    \"payment_info\": {
      \"payment_method\": \"credit_card\",
      \"card_last4\": \"4242\",
      \"card_brand\": \"Visa\"
    }
  }")

IDEM_ORDER_ID=$(echo "$IDEM_RESPONSE" | jq -r '.id')

if [ "$IDEM_ORDER_ID" == "$ORDER_ID" ]; then
  echo -e "${GREEN}Idempotency works! Same order returned: $IDEM_ORDER_ID${NC}"
else
  echo -e "${RED}Idempotency failed! Different order: $IDEM_ORDER_ID${NC}"
fi
echo ""

# ============================================================================
# 3. LIST ORDERS
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}3. LIST ORDERS${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X GET "$BASE_URL/orders/list?limit=10" \
  -H "X-User-ID: $USER_ID" | jq .

echo ""

# ============================================================================
# 4. GET ORDER BY ID
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}4. GET ORDER BY ID${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/orders/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{\"order_id\": \"$ORDER_ID\"}" | jq .

echo ""

# ============================================================================
# 5. GET ORDER BY NUMBER
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}5. GET ORDER BY NUMBER${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/orders/get-by-number" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{\"order_number\": \"$ORDER_NUMBER\"}" | jq .

echo ""

# ============================================================================
# 6. UPDATE ORDER (modify pending order)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}6. UPDATE ORDER${NC}"
echo -e "${BLUE}============================================${NC}"

UPDATE_RESPONSE=$(curl -s -X POST "$BASE_URL/orders/update" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{
    \"order_id\": \"$ORDER_ID\",
    \"shipping_address\": {
      \"recipient_name\": \"Jane Doe\",
      \"phone\": \"555-987-6543\",
      \"street_address_1\": \"456 Oak Avenue\",
      \"city\": \"Brooklyn\",
      \"state\": \"NY\",
      \"zip_code\": \"11201\",
      \"country\": \"US\",
      \"delivery_notes\": \"Ring doorbell twice\"
    }
  }")

echo "$UPDATE_RESPONSE" | jq .

echo -e "${GREEN}Shipping address updated${NC}"
echo ""

# ============================================================================
# 7. COMPLETE ORDER
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}7. COMPLETE ORDER${NC}"
echo -e "${BLUE}============================================${NC}"

COMPLETE_KEY="complete-${TIMESTAMP}-001"

COMPLETE_RESPONSE=$(curl -s -X POST "$BASE_URL/orders/complete" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Idempotency-Key: $COMPLETE_KEY" \
  -d "{\"order_id\": \"$ORDER_ID\"}")

echo "$COMPLETE_RESPONSE" | jq .

COMPLETE_STATUS=$(echo "$COMPLETE_RESPONSE" | jq -r '.status')
PAYMENT_STATUS=$(echo "$COMPLETE_RESPONSE" | jq -r '.payment.status')

echo -e "${GREEN}Order Status: $COMPLETE_STATUS${NC}"
echo -e "${GREEN}Payment Status: $PAYMENT_STATUS${NC}"
echo ""

# ============================================================================
# 8. CANCEL ORDER (should fail - order is confirmed)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}8. CANCEL CONFIRMED ORDER (expected to succeed)${NC}"
echo -e "${BLUE}============================================${NC}"

CANCEL_RESPONSE=$(curl -s -X POST "$BASE_URL/orders/cancel" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{
    \"order_id\": \"$ORDER_ID\",
    \"reason\": \"Changed my mind about the purchase\"
  }")

echo "$CANCEL_RESPONSE" | jq .

CANCEL_STATUS=$(echo "$CANCEL_RESPONSE" | jq -r '.status')
if [ "$CANCEL_STATUS" == "cancelled" ]; then
  echo -e "${GREEN}Order cancelled successfully${NC}"
else
  echo -e "${YELLOW}Cancel result: $CANCEL_STATUS${NC}"
fi
echo ""

# ============================================================================
# 9. CREATE ANOTHER ORDER FOR PENDING CANCEL TEST
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}9. CREATE NEW ORDER FOR CANCEL TEST${NC}"
echo -e "${BLUE}============================================${NC}"

CANCEL_ORDER_KEY="order-${TIMESTAMP}-cancel"

CANCEL_ORDER_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Idempotency-Key: $CANCEL_ORDER_KEY" \
  -d "{
    \"items\": [
      {
        \"product_id\": \"$PRODUCT_ID\",
        \"quantity\": 1
      }
    ],
    \"shipping_address\": {
      \"recipient_name\": \"Test Cancel\",
      \"phone\": \"555-000-0000\",
      \"street_address_1\": \"999 Cancel Lane\",
      \"city\": \"Chicago\",
      \"state\": \"IL\",
      \"zip_code\": \"60601\",
      \"country\": \"US\"
    },
    \"payment_info\": {
      \"payment_method\": \"credit_card\",
      \"card_last4\": \"1234\",
      \"card_brand\": \"Mastercard\"
    }
  }")

echo "$CANCEL_ORDER_RESPONSE" | jq .

CANCEL_ORDER_ID=$(echo "$CANCEL_ORDER_RESPONSE" | jq -r '.id')
echo -e "${GREEN}New Order ID for cancel test: $CANCEL_ORDER_ID${NC}"
echo ""

# ============================================================================
# 10. CANCEL PENDING ORDER
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}10. CANCEL PENDING ORDER${NC}"
echo -e "${BLUE}============================================${NC}"

PENDING_CANCEL=$(curl -s -X POST "$BASE_URL/orders/cancel" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{
    \"order_id\": \"$CANCEL_ORDER_ID\",
    \"reason\": \"Found a better deal elsewhere\"
  }")

echo "$PENDING_CANCEL" | jq .

PENDING_CANCEL_STATUS=$(echo "$PENDING_CANCEL" | jq -r '.status')
echo -e "${GREEN}Pending order cancelled: $PENDING_CANCEL_STATUS${NC}"
echo ""

# ============================================================================
# 11. ERROR CASES
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}11. ERROR CASES${NC}"
echo -e "${BLUE}============================================${NC}"

echo -e "${YELLOW}11a. Missing Idempotency Key:${NC}"
curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{
    \"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}],
    \"shipping_address\": {
      \"recipient_name\": \"Test\",
      \"phone\": \"555-111-1111\",
      \"street_address_1\": \"Test St\",
      \"city\": \"Test\",
      \"state\": \"TX\",
      \"zip_code\": \"12345\",
      \"country\": \"US\"
    },
    \"payment_info\": {\"payment_method\": \"credit_card\"}
  }" | jq .
echo ""

echo -e "${YELLOW}11b. Invalid Product ID:${NC}"
curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Idempotency-Key: error-test-${TIMESTAMP}" \
  -d "{
    \"items\": [{\"product_id\": \"invalid_id\", \"quantity\": 1}],
    \"shipping_address\": {
      \"recipient_name\": \"Test\",
      \"phone\": \"555-111-1111\",
      \"street_address_1\": \"Test St\",
      \"city\": \"Test\",
      \"state\": \"TX\",
      \"zip_code\": \"12345\",
      \"country\": \"US\"
    },
    \"payment_info\": {\"payment_method\": \"credit_card\"}
  }" | jq .
echo ""

echo -e "${YELLOW}11c. Order Not Found:${NC}"
curl -s -X POST "$BASE_URL/orders/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d "{\"order_id\": \"507f1f77bcf86cd799439000\"}" | jq .
echo ""

# ============================================================================
# 12. LIST ORDERS (final state)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}12. FINAL ORDER LIST${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X GET "$BASE_URL/orders/list?limit=10" \
  -H "X-User-ID: $USER_ID" | jq .

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    TEST COMPLETE${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Test Data:"
echo "  User ID: $USER_ID"
echo "  User Email: $USER_EMAIL"
echo "  Supplier ID: $SUPPLIER_ID"
echo "  Product ID: $PRODUCT_ID"
echo "  Order ID: $ORDER_ID"
echo "  Order Number: $ORDER_NUMBER"
echo ""
