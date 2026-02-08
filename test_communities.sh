#!/bin/bash

# Test Community Endpoints
# Run this after starting the application with docker-compose up

BASE_URL="http://localhost:8000"

echo "================================================"
echo "Testing Community Endpoints"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ================================================
# SETUP: Create test users
# ================================================
echo -e "${BLUE}=== SETUP: Creating Test Users ===${NC}"
echo ""

# Use timestamp for unique emails
TIMESTAMP=$(date +%s)

# Create leader user
echo "Creating leader user..."
LEADER_RESPONSE=$(curl -s -X POST "${BASE_URL}/register/leader" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"leader_${TIMESTAMP}@test.com\",
    \"password\": \"LeaderPass123\",
    \"display_name\": \"Test Leader\",
    \"company_name\": \"Test Company\",
    \"business_type\": \"personal_brand\",
    \"country\": \"US\",
    \"city\": \"San Francisco\",
    \"zip_code\": \"94102\",
    \"website\": \"https://test.com\"
  }")

LEADER_ID=$(echo "$LEADER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('id', ''))" 2>/dev/null)
if [ -z "$LEADER_ID" ]; then
  echo -e "${RED}Failed to create leader user${NC}"
  echo "$LEADER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LEADER_RESPONSE"
else
  echo -e "${GREEN}Leader created: $LEADER_ID${NC}"
fi
echo ""

# Create regular user
echo "Creating regular user..."
MEMBER_RESPONSE=$(curl -s -X POST "${BASE_URL}/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"member_${TIMESTAMP}@test.com\",
    \"password\": \"UserPass123\",
    \"display_name\": \"Test User\"
  }")

MEMBER_ID=$(echo "$MEMBER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('id', ''))" 2>/dev/null)
if [ -z "$MEMBER_ID" ]; then
  echo -e "${RED}Failed to create member user${NC}"
  echo "$MEMBER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MEMBER_RESPONSE"
else
  echo -e "${GREEN}Member created: $MEMBER_ID${NC}"
fi
echo ""

# ================================================
# 1. CREATE COMMUNITY
# ================================================
echo -e "${BLUE}=== 1. CREATE COMMUNITY ===${NC}"
echo ""

SLUG="test-comm-$(date +%s)"

echo "Creating community with slug: $SLUG"
CREATE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -H "X-User-Role: leader" \
  -d "{
    \"name\": \"Test Community\",
    \"slug\": \"$SLUG\",
    \"description\": \"A test community for testing all endpoints\",
    \"tagline\": \"Testing is fun!\",
    \"category\": \"tech\",
    \"tags\": [\"testing\", \"development\"],
    \"purpose\": {
      \"mission_statement\": \"To thoroughly test community features\",
      \"goals\": [\"Test all endpoints\", \"Verify functionality\"],
      \"target_audience\": \"Developers and testers\"
    },
    \"business_address\": {
      \"country\": \"US\",
      \"city\": \"San Francisco\",
      \"zip_code\": \"94102\"
    },
    \"branding\": {
      \"cover_image\": \"https://example.com/cover.jpg\",
      \"logo\": \"https://example.com/logo.png\",
      \"primary_color\": \"#FF5733\",
      \"secondary_color\": \"#33FF57\"
    },
    \"rules\": [
      {\"rule_title\": \"Be respectful\", \"rule_description\": \"Treat everyone with respect\"},
      {\"rule_title\": \"No spam\", \"rule_description\": \"Do not post spam content\"}
    ]
  }")

COMMUNITY_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
if [ -z "$COMMUNITY_ID" ]; then
  echo -e "${RED}Failed to create community${NC}"
  echo "$CREATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CREATE_RESPONSE"
  exit 1
else
  echo -e "${GREEN}Community created: $COMMUNITY_ID${NC}"
  echo "$CREATE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -30
fi
echo ""

# ================================================
# 2. GET COMMUNITY BY ID
# ================================================
echo -e "${BLUE}=== 2. GET COMMUNITY BY ID ===${NC}"
echo ""

GET_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$GET_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
echo ""

# ================================================
# 3. GET COMMUNITY BY SLUG
# ================================================
echo -e "${BLUE}=== 3. GET COMMUNITY BY SLUG ===${NC}"
echo ""

SLUG_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/get-by-slug" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"slug\": \"$SLUG\"}")

echo "$SLUG_RESPONSE" | python3 -m json.tool 2>/dev/null | head -15
echo ""

# ================================================
# 4. DISCOVER COMMUNITIES
# ================================================
echo -e "${BLUE}=== 4. DISCOVER COMMUNITIES ===${NC}"
echo ""

DISCOVER_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/discover" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d '{"limit": 10, "category": "tech"}')

echo "$DISCOVER_RESPONSE" | python3 -m json.tool 2>/dev/null | head -25
echo ""

# ================================================
# 5. JOIN COMMUNITY (as member)
# ================================================
echo -e "${BLUE}=== 5. JOIN COMMUNITY ===${NC}"
echo ""

JOIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/join" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $MEMBER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$JOIN_RESPONSE" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# 6. CHECK MEMBERSHIP
# ================================================
echo -e "${BLUE}=== 6. CHECK MEMBERSHIP ===${NC}"
echo ""

echo "Checking membership for member user..."
MEMBERSHIP_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/check-membership" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $MEMBER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$MEMBERSHIP_RESPONSE" | python3 -m json.tool 2>/dev/null
echo ""

echo "Checking membership for owner..."
OWNER_MEMBERSHIP=$(curl -s -X POST "${BASE_URL}/communities/check-membership" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$OWNER_MEMBERSHIP" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# 7. LIST MEMBERS
# ================================================
echo -e "${BLUE}=== 7. LIST MEMBERS ===${NC}"
echo ""

MEMBERS_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/members" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\", \"limit\": 10}")

echo "$MEMBERS_RESPONSE" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# 8. UPDATE COMMUNITY
# ================================================
echo -e "${BLUE}=== 8. UPDATE COMMUNITY ===${NC}"
echo ""

# Get current version
CURRENT_VERSION=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 1))" 2>/dev/null)

echo "Current version: $CURRENT_VERSION"

UPDATE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/update" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{
    \"community_id\": \"$COMMUNITY_ID\",
    \"expected_version\": $CURRENT_VERSION,
    \"name\": \"Updated Test Community\",
    \"tagline\": \"Now with updates!\"
  }")

echo "$UPDATE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
echo ""

# ================================================
# 9. LEAVE COMMUNITY (as member)
# ================================================
echo -e "${BLUE}=== 9. LEAVE COMMUNITY ===${NC}"
echo ""

LEAVE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/leave" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $MEMBER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$LEAVE_RESPONSE" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# 10. OWNER CANNOT LEAVE
# ================================================
echo -e "${BLUE}=== 10. OWNER CANNOT LEAVE (should fail) ===${NC}"
echo ""

OWNER_LEAVE=$(curl -s -X POST "${BASE_URL}/communities/leave" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$OWNER_LEAVE" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# 11. ARCHIVE COMMUNITY
# ================================================
echo -e "${BLUE}=== 11. ARCHIVE COMMUNITY ===${NC}"
echo ""

# Get current version
CURRENT_VERSION=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 1))" 2>/dev/null)

echo "Current version: $CURRENT_VERSION"

ARCHIVE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/archive" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{
    \"community_id\": \"$COMMUNITY_ID\",
    \"expected_version\": $CURRENT_VERSION
  }")

echo "$ARCHIVE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -15
echo ""

# ================================================
# 12. UNARCHIVE COMMUNITY
# ================================================
echo -e "${BLUE}=== 12. UNARCHIVE COMMUNITY ===${NC}"
echo ""

# Get current version
CURRENT_VERSION=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 1))" 2>/dev/null)

echo "Current version: $CURRENT_VERSION"

UNARCHIVE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/unarchive" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{
    \"community_id\": \"$COMMUNITY_ID\",
    \"expected_version\": $CURRENT_VERSION
  }")

echo "$UNARCHIVE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -15
echo ""

# ================================================
# 13. DELETE COMMUNITY
# ================================================
echo -e "${BLUE}=== 13. DELETE COMMUNITY ===${NC}"
echo ""

# Get current version
CURRENT_VERSION=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 1))" 2>/dev/null)

echo "Current version: $CURRENT_VERSION"

DELETE_RESPONSE=$(curl -s -X POST "${BASE_URL}/communities/delete" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{
    \"community_id\": \"$COMMUNITY_ID\",
    \"expected_version\": $CURRENT_VERSION
  }")

echo "$DELETE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -15
echo ""

# ================================================
# 14. TRY TO ACCESS DELETED COMMUNITY (should fail)
# ================================================
echo -e "${BLUE}=== 14. ACCESS DELETED COMMUNITY (should fail) ===${NC}"
echo ""

DELETED_ACCESS=$(curl -s -X POST "${BASE_URL}/communities/get" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $LEADER_ID" \
  -d "{\"community_id\": \"$COMMUNITY_ID\"}")

echo "$DELETED_ACCESS" | python3 -m json.tool 2>/dev/null
echo ""

# ================================================
# SUMMARY
# ================================================
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}Community Endpoint Tests Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Test IDs used:"
echo "  Leader ID: $LEADER_ID"
echo "  Member ID: $MEMBER_ID"
echo "  Community ID: $COMMUNITY_ID"
echo "  Community Slug: $SLUG"
echo ""
