"""
Supplier Model - For business entities that supply products

Suppliers are separate from users and have:
- Company information
- Business contact details
- Verification workflow
- Product/promotion management capabilities
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CompanyType(str, Enum):
    """Legal entity types"""
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    LLC = "llc"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"
    NONPROFIT = "nonprofit"
    OTHER = "other"


class IndustryCategory(str, Enum):
    """Industry categories"""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    BEAUTY = "beauty"
    HOME_GARDEN = "home_garden"
    SPORTS_OUTDOORS = "sports_outdoors"
    FOOD_BEVERAGE = "food_beverage"
    HEALTH_WELLNESS = "health_wellness"
    TOYS_GAMES = "toys_games"
    BOOKS_MEDIA = "books_media"
    AUTOMOTIVE = "automotive"
    OTHER = "other"


# Embedded Schemas
class SupplierContactInfo(BaseModel):
    """Contact information for supplier"""

    primary_email: Annotated[EmailStr, Field(description="Primary business email for login")]
    additional_emails: Annotated[List[EmailStr], Field(default_factory=list, description="Additional contact emails")]
    primary_phone: Annotated[str, Field(description="Primary business phone")]
    additional_phones: Annotated[List[str], Field(default_factory=list, description="Additional phone numbers")]
    fax: Annotated[Optional[str], Field(None, description="Fax number")]

    # Contact person
    contact_person_name: Annotated[Optional[str], Field(None, description="Primary contact person name")]
    contact_person_title: Annotated[Optional[str], Field(None, description="Contact person job title")]
    contact_person_email: Annotated[Optional[EmailStr], Field(None, description="Contact person email")]
    contact_person_phone: Annotated[Optional[str], Field(None, description="Contact person direct phone")]

    @field_validator("additional_emails")
    @classmethod
    def validate_additional_emails(cls, v: List[EmailStr], info) -> List[EmailStr]:
        """Remove duplicates and primary email"""
        if not v:
            return v
        unique_emails = list(set(v))
        primary = info.data.get("primary_email")
        if primary and primary in unique_emails:
            unique_emails.remove(primary)
        return unique_emails


class CompanyAddress(BaseModel):
    """Company physical address"""

    street_address_1: Annotated[str, Field(min_length=1, max_length=200, description="Street address line 1")]
    street_address_2: Annotated[Optional[str], Field(None, max_length=200, description="Street address line 2")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal/ZIP code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")]

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()


class CompanyInfo(BaseModel):
    """Legal company information"""

    legal_name: Annotated[str, Field(min_length=2, max_length=200, description="Legal company name")]
    dba_name: Annotated[Optional[str], Field(None, max_length=200, description="Doing Business As (DBA) name")]
    company_type: Annotated[CompanyType, Field(description="Legal entity type")]

    # Tax information
    tax_id: Annotated[str, Field(min_length=1, description="Tax ID/EIN/VAT number")]
    tax_id_country: Annotated[str, Field(min_length=2, max_length=2, description="Country of tax registration")]

    # Registration details
    registration_number: Annotated[Optional[str], Field(None, description="Company registration number")]
    registration_date: Annotated[Optional[datetime], Field(None, description="Date of company registration")]
    registration_state: Annotated[Optional[str], Field(None, description="State/Province of registration")]

    # Address
    business_address: Annotated[CompanyAddress, Field(description="Primary business address")]
    shipping_address: Annotated[Optional[CompanyAddress], Field(None, description="Shipping/warehouse address")]
    billing_address: Annotated[Optional[CompanyAddress], Field(None, description="Billing address (if different)")]

    @field_validator("tax_id_country")
    @classmethod
    def validate_tax_country(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()


class BusinessInfo(BaseModel):
    """Business operational information"""

    # Industry
    industry_category: Annotated[IndustryCategory, Field(description="Primary industry category")]
    industry_tags: Annotated[List[str], Field(default_factory=list, description="Additional industry tags")]

    # Online presence
    website: Annotated[Optional[str], Field(None, description="Company website URL")]
    logo: Annotated[Optional[str], Field(None, description="Company logo URL")]
    description: Annotated[str, Field(min_length=10, max_length=2000, description="Company description")]

    # Social media
    facebook_url: Annotated[Optional[str], Field(None, description="Facebook page URL")]
    instagram_handle: Annotated[Optional[str], Field(None, description="Instagram username")]
    twitter_handle: Annotated[Optional[str], Field(None, description="Twitter/X username")]
    linkedin_url: Annotated[Optional[str], Field(None, description="LinkedIn company page URL")]

    # Business hours
    business_hours: Annotated[Optional[str], Field(None, description="Business operating hours")]
    timezone: Annotated[Optional[str], Field(None, description="Business timezone (IANA format)")]

    # Support
    support_email: Annotated[Optional[EmailStr], Field(None, description="Customer support email")]
    support_phone: Annotated[Optional[str], Field(None, description="Customer support phone")]


class BankingInfo(BaseModel):
    """Banking and payment information (encrypted at rest)"""

    # Bank account details
    bank_name: Annotated[Optional[str], Field(None, description="Bank name")]
    account_holder_name: Annotated[Optional[str], Field(None, description="Account holder name")]
    account_number_last4: Annotated[Optional[str], Field(None, description="Last 4 digits of account number")]
    routing_number: Annotated[Optional[str], Field(None, description="Bank routing number")]
    swift_code: Annotated[Optional[str], Field(None, description="SWIFT/BIC code for international")]

    # Payment gateway
    stripe_account_id: Annotated[Optional[str], Field(None, description="Stripe Connect account ID")]
    paypal_email: Annotated[Optional[EmailStr], Field(None, description="PayPal business email")]

    # Payout settings
    payout_currency: Annotated[str, Field(default="USD", description="Preferred payout currency")]
    payout_schedule: Annotated[str, Field(default="weekly", description="Payout frequency")]


class SupplierPermissions(BaseModel):
    """Supplier-specific permissions"""

    can_create_products: Annotated[bool, Field(default=True, description="Can create products")]
    can_create_promotions: Annotated[bool, Field(default=True, description="Can create promotions")]
    can_access_analytics: Annotated[bool, Field(default=True, description="Can view analytics")]

    max_products: Annotated[int, Field(default=1000, ge=0, le=100000, description="Max products allowed")]
    max_active_promotions: Annotated[int, Field(default=50, ge=0, le=1000, description="Max active promotions")]
    max_images_per_product: Annotated[int, Field(default=10, ge=1, le=50, description="Max images per product")]


class SupplierStats(BaseModel):
    """Supplier statistics (denormalized for performance)"""

    product_count: Annotated[int, Field(default=0, ge=0, description="Total products created")]
    active_product_count: Annotated[int, Field(default=0, ge=0, description="Currently active products")]
    promotion_count: Annotated[int, Field(default=0, ge=0, description="Total promotions created")]
    active_promotion_count: Annotated[int, Field(default=0, ge=0, description="Currently active promotions")]

    total_sales_cents: Annotated[int, Field(default=0, ge=0, description="Total sales revenue in cents")]
    total_orders: Annotated[int, Field(default=0, ge=0, description="Total orders received")]

    average_rating: Annotated[float, Field(default=0.0, ge=0.0, le=5.0, description="Average product rating")]
    total_reviews: Annotated[int, Field(default=0, ge=0, description="Total product reviews")]


class SecurityInfo(BaseModel):
    """Security-related information"""

    last_login_at: Annotated[Optional[datetime], Field(None, description="Last successful login")]
    last_login_ip: Annotated[Optional[str], Field(None, description="Last login IP address")]
    failed_login_attempts: Annotated[int, Field(default=0, ge=0, description="Failed login counter")]
    locked_until: Annotated[Optional[datetime], Field(None, description="Account locked until timestamp")]
    password_changed_at: Annotated[datetime, Field(default_factory=utc_now, description="Last password change")]


# Main Supplier Document
class Supplier(Document):
    """
    Supplier model for business entities that provide products

    Suppliers are NOT users - they cannot:
    - Browse social feeds
    - Join communities
    - Follow users/leaders

    They CAN:
    - Create and manage products
    - Create and manage promotions
    - View analytics and reports
    """

    # Authentication
    password_hash: Annotated[str, Field(description="Bcrypt hashed password")]

    # Contact information
    contact_info: Annotated[SupplierContactInfo, Field(description="Contact details")]

    # Company information
    company_info: Annotated[CompanyInfo, Field(description="Legal company information")]

    # Business information
    business_info: Annotated[BusinessInfo, Field(description="Business operational info")]

    # Banking (encrypted)
    banking_info: Annotated[Optional[BankingInfo], Field(None, description="Banking and payout details")]

    # Permissions
    permissions: Annotated[SupplierPermissions, Field(default_factory=SupplierPermissions, description="Supplier permissions")]

    # Statistics
    stats: Annotated[SupplierStats, Field(default_factory=SupplierStats, description="Supplier statistics")]

    # Security
    security: Annotated[SecurityInfo, Field(default_factory=SecurityInfo, description="Security info")]

    # Product references (for maintaining relationship)
    product_ids: Annotated[List[PydanticObjectId], Field(default_factory=list, description="References to all products")]

    # Account status
    status: Annotated[SupplierStatus, Field(default=SupplierStatus.ACTIVE, description="Account status")]

    # Soft delete
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Account creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "suppliers"

        indexes = [
            # Unique primary email for login
            [("contact_info.primary_email", 1)],

            # Find suppliers by industry
            [("business_info.industry_category", 1), ("status", 1)],

            # Find suppliers by location
            [
                ("company_info.business_address.country", 1),
                ("company_info.business_address.state", 1),
                ("company_info.business_address.city", 1)
            ],

            # Find top suppliers by sales
            [("stats.total_sales_cents", -1), ("status", 1)],

            # Soft delete filter
            [("deleted_at", 1)],

            # Tax ID lookup (for compliance)
            [("company_info.tax_id", 1)],
        ]

    # Helper methods
    def is_active(self) -> bool:
        """Check if supplier is active"""
        return self.status == SupplierStatus.ACTIVE and self.deleted_at is None

    def can_create_product(self) -> bool:
        """Check if supplier can create another product"""
        return (
            self.is_active()
            and self.permissions.can_create_products
            and self.stats.product_count < self.permissions.max_products
        )

    def can_create_promotion(self) -> bool:
        """Check if supplier can create another promotion"""
        return (
            self.is_active()
            and self.permissions.can_create_promotions
            and self.stats.active_promotion_count < self.permissions.max_active_promotions
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
        """Get all emails"""
        return [self.contact_info.primary_email] + self.contact_info.additional_emails

    def get_display_name(self) -> str:
        """Get supplier display name"""
        return self.company_info.dba_name or self.company_info.legal_name

    async def soft_delete(self) -> None:
        """Soft delete supplier account"""
        self.deleted_at = utc_now()
        self.status = SupplierStatus.DELETED
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
        """Return public-safe supplier data"""
        return {
            "id": str(self.id),
            "business_name": self.get_display_name(),
            "legal_name": self.company_info.legal_name,
            "logo": self.business_info.logo,
            "description": self.business_info.description,
            "industry": self.business_info.industry_category.value,
            "website": self.business_info.website,
            "location": {
                "city": self.company_info.business_address.city,
                "state": self.company_info.business_address.state,
                "country": self.company_info.business_address.country
            },
            "stats": {
                "product_count": self.stats.active_product_count,
                "average_rating": self.stats.average_rating,
                "total_reviews": self.stats.total_reviews
            },
            "created_at": self.created_at.isoformat()
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
