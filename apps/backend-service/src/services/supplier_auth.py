"""
Supplier Authentication Service - Business logic for supplier authentication
"""

import bcrypt
import jwt
import re
from datetime import timedelta
from typing import Optional, Dict, Any
from bson import ObjectId

from shared.models.supplier import *
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.serialization import oid_to_str


# JWT Configuration
JWT_SECRET = "your-secret-key-here"  # TODO: Move to environment variable
JWT_ALGORITHM = "HS256"


class SupplierAuthService:
    """Service class for supplier authentication operations"""

    def __init__(self):
        """Initialize supplier authentication service"""
        self.password_min_length = 10  # Stricter than consumer (8)
        self.password_max_length = 128
        self.max_failed_attempts = 5
        self.lock_duration_minutes = 30
        self._kafka = get_kafka_producer()

        # Password regex: at least 1 uppercase, 1 lowercase, 1 digit, 1 special char
        self.password_pattern = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).+$'
        )

    # Token utilities
    def generate_verification_token(self, supplier_id: str, email: str) -> str:
        """Generate email verification JWT token (6 hour expiry)"""
        payload = {
            "supplier_id": supplier_id,
            "email": email,
            "type": "supplier_email_verification",
            "exp": utc_now() + timedelta(hours=6)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def generate_reset_token(self, supplier_id: str, email: str) -> str:
        """Generate password reset JWT token (1 hour expiry)"""
        payload = {
            "supplier_id": supplier_id,
            "email": email,
            "type": "supplier_password_reset",
            "exp": utc_now() + timedelta(hours=1)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str, token_type: str) -> Dict[str, Any]:
        """
        Verify JWT token and return payload
        Raises ValueError if invalid or expired
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            if payload.get("type") != token_type:
                raise ValueError("Invalid token type")

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    # Password utilities
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def validate_password(self, password: str, email: str) -> None:
        """
        Validate password meets requirements using regex
        Raises ValueError if invalid
        """
        # Check length
        if len(password) < self.password_min_length:
            raise ValueError(f"Password must be at least {self.password_min_length} characters")

        if len(password) > self.password_max_length:
            raise ValueError(f"Password must be at most {self.password_max_length} characters")

        # Check pattern (uppercase, lowercase, digit, special char)
        if not self.password_pattern.match(password):
            raise ValueError("Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character (!@#$%^&*)")

        # Check if password contains email username
        email_username = email.split('@')[0].lower()
        if email_username in password.lower():
            raise ValueError("Password cannot contain your email username")

    # Email utilities
    async def is_email_available(self, email: str) -> bool:
        """Check if email is available (not used in suppliers or users)"""
        try:
            email = email.lower().strip()

            # Check within suppliers (primary email)
            supplier = await Supplier.find_one({"contact_info.primary_email": email})
            if supplier:
                return False

            # Check within suppliers (additional emails)
            supplier = await Supplier.find_one({"contact_info.additional_emails": email})
            if supplier:
                return False

            # TODO: Cross-check with Users collection
            # from shared.models.user import User
            # user = await User.find_one({"contact_info.primary_email": email})
            # if user:
            #     return False

            return True
        except Exception as e:
            raise Exception(f"Failed to check email availability: {str(e)}")

    # Registration
    async def register_supplier(
        self,
        primary_email: str,
        phone: str,
        contact_person_name: str,
        contact_person_title: Optional[str],
        legal_name: str,
        company_type: str,
        tax_id: str,
        tax_id_country: str,
        street_address: str,
        city: str,
        state: Optional[str],
        zip_code: str,
        country: str,
        industry_category: str,
        description: str,
        website: Optional[str],
        password: str,
        terms_accepted: bool,
        privacy_policy_accepted: bool
    ) -> Dict[str, Any]:
        """
        Register a new supplier
        Returns: dict with supplier data and verification token
        """
        try:
            primary_email = primary_email.lower().strip()
            contact_person_name = contact_person_name.strip()
            legal_name = legal_name.strip()

            # Validate terms acceptance
            if not terms_accepted:
                raise ValueError("You must accept the Terms of Service to register")

            if not privacy_policy_accepted:
                raise ValueError("You must accept the Privacy Policy to register")

            # Check email availability
            if not await self.is_email_available(primary_email):
                raise ValueError("Email already in use")

            # Validate password
            self.validate_password(password, primary_email)

            # Validate company type
            valid_company_types = ["corporation", "llc", "partnership", "sole_proprietorship"]
            if company_type not in valid_company_types:
                raise ValueError(f"Invalid company type. Must be one of: {', '.join(valid_company_types)}")

            # Validate country codes
            if len(tax_id_country) != 2 or len(country) != 2:
                raise ValueError("Country codes must be 2-letter ISO codes")

            # Create supplier document
            supplier = Supplier(
                password_hash=self.hash_password(password),
                contact_info=SupplierContactInfo(
                    primary_email=primary_email,
                    primary_phone=phone,
                    contact_person_name=contact_person_name,
                    contact_person_title=contact_person_title,
                    contact_person_email=primary_email
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

            await supplier.insert()

            # Emit supplier.registered event
            supplier_id = oid_to_str(supplier.id)
            self._kafka.emit(
                topic=Topic.SUPPLIER,
                action="registered",
                entity_id=supplier_id,
                data=supplier.model_dump(mode="json"),
            )

            # Generate verification token
            verification_token = self.generate_verification_token(supplier_id, primary_email)

            return {
                "supplier": {
                    "id": supplier_id,
                    "email": supplier.contact_info.primary_email,
                    "company_name": supplier.company_info.legal_name,
                    "verification_status": supplier.verification.verification_status.value,
                    "status": supplier.status.value
                },
                "verification_token": verification_token
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to register supplier: {str(e)}")

    # Login
    async def login(self, email: str, password: str, ip_address: str) -> Dict[str, Any]:
        """
        Authenticate supplier and return tokens + supplier data
        Returns: dict with tokens and supplier data
        """
        try:
            email = email.lower().strip()

            # Find supplier by primary email only
            supplier = await Supplier.find_one({"contact_info.primary_email": email})
            if not supplier:
                raise ValueError("Invalid email or password")

            # Check if soft-deleted
            if supplier.deleted_at is not None:
                raise ValueError("Account no longer exists")

            # Check if status is deleted
            if supplier.status == SupplierStatus.DELETED:
                raise ValueError("Account has been deleted")

            # Check if suspended
            if supplier.status == SupplierStatus.SUSPENDED:
                raise ValueError("Account suspended. Contact support.")

            # Check if account locked
            if supplier.security.locked_until:
                if utc_now() < supplier.security.locked_until:
                    remaining = int((supplier.security.locked_until - utc_now()).total_seconds() / 60)
                    raise ValueError(f"Account locked. Try again in {remaining} minutes")
                else:
                    # Lock expired, reset
                    supplier.security.locked_until = None
                    supplier.security.failed_login_attempts = 0
                    await supplier.save()

            # Verify password
            if not self.verify_password(password, supplier.password_hash):
                # Increment failed attempts
                supplier.security.failed_login_attempts += 1

                # Lock account after max attempts
                if supplier.security.failed_login_attempts >= self.max_failed_attempts:
                    supplier.security.locked_until = utc_now() + timedelta(minutes=self.lock_duration_minutes)
                    await supplier.save()
                    raise ValueError(f"Too many failed attempts. Account locked for {self.lock_duration_minutes} minutes")

                await supplier.save()
                raise ValueError("Invalid email or password")

            # Successful login - record it
            await supplier.record_successful_login(ip_address)

            # Emit supplier.login event
            supplier_id = oid_to_str(supplier.id)
            self._kafka.emit(
                topic=Topic.SUPPLIER,
                action="login",
                entity_id=supplier_id,
                data={
                    "email": supplier.contact_info.primary_email,
                    "company_name": supplier.company_info.legal_name,
                    "ip_address": ip_address,
                },
            )

            # Generate tokens (access + refresh)
            access_token = self.generate_access_token(supplier)
            refresh_token = self.generate_refresh_token(supplier)

            # Return tokens and supplier data
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
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to login: {str(e)}")

    def generate_access_token(self, supplier: Supplier) -> str:
        """Generate JWT access token (30 minutes expiry)"""
        payload = {
            "sub": str(supplier.id),
            "email": supplier.contact_info.primary_email,
            "company_name": supplier.company_info.legal_name,
            "type": "supplier_access",
            "verification_status": supplier.verification.verification_status.value,
            "status": supplier.status.value,
            "iat": int(utc_now().timestamp()),
            "exp": int((utc_now() + timedelta(minutes=30)).timestamp())
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def generate_refresh_token(self, supplier: Supplier) -> str:
        """Generate JWT refresh token (7 days expiry)"""
        payload = {
            "sub": str(supplier.id),
            "type": "supplier_refresh",
            "iat": int(utc_now().timestamp()),
            "exp": int((utc_now() + timedelta(days=7)).timestamp())
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Email verification
    async def verify_email(self, token: str) -> Dict[str, Any]:
        """
        Verify supplier email
        Returns: supplier data dictionary
        """
        try:
            # Verify token
            payload = self.verify_token(token, "supplier_email_verification")
            supplier_id = payload.get("supplier_id")

            # Get supplier
            supplier = await Supplier.get(ObjectId(supplier_id))
            if not supplier:
                raise ValueError("Supplier not found")

            # Mark email as verified
            supplier.contact_info.phone_verified = False  # Email verified, but phone not yet
            # Note: Supplier model doesn't have email_verified field like User
            # We'll just update the status if needed

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

    # Password reset
    async def request_password_reset(self, email: str) -> Optional[str]:
        """
        Request password reset
        Returns: reset token if supplier exists, None otherwise
        """
        try:
            email = email.lower().strip()

            # Find supplier
            supplier = await Supplier.find_one({"contact_info.primary_email": email})
            if not supplier:
                return None

            # Generate reset token
            reset_token = self.generate_reset_token(str(supplier.id), email)

            return reset_token
        except Exception as e:
            raise Exception(f"Failed to request password reset: {str(e)}")

    async def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """
        Reset supplier password
        Returns: success message
        """
        try:
            # Verify token
            payload = self.verify_token(token, "supplier_password_reset")
            supplier_id = payload.get("supplier_id")
            email = payload.get("email")

            # Get supplier
            supplier = await Supplier.get(ObjectId(supplier_id))
            if not supplier:
                raise ValueError("Supplier not found")

            # Validate new password
            self.validate_password(new_password, email)

            # Update password
            supplier.password_hash = self.hash_password(new_password)
            supplier.security.password_changed_at = utc_now()
            supplier.security.failed_login_attempts = 0
            supplier.security.locked_until = None

            await supplier.save()

            return {
                "message": "Password reset successful"
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to reset password: {str(e)}")

    # Document submission
    async def submit_verification_documents(
        self,
        supplier_id: str,
        documents: list
    ) -> Dict[str, Any]:
        """
        Submit verification documents
        Returns: success message
        """
        try:
            # Get supplier
            supplier = await Supplier.get(ObjectId(supplier_id))
            if not supplier:
                raise ValueError("Supplier not found")

            # Check if already submitted or verified
            if supplier.verification.verification_status != VerificationStatus.PENDING:
                raise ValueError("Documents already submitted or supplier already verified")

            # Validate minimum required documents
            required_types = ["business_license", "tax_document", "identity_verification"]
            submitted_types = [doc.get("document_type") for doc in documents]

            missing = [t for t in required_types if t not in submitted_types]
            if missing:
                raise ValueError(f"Missing required documents: {', '.join(missing)}")

            # Update supplier
            supplier.verification.submitted_documents = documents
            supplier.verification.verification_status = VerificationStatus.UNDER_REVIEW
            supplier.updated_at = utc_now()

            await supplier.save()

            # Emit supplier.documents_submitted event
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
