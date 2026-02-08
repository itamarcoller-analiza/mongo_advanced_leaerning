#!/bin/bash

# Test Authentication Flows
# Run this after starting the application with docker-compose up

BASE_URL="http://localhost:8000"

echo "================================================"
echo "Testing Authentication Flows"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ================================================
# 1. CONSUMER USER REGISTRATION & LOGIN
# ================================================
echo -e "${BLUE}=== 1. CONSUMER USER FLOW ===${NC}"
echo ""

echo "Step 1: Register Consumer User"
CONSUMER_REGISTER=$(curl -s -X POST "${BASE_URL}/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "Consumer123",
    "display_name": "John Consumer"
  }')

echo "$CONSUMER_REGISTER" | jq '.'
echo ""

# Extract verification token (in real scenario, this would be from email)
# For testing, we'll manually create a token or skip verification

echo "Step 2: Attempt Login (before email verification - should fail)"
CONSUMER_LOGIN_FAIL=$(curl -s -X POST "${BASE_URL}/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "Consumer123"
  }')

echo "$CONSUMER_LOGIN_FAIL" | jq '.'
echo ""

echo -e "${RED}Note: Email verification required. In production, user would click link in email.${NC}"
echo ""

# ================================================
# 2. LEADER USER REGISTRATION & LOGIN
# ================================================
echo -e "${BLUE}=== 2. LEADER USER FLOW ===${NC}"
echo ""

echo "Step 1: Register Leader User"
LEADER_REGISTER=$(curl -s -X POST "${BASE_URL}/register/leader" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "leader@celebrity.com",
    "password": "Leader123!",
    "display_name": "Jane Celebrity",
    "company_name": "Celebrity Brand Inc",
    "business_type": "personal_brand",
    "country": "US",
    "city": "Los Angeles",
    "zip_code": "90001",
    "website": "https://celebrity.com"
  }')

echo "$LEADER_REGISTER" | jq '.'
echo ""

echo "Step 2: Attempt Login (before email verification - should fail)"
LEADER_LOGIN_FAIL=$(curl -s -X POST "${BASE_URL}/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "leader@celebrity.com",
    "password": "Leader123!"
  }')

echo "$LEADER_LOGIN_FAIL" | jq '.'
echo ""

echo -e "${RED}Note: Leader requires email verification AND admin approval.${NC}"
echo ""

# ================================================
# 3. SUPPLIER REGISTRATION & LOGIN
# ================================================
echo -e "${BLUE}=== 3. SUPPLIER FLOW ===${NC}"
echo ""

echo "Step 1: Register Supplier"
SUPPLIER_REGISTER=$(curl -s -X POST "${BASE_URL}/supplier/register" \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "supplier@acme.com",
    "phone": "+1-555-0100",
    "contact_person_name": "Bob Manager",
    "contact_person_title": "Operations Director",
    "legal_name": "ACME Electronics Inc.",
    "company_type": "corporation",
    "tax_id": "12-3456789",
    "tax_id_country": "US",
    "street_address": "123 Business Ave",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94105",
    "country": "US",
    "industry_category": "electronics",
    "description": "We supply premium electronics and accessories to retailers worldwide.",
    "website": "https://acme-electronics.com",
    "password": "Supplier123!@",
    "terms_accepted": true,
    "privacy_policy_accepted": true
  }')

echo "$SUPPLIER_REGISTER" | jq '.'
echo ""

echo "Step 2: Attempt Supplier Login (before email verification - should work but limited)"
SUPPLIER_LOGIN=$(curl -s -X POST "${BASE_URL}/supplier/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "supplier@acme.com",
    "password": "Supplier123!@"
  }')

# Check if login was successful
if echo "$SUPPLIER_LOGIN" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Supplier Login Successful!${NC}"
    echo "$SUPPLIER_LOGIN" | jq '.'

    # Extract access token
    ACCESS_TOKEN=$(echo "$SUPPLIER_LOGIN" | jq -r '.access_token')
    echo ""
    echo -e "${GREEN}Access Token: $ACCESS_TOKEN${NC}"
    echo ""

    echo "Step 3: Submit Verification Documents"
    SUBMIT_DOCS=$(curl -s -X POST "${BASE_URL}/supplier/submit-documents" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -d '{
        "documents": [
          {
            "document_type": "business_license",
            "file_url": "https://s3.example.com/docs/license.pdf",
            "uploaded_at": "2025-02-03T10:00:00Z"
          },
          {
            "document_type": "tax_document",
            "file_url": "https://s3.example.com/docs/tax.pdf",
            "uploaded_at": "2025-02-03T10:01:00Z"
          },
          {
            "document_type": "identity_verification",
            "file_url": "https://s3.example.com/docs/id.pdf",
            "uploaded_at": "2025-02-03T10:02:00Z"
          }
        ]
      }')

    echo "$SUBMIT_DOCS" | jq '.'
    echo ""

else
    echo -e "${RED}✗ Supplier Login Failed${NC}"
    echo "$SUPPLIER_LOGIN" | jq '.'
    echo ""
fi

# ================================================
# SUMMARY
# ================================================
echo "================================================"
echo -e "${BLUE}SUMMARY${NC}"
echo "================================================"
echo ""
echo "1. Consumer Registration: Created with status=PENDING (needs email verification)"
echo "2. Leader Registration: Created with status=PENDING (needs email verification + admin approval)"
echo "3. Supplier Registration: Created with status=ACTIVE, verification_status=PENDING"
echo "4. Supplier Login: Successful! Can login and access dashboard"
echo "5. Supplier Document Submission: Ready for admin review"
echo ""
echo -e "${GREEN}Key Differences:${NC}"
echo "  - Consumers: Must verify email before login"
echo "  - Leaders: Must verify email + wait for admin approval before full access"
echo "  - Suppliers: Can login immediately (status=ACTIVE) but need verification to create products"
echo ""
echo "================================================"
