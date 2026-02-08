"""
Authentication Service - Business logic for user authentication
"""

import bcrypt
import jwt
import re
from datetime import  timedelta
from typing import Optional, Dict, Any
from bson import ObjectId

from shared.models.user import User, UserRole, UserStatus, ContactInfo, UserProfile, CelebrityBusinessInfo, BusinessAddress
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.serialization import oid_to_str


# JWT Configuration
JWT_SECRET = "your-secret-key-here"  # TODO: Move to environment variable
JWT_ALGORITHM = "HS256"


class AuthService:
    """Service class for authentication operations"""

    def __init__(self):
        """Initialize authentication service"""
        self.password_min_length = 8
        self.password_max_length = 128
        self.max_failed_attempts = 5
        self.lock_duration_minutes = 30
        self._kafka = get_kafka_producer()

        # Password regex pattern: at least 1 uppercase, 1 lowercase, 1 digit
        self.password_pattern = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$'
        )

    # Token utilities
    def generate_verification_token(self, user_id: str, email: str) -> str:
        """Generate email verification JWT token (6 hour expiry)"""
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "email_verification",
            "exp": utc_now() + timedelta(hours=6)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def generate_reset_token(self, user_id: str, email: str) -> str:
        """Generate password reset JWT token (1 hour expiry)"""
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "password_reset",
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

        # Check pattern (uppercase, lowercase, digit)
        if not self.password_pattern.match(password):
            raise ValueError("Password must contain at least one uppercase letter, one lowercase letter, and one digit")

        # Check if password contains email username
        email_username = email.split('@')[0].lower()
        if email_username in password.lower():
            raise ValueError("Password cannot contain your email username")

    # Email utilities
    async def is_email_available(self, email: str) -> bool:
        """Check if email is available (not used as primary or additional email)"""
        try:
            email = email.lower().strip()

            # Check primary email
            user = await User.find_one({"contact_info.primary_email": email})
            if user:
                return False

            # Check additional emails
            user = await User.find_one({"contact_info.additional_emails": email})
            if user:
                return False

            return True
        except Exception as e:
            raise Exception(f"Failed to check email availability: {str(e)}")

    # Registration
    async def register_consumer(
        self,
        email: str,
        password: str,
        display_name: str
    ) -> Dict[str, Any]:
        """
        Register a new consumer user
        Returns: dict with user data and verification token
        """
        try:
            email = email.lower().strip()
            display_name = display_name.strip()

            # Check email availability
            if not await self.is_email_available(email):
                raise ValueError("Email already in use")

            # Validate password
            self.validate_password(password, email)

            # Create user document
            user = User(
                password_hash=self.hash_password(password),
                contact_info=ContactInfo(primary_email=email),
                profile=UserProfile(display_name=display_name)
            )

            await user.insert()

            # Emit user.registered event
            user_id = oid_to_str(user.id)
            self._kafka.emit(
                topic=Topic.USER,
                action="registered",
                entity_id=user_id,
                data=user.model_dump(mode="json"),
            )

            # Generate verification token
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

    async def register_leader(
        self,
        email: str,
        password: str,
        display_name: str,
        company_name: str,
        business_type: str,
        country: str,
        city: str,
        zip_code: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        street_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new leader user (requires approval)
        Returns: dict with user data and verification token
        """
        try:
            email = email.lower().strip()
            display_name = display_name.strip()

            # Check email availability
            if not await self.is_email_available(email):
                raise ValueError("Email already in use")

            # Validate password
            self.validate_password(password, email)

            # Validate business type
            if business_type not in ["personal_brand", "company", "agency"]:
                raise ValueError("Invalid business type")

            # Create user document with business info
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

            await user.insert()

            # Emit user.registered event
            user_id = oid_to_str(user.id)
            self._kafka.emit(
                topic=Topic.USER,
                action="registered",
                entity_id=user_id,
                data=user.model_dump(mode="json"),
            )

            # Generate verification token
            verification_token = self.generate_verification_token(user_id, email)

            return {
                "user": {
                    "id": user_id,
                    "email": user.contact_info.primary_email,
                    "display_name": user.profile.display_name,
                    "role": user.role.value,
                    "status": user.status.value,
                    "business_info": {
                        "company_name": company_name,
                        "business_type": business_type
                    }
                },
                "verification_token": verification_token
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to register leader: {str(e)}")

    # Login
    async def login(self, email: str, password: str, ip_address: str) -> Dict[str, Any]:
        """
        Authenticate user and return user data
        Returns: user data dictionary
        """
        try:
            email = email.lower().strip()

            # Find user by email
            user = await User.find_one({"contact_info.primary_email": email})
            if not user:
                raise ValueError("Invalid email or password")

            # Check if deleted
            if user.deleted_at is not None:
                raise ValueError("Account no longer exists")

            # Check if suspended
            if user.status == UserStatus.SUSPENDED:
                raise ValueError("Account suspended. Contact support.")

            # Check if locked
            if user.security.locked_until:
                if utc_now() < user.security.locked_until:
                    remaining = int((user.security.locked_until - utc_now()).total_seconds() / 60)
                    raise ValueError(f"Account locked. Try again in {remaining} minutes")
                else:
                    # Lock expired, reset
                    user.security.locked_until = None
                    user.security.failed_login_attempts = 0
                    await user.save()

            # Check if email verified (disabled for development)
            # if not user.contact_info.email_verified:
            #     raise ValueError("Email not verified. Check your inbox.")

            # Check if active (disabled for development)
            # if user.status != UserStatus.ACTIVE:
            #     raise ValueError("Account pending approval")

            # Verify password
            if not self.verify_password(password, user.password_hash):
                # Increment failed attempts
                user.security.failed_login_attempts += 1

                # Lock account after max attempts
                if user.security.failed_login_attempts >= self.max_failed_attempts:
                    user.security.locked_until = utc_now() + timedelta(minutes=self.lock_duration_minutes)
                    await user.save()

                    # Emit user.account_locked event
                    self._kafka.emit(
                        topic=Topic.USER,
                        action="account_locked",
                        entity_id=oid_to_str(user.id),
                        data={
                            "email": email,
                            "failed_attempts": user.security.failed_login_attempts,
                            "lock_duration_minutes": self.lock_duration_minutes,
                        },
                    )

                    raise ValueError(f"Too many failed attempts. Account locked for {self.lock_duration_minutes} minutes")

                await user.save()
                raise ValueError("Invalid email or password")

            # Successful login - record it
            await user.record_successful_login(ip_address)

            # Emit user.login event
            user_id = oid_to_str(user.id)
            self._kafka.emit(
                topic=Topic.USER,
                action="login",
                entity_id=user_id,
                data={
                    "email": user.contact_info.primary_email,
                    "role": user.role.value,
                    "ip_address": ip_address,
                },
            )

            # Return user data
            return {
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
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to login: {str(e)}")

    # Email verification
    async def verify_email(self, token: str) -> Dict[str, Any]:
        """
        Verify user email and activate account
        Returns: user data dictionary
        """
        try:
            # Verify token
            payload = self.verify_token(token, "email_verification")
            user_id = payload.get("user_id")

            # Get user
            user = await User.get(ObjectId(user_id))
            if not user:
                raise ValueError("User not found")

            # Mark email as verified
            user.contact_info.email_verified = True

            # Auto-activate consumers, leaders need admin approval
            if user.role == UserRole.CONSUMER:
                user.status = UserStatus.ACTIVE

            await user.save()

            # Emit user.email_verified event
            user_id = oid_to_str(user.id)
            self._kafka.emit(
                topic=Topic.USER,
                action="email_verified",
                entity_id=user_id,
                data={
                    "email": user.contact_info.primary_email,
                    "status": user.status.value,
                },
            )

            return {
                "id": user_id,
                "email": user.contact_info.primary_email,
                "email_verified": True,
                "status": user.status.value
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to verify email: {str(e)}")

    # Password reset
    async def request_password_reset(self, email: str) -> Optional[str]:
        """
        Request password reset
        Returns: reset token if user exists, None otherwise
        """
        try:
            email = email.lower().strip()

            # Find user
            user = await User.find_one({"contact_info.primary_email": email})
            if not user:
                return None

            # Emit user.password_reset_requested event
            user_id = oid_to_str(user.id)
            self._kafka.emit(
                topic=Topic.USER,
                action="password_reset_requested",
                entity_id=user_id,
                data={"email": email},
            )

            # Generate reset token
            reset_token = self.generate_reset_token(user_id, email)

            return reset_token
        except Exception as e:
            raise Exception(f"Failed to request password reset: {str(e)}")

    async def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """
        Reset user password
        Returns: success message
        """
        try:
            # Verify token
            payload = self.verify_token(token, "password_reset")
            user_id = payload.get("user_id")
            email = payload.get("email")

            # Get user
            user = await User.get(ObjectId(user_id))
            if not user:
                raise ValueError("User not found")

            # Validate new password
            self.validate_password(new_password, email)

            # Update password
            user.password_hash = self.hash_password(new_password)
            user.security.password_changed_at = utc_now()
            user.security.failed_login_attempts = 0
            user.security.locked_until = None

            await user.save()

            # Emit user.password_reset event
            self._kafka.emit(
                topic=Topic.USER,
                action="password_reset",
                entity_id=oid_to_str(user.id),
                data={},
            )

            return {
                "message": "Password reset successful"
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to reset password: {str(e)}")
