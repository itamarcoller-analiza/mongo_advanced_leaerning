"""
Test Authentication Flows (Async)
Simulates user, leader, and supplier registration and login
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_step(text):
    print(f"{Colors.YELLOW}► {text}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_json(data):
    print(json.dumps(data, indent=2))
    print()

# ================================================
# 1. CONSUMER USER FLOW
# ================================================
async def test_consumer_flow():
    print_header("1. CONSUMER USER FLOW")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Register Consumer
        print_step("Step 1: Register Consumer User")
        consumer_data = {
            "email": "john.doe@example.com",
            "password": "SecurePass123!",  # Fixed: doesn't contain "john"
            "display_name": "John Consumer"
        }

        try:
            response = await client.post(f"{BASE_URL}/register", json=consumer_data)
            if response.status_code == 201:
                print_success("Consumer registered successfully!")
                print_json(response.json())
            else:
                print_error(f"Registration failed: {response.status_code}")
                print_json(response.json())
        except Exception as e:
            print_error(f"Error: {str(e)}")
            return

        # Step 2: Attempt Login (should fail - email not verified)
        print_step("Step 2: Attempt Login (before email verification)")
        login_data = {
            "email": "john.doe@example.com",
            "password": "SecurePass123!"
        }

        try:
            response = await client.post(f"{BASE_URL}/login", json=login_data)
            if response.status_code == 200:
                print_success("Login successful!")
                print_json(response.json())
            else:
                print_error(f"Login failed (expected): {response.json().get('detail')}")
                print(f"Status Code: {response.status_code}\n")
        except Exception as e:
            print_error(f"Error: {str(e)}")

        print(f"{Colors.RED}Note: In production, user would verify email via link sent to inbox.{Colors.END}\n")

# ================================================
# 2. LEADER USER FLOW
# ================================================
async def test_leader_flow():
    print_header("2. LEADER USER FLOW")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Register Leader
        print_step("Step 1: Register Leader User")
        leader_data = {
            "email": "jane.celebrity@influencer.com",
            "password": "Leader$Pass456!",  # Fixed: doesn't contain "jane" or "celebrity"
            "display_name": "Jane Celebrity",
            "company_name": "Celebrity Brand Inc",
            "business_type": "personal_brand",
            "country": "US",
            "city": "Los Angeles",
            "zip_code": "90001",
            "website": "https://janecelebrity.com"
        }

        try:
            response = await client.post(f"{BASE_URL}/register/leader", json=leader_data)
            if response.status_code == 201:
                print_success("Leader registered successfully!")
                print_json(response.json())
            else:
                print_error(f"Registration failed: {response.status_code}")
                print_json(response.json())
        except Exception as e:
            print_error(f"Error: {str(e)}")
            return

        # Step 2: Attempt Login
        print_step("Step 2: Attempt Login (before email verification)")
        login_data = {
            "email": "jane.celebrity@influencer.com",
            "password": "Leader$Pass456!"
        }

        try:
            response = await client.post(f"{BASE_URL}/login", json=login_data)
            if response.status_code == 200:
                print_success("Login successful!")
                print_json(response.json())
            else:
                print_error(f"Login failed (expected): {response.json().get('detail')}")
                print(f"Status Code: {response.status_code}\n")
        except Exception as e:
            print_error(f"Error: {str(e)}")

        print(f"{Colors.RED}Note: Leader requires email verification AND admin approval before full access.{Colors.END}\n")

# ================================================
# 3. SUPPLIER FLOW
# ================================================
async def test_supplier_flow():
    print_header("3. SUPPLIER FLOW")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Register Supplier
        print_step("Step 1: Register Supplier")
        supplier_data = {
            "primary_email": "operations@acme-electronics.com",
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
            "password": "Supplier#Pass789!",  # Fixed: doesn't contain "operations"
            "terms_accepted": True,
            "privacy_policy_accepted": True
        }

        try:
            response = await client.post(f"{BASE_URL}/supplier/register", json=supplier_data)
            if response.status_code == 201:
                print_success("Supplier registered successfully!")
                print_json(response.json())
            else:
                print_error(f"Registration failed: {response.status_code}")
                print_json(response.json())
                return
        except Exception as e:
            print_error(f"Error: {str(e)}")
            return

        # Step 2: Supplier Login
        print_step("Step 2: Supplier Login")
        login_data = {
            "email": "operations@acme-electronics.com",
            "password": "Supplier#Pass789!"
        }

        try:
            response = await client.post(f"{BASE_URL}/supplier/login", json=login_data)
            if response.status_code == 200:
                print_success("Supplier login successful!")
                result = response.json()
                print_json(result)

                # Extract access token
                access_token = result.get("access_token")

                # Step 3: Submit Verification Documents
                print_step("Step 3: Submit Verification Documents")
                documents_data = {
                    "documents": [
                        {
                            "document_type": "business_license",
                            "file_url": "https://s3.example.com/docs/license.pdf",
                            "uploaded_at": datetime.utcnow().isoformat() + "Z"
                        },
                        {
                            "document_type": "tax_document",
                            "file_url": "https://s3.example.com/docs/tax.pdf",
                            "uploaded_at": datetime.utcnow().isoformat() + "Z"
                        },
                        {
                            "document_type": "identity_verification",
                            "file_url": "https://s3.example.com/docs/id.pdf",
                            "uploaded_at": datetime.utcnow().isoformat() + "Z"
                        }
                    ]
                }

                headers = {"Authorization": f"Bearer {access_token}"}
                doc_response = await client.post(
                    f"{BASE_URL}/supplier/submit-documents",
                    json=documents_data,
                    headers=headers
                )

                if doc_response.status_code == 200:
                    print_success("Documents submitted successfully!")
                    print_json(doc_response.json())
                else:
                    print_error(f"Document submission failed: {doc_response.status_code}")
                    print_json(doc_response.json())

            else:
                print_error(f"Login failed: {response.json().get('detail')}")
                print(f"Status Code: {response.status_code}\n")
        except Exception as e:
            print_error(f"Error: {str(e)}")

# ================================================
# SUMMARY
# ================================================
def print_summary():
    print_header("SUMMARY")

    print(f"{Colors.BOLD}Key Differences Between User Types:{Colors.END}\n")

    print(f"{Colors.GREEN}Consumer:{Colors.END}")
    print("  • Registration creates account with status=PENDING")
    print("  • Must verify email before login")
    print("  • After verification, status changes to ACTIVE")
    print("  • Can immediately use the platform after verification\n")

    print(f"{Colors.GREEN}Leader:{Colors.END}")
    print("  • Registration creates account with status=PENDING")
    print("  • Must verify email AND wait for admin approval")
    print("  • Cannot manage communities or create promotions until approved")
    print("  • Admin sets role=LEADER and grants permissions after review\n")

    print(f"{Colors.GREEN}Supplier:{Colors.END}")
    print("  • Registration creates account with status=ACTIVE")
    print("  • Can login immediately (no email verification gate)")
    print("  • Has verification_status=PENDING initially")
    print("  • Can access dashboard and submit documents")
    print("  • Cannot create products/promotions until verification_status=VERIFIED")
    print("  • Admin reviews documents and approves\n")

    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

# ================================================
# MAIN
# ================================================
async def main():
    print(f"\n{Colors.BOLD}Testing Authentication Flows (Async){Colors.END}")
    print(f"{Colors.BOLD}API Base URL: {BASE_URL}{Colors.END}\n")

    # Test all flows
    await test_consumer_flow()
    await test_leader_flow()
    await test_supplier_flow()

    # Print summary
    print_summary()

    print(f"{Colors.GREEN}All tests completed!{Colors.END}\n")

if __name__ == "__main__":
    asyncio.run(main())
