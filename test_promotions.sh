#!/bin/bash

# ============================================================================
# Promotion API Test Script (curl)
# ============================================================================

BASE_URL="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Saved user data
SAVED_USER_ID="6983152c215b5fb1fbb19299"
SAVED_USER_EMAIL="user22@example.com"

# Test data (will be populated during tests)
SUPPLIER_ID=""
SUPPLIER_TOKEN=""
PRODUCT_ID_1=""
PRODUCT_ID_2=""
PRODUCT_ID_3=""
PROMOTION_ID=""
PROMOTION_VERSION=1
COMMUNITY_ID="507f1f77bcf86cd799439011"
ADMIN_ID="507f1f77bcf86cd799439099"  # Valid ObjectId for testing

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    PROMOTION API TEST SCRIPT${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================================================
# SETUP: Register Supplier
# ============================================================================
echo -e "${YELLOW}=== SETUP: Register Supplier ===${NC}"

TIMESTAMP=$(date +%s)

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/supplier/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"primary_email\": \"promo_test_${TIMESTAMP}@supplier.com\",
    \"phone\": \"+1-555-0199\",
    \"contact_person_name\": \"Promo Test Manager\",
    \"contact_person_title\": \"Marketing Director\",
    \"legal_name\": \"Promo Test Supplier ${TIMESTAMP}\",
    \"company_type\": \"corporation\",
    \"tax_id\": \"99-${TIMESTAMP: -7}\",
    \"tax_id_country\": \"US\",
    \"street_address\": \"456 Promo Street\",
    \"city\": \"New York\",
    \"state\": \"NY\",
    \"zip_code\": \"10001\",
    \"country\": \"US\",
    \"industry_category\": \"electronics\",
    \"description\": \"Test supplier for promotion testing\",
    \"website\": \"https://promo-test-supplier.com\",
    \"password\": \"PromoTest#Pass123!\",
    \"terms_accepted\": true,
    \"privacy_policy_accepted\": true
  }")

echo "Register Response:"
echo "$REGISTER_RESPONSE" | jq .

SUPPLIER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.supplier.id')
SUPPLIER_EMAIL="promo_test_${TIMESTAMP}@supplier.com"
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
# SETUP: Login Supplier
# ============================================================================
echo -e "${YELLOW}=== SETUP: Login Supplier ===${NC}"

LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/supplier/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$SUPPLIER_EMAIL\",
    \"password\": \"PromoTest#Pass123!\"
  }")

echo "Login Response:"
echo "$LOGIN_RESPONSE" | jq .

SUPPLIER_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
echo -e "${GREEN}Token obtained${NC}"
echo ""

# ============================================================================
# SETUP: Create Products
# ============================================================================
echo -e "${YELLOW}=== SETUP: Create Products ===${NC}"

# Product 1
echo "Creating Product 1..."
PRODUCT_1_RESPONSE=$(curl -s -X POST "$BASE_URL/products" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"name\": \"Test Product Alpha ${TIMESTAMP}\",
    \"short_description\": \"Test product 1 for promotion testing\",
    \"category\": \"electronics\",
    \"condition\": \"new\",
    \"base_price_cents\": 9999,
    \"currency\": \"USD\",
    \"base_sku\": \"ALPHA-${TIMESTAMP}\",
    \"tags\": [\"test\", \"promotion\"],
    \"images\": [
      {
        \"url\": \"https://example.com/images/product1.jpg\",
        \"alt_text\": \"Product Alpha\",
        \"order\": 0,
        \"is_primary\": true
      }
    ],
    \"shipping\": {
      \"free_shipping\": true,
      \"ships_from_country\": \"US\",
      \"ships_to_countries\": [\"US\", \"CA\"],
      \"estimated_delivery_days\": 5
    }
  }")

echo "$PRODUCT_1_RESPONSE" | jq .
PRODUCT_ID_1=$(echo "$PRODUCT_1_RESPONSE" | jq -r '.id')
echo -e "${GREEN}Product 1 created: $PRODUCT_ID_1${NC}"
echo ""

# Product 2
echo "Creating Product 2..."
PRODUCT_2_RESPONSE=$(curl -s -X POST "$BASE_URL/products" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"name\": \"Test Product Beta ${TIMESTAMP}\",
    \"short_description\": \"Test product 2 for promotion testing\",
    \"category\": \"electronics\",
    \"condition\": \"new\",
    \"base_price_cents\": 14999,
    \"currency\": \"USD\",
    \"base_sku\": \"BETA-${TIMESTAMP}\",
    \"tags\": [\"test\", \"promotion\"],
    \"images\": [
      {
        \"url\": \"https://example.com/images/product2.jpg\",
        \"alt_text\": \"Product Beta\",
        \"order\": 0,
        \"is_primary\": true
      }
    ],
    \"shipping\": {
      \"free_shipping\": false,
      \"shipping_cost_cents\": 999,
      \"ships_from_country\": \"US\",
      \"ships_to_countries\": [\"US\"],
      \"estimated_delivery_days\": 3
    }
  }")

echo "$PRODUCT_2_RESPONSE" | jq .
PRODUCT_ID_2=$(echo "$PRODUCT_2_RESPONSE" | jq -r '.id')
echo -e "${GREEN}Product 2 created: $PRODUCT_ID_2${NC}"
echo ""

# Product 3
echo "Creating Product 3..."
PRODUCT_3_RESPONSE=$(curl -s -X POST "$BASE_URL/products" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"name\": \"Test Product Gamma ${TIMESTAMP}\",
    \"short_description\": \"Test product 3 for promotion testing\",
    \"category\": \"electronics\",
    \"condition\": \"new\",
    \"base_price_cents\": 19999,
    \"currency\": \"USD\",
    \"base_sku\": \"GAMMA-${TIMESTAMP}\",
    \"tags\": [\"test\", \"promotion\"],
    \"images\": [
      {
        \"url\": \"https://example.com/images/product3.jpg\",
        \"alt_text\": \"Product Gamma\",
        \"order\": 0,
        \"is_primary\": true
      }
    ],
    \"shipping\": {
      \"free_shipping\": true,
      \"ships_from_country\": \"US\",
      \"ships_to_countries\": [\"US\", \"CA\", \"MX\"],
      \"estimated_delivery_days\": 7
    }
  }")

echo "$PRODUCT_3_RESPONSE" | jq .
PRODUCT_ID_3=$(echo "$PRODUCT_3_RESPONSE" | jq -r '.id')
echo -e "${GREEN}Product 3 created: $PRODUCT_ID_3${NC}"
echo ""

# Check if products were created
if [ "$PRODUCT_ID_1" == "null" ] || [ "$PRODUCT_ID_2" == "null" ]; then
  echo -e "${RED}Failed to create products. Aborting tests.${NC}"
  exit 1
fi

# ============================================================================
# 1. CREATE PROMOTION
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}1. CREATE PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"

START_DATE=$(date -u -v+1d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT%H:%M:%SZ")
END_DATE=$(date -u -v+14d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+14 days" +"%Y-%m-%dT%H:%M:%SZ")

CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"type\": \"campaign\",
    \"title\": \"Summer Sale Campaign 2024\",
    \"description\": \"Amazing summer deals on electronics! Get up to 25% off on selected items.\",
    \"banner_image\": \"https://example.com/banners/summer-sale.jpg\",
    \"products\": [
      {\"product_id\": \"$PRODUCT_ID_1\", \"discount_percent\": 20},
      {\"product_id\": \"$PRODUCT_ID_2\", \"discount_percent\": 25}
    ],
    \"visibility\": {
      \"type\": \"both\",
      \"community_ids\": [\"$COMMUNITY_ID\"]
    },
    \"schedule\": {
      \"start_date\": \"$START_DATE\",
      \"end_date\": \"$END_DATE\",
      \"timezone\": \"America/New_York\"
    },
    \"terms\": {
      \"terms_text\": \"Limited time offer. While supplies last.\",
      \"restrictions\": [\"Cannot be combined with other offers\"],
      \"max_uses_per_user\": 1
    }
  }")

echo "Create Response:"
echo "$CREATE_RESPONSE" | jq .

PROMOTION_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
PROMOTION_VERSION=$(echo "$CREATE_RESPONSE" | jq -r '.version')

if [ "$PROMOTION_ID" == "null" ]; then
  echo -e "${RED}Failed to create promotion. Check error above.${NC}"
  exit 1
fi

echo -e "${GREEN}Promotion ID: $PROMOTION_ID${NC}"
echo -e "${GREEN}Version: $PROMOTION_VERSION${NC}"
echo ""

# ============================================================================
# 2. GET PROMOTION
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}2. GET PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/promotions/get" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{\"promotion_id\": \"$PROMOTION_ID\"}" | jq .

echo ""

# ============================================================================
# 3. LIST PROMOTIONS
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}3. LIST PROMOTIONS${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X GET "$BASE_URL/promotions/list?page=1&limit=10" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" | jq .

echo ""

# ============================================================================
# 4. UPDATE PROMOTION
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}4. UPDATE PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"

UPDATE_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/update" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION,
    \"title\": \"Super Summer Sale Campaign 2024 - Extended!\",
    \"description\": \"Extended summer deals! Now with even bigger discounts!\"
  }")

echo "$UPDATE_RESPONSE" | jq .

PROMOTION_VERSION=$(echo "$UPDATE_RESPONSE" | jq -r '.version')
echo -e "${GREEN}New Version: $PROMOTION_VERSION${NC}"
echo ""

# ============================================================================
# 5. SUBMIT FOR APPROVAL
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}5. SUBMIT FOR APPROVAL${NC}"
echo -e "${BLUE}============================================${NC}"

SUBMIT_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/submit" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION
  }")

echo "$SUBMIT_RESPONSE" | jq .

PROMOTION_VERSION=$(echo "$SUBMIT_RESPONSE" | jq -r '.version')
echo -e "${GREEN}Status: $(echo "$SUBMIT_RESPONSE" | jq -r '.status')${NC}"
echo ""

# ============================================================================
# 6. ADMIN - LIST PENDING APPROVALS
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}6. ADMIN - LIST PENDING APPROVALS${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X GET "$BASE_URL/admin/promos/pending?page=1&limit=10" \
  -H "X-Admin-ID: $ADMIN_ID" \
  -H "X-Admin-Type: admin" | jq .

echo ""

# ============================================================================
# 7. ADMIN - GET PROMOTION
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}7. ADMIN - GET PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/admin/promos/get" \
  -H "Content-Type: application/json" \
  -H "X-Admin-ID: $ADMIN_ID" \
  -H "X-Admin-Type: admin" \
  -d "{\"promotion_id\": \"$PROMOTION_ID\"}" | jq .

echo ""

# ============================================================================
# 8. ADMIN - APPROVE PROMOTION (GLOBAL)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}8. ADMIN - APPROVE PROMOTION (GLOBAL)${NC}"
echo -e "${BLUE}============================================${NC}"

APPROVE_RESPONSE=$(curl -s -X POST "$BASE_URL/admin/promos/approve" \
  -H "Content-Type: application/json" \
  -H "X-Admin-ID: $ADMIN_ID" \
  -H "X-Admin-Type: admin" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION,
    \"approval_scope\": \"global\",
    \"notes\": \"Approved for global visibility\"
  }")

echo "$APPROVE_RESPONSE" | jq .

PROMOTION_VERSION=$(echo "$APPROVE_RESPONSE" | jq -r '.version')
echo -e "${GREEN}Status: $(echo "$APPROVE_RESPONSE" | jq -r '.status')${NC}"
echo ""

# ============================================================================
# 9. ADMIN - APPROVE PROMOTION (COMMUNITY)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}9. ADMIN - APPROVE PROMOTION (COMMUNITY)${NC}"
echo -e "${BLUE}============================================${NC}"

APPROVE_COMM_RESPONSE=$(curl -s -X POST "$BASE_URL/admin/promos/approve" \
  -H "Content-Type: application/json" \
  -H "X-Admin-ID: $ADMIN_ID" \
  -H "X-Admin-Type: admin" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION,
    \"approval_scope\": \"community\",
    \"community_id\": \"$COMMUNITY_ID\",
    \"notes\": \"Approved for community\"
  }")

echo "$APPROVE_COMM_RESPONSE" | jq .

PROMOTION_VERSION=$(echo "$APPROVE_COMM_RESPONSE" | jq -r '.version')
echo ""

# ============================================================================
# 10. PAUSE PROMOTION (Note: Only works for ACTIVE promotions)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}10. PAUSE PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}Note: Promotion is 'scheduled' (start_date is in future).${NC}"
echo -e "${YELLOW}Pause only works for ACTIVE promotions. This test shows expected error.${NC}"

PAUSE_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/pause" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION,
    \"reason\": \"Inventory check required\"
  }")

echo "$PAUSE_RESPONSE" | jq .

# Only update version if pause succeeded
NEW_VERSION=$(echo "$PAUSE_RESPONSE" | jq -r '.version')
if [ "$NEW_VERSION" != "null" ]; then
  PROMOTION_VERSION=$NEW_VERSION
  echo -e "${GREEN}Status: $(echo "$PAUSE_RESPONSE" | jq -r '.status')${NC}"
else
  echo -e "${YELLOW}Expected: Pause failed (promotion is scheduled, not active)${NC}"
fi
echo ""

# ============================================================================
# 11. RESUME PROMOTION (Note: Only works for PAUSED promotions)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}11. RESUME PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}Note: Resume only works for PAUSED promotions.${NC}"

RESUME_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/resume" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION
  }")

echo "$RESUME_RESPONSE" | jq .

# Only update version if resume succeeded
NEW_VERSION=$(echo "$RESUME_RESPONSE" | jq -r '.version')
if [ "$NEW_VERSION" != "null" ]; then
  PROMOTION_VERSION=$NEW_VERSION
  echo -e "${GREEN}Status: $(echo "$RESUME_RESPONSE" | jq -r '.status')${NC}"
else
  echo -e "${YELLOW}Expected: Resume failed (promotion is scheduled, not paused)${NC}"
fi
echo ""

# ============================================================================
# 12. GLOBAL FEED
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}12. GLOBAL FEED${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/promotions/global?limit=20" \
  -H "Content-Type: application/json" \
  -d "{\"cursor\": null}" | jq .

echo ""

# ============================================================================
# 13. COMMUNITY FEED
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}13. COMMUNITY FEED${NC}"
echo -e "${BLUE}============================================${NC}"

curl -s -X POST "$BASE_URL/promotions/community?limit=20" \
  -H "Content-Type: application/json" \
  -d "{\"community_id\": \"$COMMUNITY_ID\", \"cursor\": null}" | jq .

echo ""

# ============================================================================
# 14. END PROMOTION (Note: Only works for ACTIVE promotions)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}14. END PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}Note: End only works for ACTIVE promotions (not scheduled).${NC}"

END_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/end" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION
  }")

echo "$END_RESPONSE" | jq .

# Only update version if end succeeded
NEW_VERSION=$(echo "$END_RESPONSE" | jq -r '.version')
if [ "$NEW_VERSION" != "null" ]; then
  PROMOTION_VERSION=$NEW_VERSION
  echo -e "${GREEN}Status: $(echo "$END_RESPONSE" | jq -r '.status')${NC}"
else
  echo -e "${YELLOW}Expected: End failed (promotion is scheduled, not active)${NC}"
fi
echo ""

# ============================================================================
# 15. DELETE PROMOTION (works for non-sent promotions)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}15. DELETE PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}Note: Delete works for promotions that haven't been 'sent' (never activated).${NC}"
echo -e "${YELLOW}Since this promo is 'scheduled' (start_date in future), it can be deleted.${NC}"

DELETE_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/delete" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION
  }")

echo "$DELETE_RESPONSE" | jq .

# Only update version if delete succeeded
NEW_VERSION=$(echo "$DELETE_RESPONSE" | jq -r '.version')
if [ "$NEW_VERSION" != "null" ]; then
  PROMOTION_VERSION=$NEW_VERSION
  echo -e "${GREEN}Status: $(echo "$DELETE_RESPONSE" | jq -r '.status')${NC}"
else
  echo -e "${YELLOW}Delete failed or promotion already deleted${NC}"
fi
echo ""

# ============================================================================
# 16. CANCEL PROMOTION (alternative to delete for sent promos)
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}16. CANCEL PROMOTION${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}Note: Cancel is for 'sent' promotions that cannot be deleted.${NC}"
echo -e "${YELLOW}If step 15 (delete) succeeded, this will fail (promotion already deleted).${NC}"

CANCEL_RESPONSE=$(curl -s -X POST "$BASE_URL/promotions/cancel" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "X-Supplier-ID: $SUPPLIER_ID" \
  -d "{
    \"promotion_id\": \"$PROMOTION_ID\",
    \"version\": $PROMOTION_VERSION,
    \"reason\": \"Campaign strategy changed\"
  }")

echo "$CANCEL_RESPONSE" | jq .

# Check result
NEW_VERSION=$(echo "$CANCEL_RESPONSE" | jq -r '.version')
if [ "$NEW_VERSION" != "null" ]; then
  echo -e "${GREEN}Status: $(echo "$CANCEL_RESPONSE" | jq -r '.status')${NC}"
else
  echo -e "${YELLOW}Expected: Cancel failed (promotion was deleted in step 15)${NC}"
fi
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    TEST COMPLETE${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Test Data:"
echo "  Supplier ID: $SUPPLIER_ID"
echo "  Product IDs: $PRODUCT_ID_1, $PRODUCT_ID_2, $PRODUCT_ID_3"
echo "  Promotion ID: $PROMOTION_ID"
echo "  Saved User: $SAVED_USER_EMAIL (ID: $SAVED_USER_ID)"
echo ""
