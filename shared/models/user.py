"""
User Model - For consumers and celebrities/influencers (leaders)

Supports:
- Regular consumers (role=consumer)
- Celebrities/Influencers (role=leader) with business information
- Multiple contact emails
- Business location information for celebrities
"""

from beanie import Document
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class UserRole(str, Enum):
    CONSUMER = "consumer"
    LEADER = "leader"


class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class BusinessType(str, Enum):
    """Business types for celebrity/leader accounts"""
    PERSONAL_BRAND = "personal_brand"
    COMPANY = "company"
    AGENCY = "agency"
    INFLUENCER = "influencer"
    CONTENT_CREATOR = "content_creator"
    BRAND_AMBASSADOR = "brand_ambassador"
    CELEBRITY = "celebrity"
    MEDIA_COMPANY = "media_company"
    OTHER = "other"


# Embedded Schemas
class ContactInfo(BaseModel):
    """Contact information with primary and additional emails"""

    primary_email: Annotated[EmailStr, Field(description="Primary email for login")]
    additional_emails: Annotated[List[EmailStr], Field(default_factory=list, description="Additional contact emails")]
    phone: Annotated[Optional[str], Field(None, description="Phone with country code")]

    @field_validator("additional_emails")
    @classmethod
    def validate_additional_emails(cls, v: List[EmailStr], info) -> List[EmailStr]:
        """Ensure additional emails don't duplicate primary"""
        if not v:
            return v

        unique_emails = list(set(v))
        primary = info.data.get("primary_email")
        if primary and primary in unique_emails:
            unique_emails.remove(primary)

        return unique_emails


class BusinessAddress(BaseModel):
    """Business address for celebrity/leader accounts"""

    street: Annotated[Optional[str], Field(None, max_length=200, description="Street address")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal/ZIP code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")]

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()


class CelebrityBusinessInfo(BaseModel):
    """Business information for celebrity/influencer accounts"""

    business_name: Annotated[str, Field(min_length=2, max_length=200, description="Legal business name or DBA")]
    business_type: Annotated[BusinessType, Field(description="Type of business/influence")]
    tax_id: Annotated[Optional[str], Field(None, description="Tax ID/EIN for business entities")]

    # Business address
    address: Annotated[BusinessAddress, Field(description="Business physical address")]

    # Business contact (separate from personal)
    business_email: Annotated[Optional[EmailStr], Field(None, description="Business contact email")]
    business_phone: Annotated[Optional[str], Field(None, description="Business phone number")]

    # Social media / online presence
    website: Annotated[Optional[str], Field(None, description="Official website URL")]
    instagram_handle: Annotated[Optional[str], Field(None, description="Instagram username")]
    twitter_handle: Annotated[Optional[str], Field(None, description="Twitter/X username")]
    tiktok_handle: Annotated[Optional[str], Field(None, description="TikTok username")]
    youtube_channel: Annotated[Optional[str], Field(None, description="YouTube channel URL")]

    # Representation
    agency_name: Annotated[Optional[str], Field(None, description="Management/talent agency name")]
    agent_name: Annotated[Optional[str], Field(None, description="Agent full name")]
    agent_email: Annotated[Optional[EmailStr], Field(None, description="Agent contact email")]
    agent_phone: Annotated[Optional[str], Field(None, description="Agent phone number")]


class UserProfile(BaseModel):
    """User profile information"""

    display_name: Annotated[str, Field(min_length=1, max_length=100, description="Public display name")]
    avatar: Annotated[str, Field(default="https://cdn.example.com/avatars/default.jpg", description="Avatar image URL")]
    bio: Annotated[Optional[str], Field(None, max_length=500, description="User biography")]
    date_of_birth: Annotated[Optional[datetime], Field(None, description="Date of birth")]

    # Celebrity/Leader business info (only if role=leader)
    celebrity_business_info: Annotated[Optional[CelebrityBusinessInfo], Field(None, description="Business info for leaders")]

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """Ensure display name is not empty"""
        if not v.strip():
            raise ValueError("Display name cannot be empty")
        return v.strip()


class UserPermissions(BaseModel):
    """User permissions"""

    can_post: Annotated[bool, Field(default=True, description="Can create posts")]
    can_comment: Annotated[bool, Field(default=True, description="Can comment on posts")]
    can_manage_communities: Annotated[bool, Field(default=False, description="Can create/manage communities")]
    max_communities_owned: Annotated[int, Field(default=5, ge=0, le=100, description="Max communities user can own")]
    can_create_promotions: Annotated[bool, Field(default=False, description="Can create promotional content")]


class UserStats(BaseModel):
    """User statistics (denormalized for performance)"""

    following_count: Annotated[int, Field(default=0, ge=0, description="Communities/leaders following")]
    follower_count: Annotated[int, Field(default=0, ge=0, description="Number of followers (leaders only)")]
    communities_owned: Annotated[int, Field(default=0, ge=0, description="Communities owned (leaders only)")]
    total_orders: Annotated[int, Field(default=0, ge=0, description="Total orders placed")]
    total_spent_cents: Annotated[int, Field(default=0, ge=0, description="Total spent in cents")]


class SecurityInfo(BaseModel):
    """Security-related information"""

    last_login_at: Annotated[Optional[datetime], Field(None, description="Last successful login timestamp")]
    last_login_ip: Annotated[Optional[str], Field(None, description="Last login IP address")]
    failed_login_attempts: Annotated[int, Field(default=0, ge=0, description="Failed login counter")]
    locked_until: Annotated[Optional[datetime], Field(None, description="Account locked until timestamp")]
    password_changed_at: Annotated[datetime, Field(default_factory=utc_now, description="Last password change")]


# Main User Document
class User(Document):
    """
    User model for consumers and celebrities/influencers

    - Consumers: Regular shoppers who browse and purchase
    - Leaders (Celebrities): Can manage communities and have business info
    """

    # Authentication
    password_hash: Annotated[str, Field(description="Bcrypt hashed password")]

    # Contact information
    contact_info: Annotated[ContactInfo, Field(description="Contact details")]

    # Role
    role: Annotated[UserRole, Field(default=UserRole.CONSUMER, description="User role")]

    # Profile
    profile: Annotated[UserProfile, Field(description="User profile data")]

    # Permissions
    permissions: Annotated[UserPermissions, Field(default_factory=UserPermissions, description="User permissions")]

    # Statistics
    stats: Annotated[UserStats, Field(default_factory=UserStats, description="User statistics")]

    # Security
    security: Annotated[SecurityInfo, Field(default_factory=SecurityInfo, description="Security info")]

    # Account status
    status: Annotated[UserStatus, Field(default=UserStatus.PENDING, description="Account status")]

    # Soft delete
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Document version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Account creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "users"

        indexes = [
            # Unique primary email for login
            [("contact_info.primary_email", 1)],

            # Find leaders for leaderboard
            [("role", 1), ("status", 1), ("stats.follower_count", -1)],

            # Search by additional emails
            [("contact_info.additional_emails", 1)],

            # Business location search (for leaders)
            [
                ("profile.celebrity_business_info.address.country", 1),
                ("profile.celebrity_business_info.address.state", 1),
                ("profile.celebrity_business_info.address.city", 1)
            ],

            # Soft delete filter
            [("deleted_at", 1)],

            # Security - locked accounts
            [("security.locked_until", 1)],
        ]

    @field_validator("profile")
    @classmethod
    def validate_leader_business_info(cls, v: UserProfile, info) -> UserProfile:
        """Ensure leaders have business info"""
        role = info.data.get("role")
        if role == UserRole.LEADER and not v.celebrity_business_info:
            raise ValueError("Leaders must have celebrity_business_info")
        return v

    # Helper methods
    def is_active(self) -> bool:
        """Check if account is active"""
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    def is_leader(self) -> bool:
        """Check if user is a leader/celebrity"""
        return self.role == UserRole.LEADER

    def is_consumer(self) -> bool:
        """Check if user is a consumer"""
        return self.role == UserRole.CONSUMER

    def can_create_community(self) -> bool:
        """Check if user can create another community"""
        return (
            self.is_leader()
            and self.permissions.can_manage_communities
            and self.stats.communities_owned < self.permissions.max_communities_owned
        )

    def is_account_locked(self) -> bool:
        """Check if account is temporarily locked"""
        return (
            self.security.locked_until is not None
            and utc_now() < self.security.locked_until
        )

    def get_primary_email(self) -> str:
        """Get primary email"""
        return self.contact_info.primary_email

    def get_all_emails(self) -> List[str]:
        """Get all emails (primary + additional)"""
        return [self.contact_info.primary_email] + self.contact_info.additional_emails

    async def add_additional_email(self, email: EmailStr) -> None:
        """Add an additional email"""
        if email == self.contact_info.primary_email:
            raise ValueError("Email is already the primary email")
        if email in self.contact_info.additional_emails:
            raise ValueError("Email already exists")

        self.contact_info.additional_emails.append(email)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def remove_additional_email(self, email: EmailStr) -> None:
        """Remove an additional email"""
        if email not in self.contact_info.additional_emails:
            raise ValueError("Email not found")

        self.contact_info.additional_emails.remove(email)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def promote_to_leader(self, business_info: CelebrityBusinessInfo) -> None:
        """Promote consumer to leader"""
        if self.is_leader():
            raise ValueError("User is already a leader")

        self.role = UserRole.LEADER
        self.profile.celebrity_business_info = business_info
        self.permissions.can_manage_communities = True
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def soft_delete(self) -> None:
        """Soft delete user account"""
        self.deleted_at = utc_now()
        self.status = UserStatus.DELETED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def lock_account(self, duration_minutes: int = 30) -> None:
        """Temporarily lock account"""
        from datetime import timedelta
        self.security.locked_until = utc_now() + timedelta(minutes=duration_minutes)
        self.updated_at = utc_now()
        await self.save()

    async def unlock_account(self) -> None:
        """Unlock account"""
        self.security.locked_until = None
        self.security.failed_login_attempts = 0
        self.updated_at = utc_now()
        await self.save()

    async def increment_failed_login(self) -> None:
        """Increment failed login attempts and lock if threshold exceeded"""
        self.security.failed_login_attempts += 1
        if self.security.failed_login_attempts >= 5:
            await self.lock_account(duration_minutes=30)
        else:
            await self.save()

    async def record_successful_login(self, ip_address: str) -> None:
        """Record successful login"""
        self.security.last_login_at = utc_now()
        self.security.last_login_ip = ip_address
        self.security.failed_login_attempts = 0
        self.security.locked_until = None
        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe user data"""
        result = {
            "id": str(self.id),
            "display_name": self.profile.display_name,
            "avatar": self.profile.avatar,
            "bio": self.profile.bio,
            "role": self.role.value,
            "created_at": self.created_at.isoformat()
        }

        if self.is_leader():
            result["follower_count"] = self.stats.follower_count
            result["communities_owned"] = self.stats.communities_owned

            if self.profile.celebrity_business_info:
                result["business_name"] = self.profile.celebrity_business_info.business_name
                result["business_type"] = self.profile.celebrity_business_info.business_type.value
                result["website"] = self.profile.celebrity_business_info.website
                result["instagram"] = self.profile.celebrity_business_info.instagram_handle

        return result

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
