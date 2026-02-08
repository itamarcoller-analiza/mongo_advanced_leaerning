"""
Promotion Model - Marketing campaigns created by suppliers

Promotion Types:
1. Campaign: Bundle of up to 3 products together
2. Single: Single product promotion with discount
3. Default: Auto-generated product promotion (no discount, for visibility)
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Annotated
from datetime import datetime, timezone
from enum import Enum
# ObjectId is now imported as PydanticObjectId from beanie

from src.utils.datetime_utils import utc_now


# Enums
class PromotionType(str, Enum):
    CAMPAIGN = "campaign"  # Bundle of 2-3 products
    SINGLE = "single"  # Single product with discount
    DEFAULT = "default"  # Auto-generated, no discount


class PromotionStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    CANCELLED = "cancelled"


class VisibilityType(str, Enum):
    GLOBAL = "global"  # Main feed only
    COMMUNITIES = "communities"  # Specific communities only
    BOTH = "both"  # Both global and communities


# Embedded Schemas
class SupplierInfo(BaseModel):
    """Supplier information (denormalized)"""

    supplier_id: Annotated[PydanticObjectId, Field(description="Reference to Supplier document")]
    business_name: Annotated[str, Field(description="Supplier business name")]
    logo: Annotated[Optional[str], Field(None, description="Supplier logo URL")]


class ProductSnapshot(BaseModel):
    """Snapshot of product at promotion creation time (immutable)"""

    product_id: Annotated[PydanticObjectId, Field(description="Reference to Product document")]
    product_name: Annotated[str, Field(description="Product name")]
    product_slug: Annotated[str, Field(description="Product slug")]
    product_image: Annotated[str, Field(description="Product image URL")]

    # Pricing snapshot
    original_price_cents: Annotated[int, Field(ge=0, description="Original price in cents")]
    currency: Annotated[str, Field(default="USD", description="Currency code")]
    snapshot_at: Annotated[datetime, Field(default_factory=utc_now, description="Snapshot timestamp")]

    # Variant info (if applicable)
    variant_name: Annotated[Optional[str], Field(None, description="Variant name if specific variant")]

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()


class PromotionProduct(BaseModel):
    """Product in promotion with discount details"""

    product_snapshot: Annotated[ProductSnapshot, Field(description="Product snapshot")]

    # Discount (only for campaign and single promotions)
    discount_percent: Annotated[int, Field(default=0, ge=0, le=100, description="Discount percentage")]
    discounted_price_cents: Annotated[int, Field(ge=0, description="Price after discount")]

    # Current product status (updated by background job)
    current_status: Annotated[str, Field(default="active", description="Current product status")]
    current_price_cents: Annotated[Optional[int], Field(None, description="Current actual price")]
    price_discrepancy: Annotated[bool, Field(default=False, description="Price changed significantly")]
    last_checked_at: Annotated[datetime, Field(default_factory=utc_now, description="Last status check")]


class PromotionVisibility(BaseModel):
    """Where the promotion appears"""

    type: Annotated[VisibilityType, Field(description="Visibility type")]
    community_ids: Annotated[List[PydanticObjectId], Field(default_factory=list, description="Target communities")]

    # Computed fields
    is_global: Annotated[bool, Field(default=False, description="Appears on main feed")]
    community_count: Annotated[int, Field(default=0, ge=0, description="Number of communities")]
    estimated_reach: Annotated[int, Field(default=0, ge=0, description="Estimated audience size")]

    @field_validator("community_ids")
    @classmethod
    def validate_community_ids(cls, v: List[PydanticObjectId], info) -> List[PydanticObjectId]:
        """Ensure community_ids match visibility type"""
        visibility_type = info.data.get("type")

        if visibility_type == VisibilityType.GLOBAL and v:
            raise ValueError("Global promotions should not have community_ids")

        if visibility_type == VisibilityType.COMMUNITIES and not v:
            raise ValueError("Community promotions must have at least one community_id")

        return v


class PromotionSchedule(BaseModel):
    """Promotion scheduling"""

    start_date: Annotated[datetime, Field(description="Promotion start date (UTC)")]
    end_date: Annotated[datetime, Field(description="Promotion end date (UTC)")]
    timezone: Annotated[str, Field(default="UTC", description="Display timezone")]

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: datetime, info) -> datetime:
        """Ensure end_date is after start_date"""
        start_date = info.data.get("start_date")
        if start_date and v <= start_date:
            raise ValueError("end_date must be after start_date")
        return v


class PromotionStats(BaseModel):
    """Promotion performance statistics"""

    impressions: Annotated[int, Field(default=0, ge=0, description="Feed views")]
    clicks: Annotated[int, Field(default=0, ge=0, description="Banner clicks")]
    conversions: Annotated[int, Field(default=0, ge=0, description="Purchases")]
    revenue_cents: Annotated[int, Field(default=0, ge=0, description="Total revenue in cents")]

    # Community breakdown
    community_stats: Annotated[Dict[str, Dict[str, int]], Field(
        default_factory=dict,
        description="Stats per community {community_id: {impressions, clicks, conversions}}"
    )]

    # Conversion rates
    click_through_rate: Annotated[float, Field(default=0.0, ge=0.0, le=100.0, description="CTR %")]
    conversion_rate: Annotated[float, Field(default=0.0, ge=0.0, le=100.0, description="Conversion %")]

    # Last updated
    last_impression_at: Annotated[Optional[datetime], Field(None, description="Last viewed")]
    last_conversion_at: Annotated[Optional[datetime], Field(None, description="Last purchase")]


class PromotionTerms(BaseModel):
    """Terms and conditions"""

    terms_text: Annotated[str, Field(max_length=2000, description="Terms and conditions")]
    restrictions: Annotated[List[str], Field(default_factory=list, description="List of restrictions")]
    min_purchase_amount_cents: Annotated[Optional[int], Field(None, ge=0, description="Minimum purchase amount")]
    max_uses_per_user: Annotated[Optional[int], Field(None, ge=1, description="Max uses per customer")]


# Main Promotion Document
class Promotion(Document):
    """
    Promotion model - marketing campaigns by suppliers

    Types:
    - Campaign: Bundle of 2-3 products together
    - Single: Single product with discount
    - Default: Auto-generated for eligible products (no discount)
    """

    # Promotion type
    promotion_type: Annotated[PromotionType, Field(description="Type of promotion")]

    # Supplier
    supplier: Annotated[SupplierInfo, Field(description="Supplier information")]

    # Basic information
    title: Annotated[str, Field(min_length=5, max_length=200, description="Promotion title")]
    description: Annotated[str, Field(min_length=10, max_length=2000, description="Promotion description")]
    banner_image: Annotated[str, Field(description="Promotion banner image URL")]

    # Products (1 for single/default, 2-3 for campaign)
    products: Annotated[List[PromotionProduct], Field(description="Products in promotion")]

    # Visibility
    visibility: Annotated[PromotionVisibility, Field(description="Where promotion appears")]

    # Schedule
    schedule: Annotated[PromotionSchedule, Field(description="Start and end dates")]

    # Status
    status: Annotated[PromotionStatus, Field(default=PromotionStatus.DRAFT, description="Promotion status")]
    status_reasons: Annotated[List[str], Field(default_factory=list, description="Reasons for status change")]

    # Terms
    terms: Annotated[Optional[PromotionTerms], Field(None, description="Terms and conditions")]

    # Statistics
    stats: Annotated[PromotionStats, Field(default_factory=PromotionStats, description="Performance stats")]

    # Auto-generated flag (for default promotions)
    is_auto_generated: Annotated[bool, Field(default=False, description="Auto-generated by system")]

    # Lifecycle tracking
    first_activated_at: Annotated[Optional[datetime], Field(None, description="First time promotion went active (immutable, defines 'sent')")]
    paused_at: Annotated[Optional[datetime], Field(None, description="When promotion was paused")]
    cancellation_reason: Annotated[Optional[str], Field(None, max_length=500, description="Reason for cancellation")]

    # Soft delete
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "promotions"

        indexes = [
            # Supplier's promotions
            [("supplier.supplier_id", 1), ("status", 1), ("created_at", -1)],

            # Active promotions
            [("status", 1), ("schedule.start_date", 1)],
            [("status", 1), ("schedule.end_date", 1)],

            # Promotion type filtering
            [("promotion_type", 1), ("status", 1)],

            # Community promotions
            [("visibility.community_ids", 1), ("status", 1)],

            # Auto-generated promotions
            [("is_auto_generated", 1), ("status", 1)],

            # Product promotions (for checking if product already has promotion)
            [("products.product_snapshot.product_id", 1), ("status", 1)],

            # Soft delete
            [("deleted_at", 1)],

            # Performance sorting
            [("stats.conversions", -1), ("status", 1)],

            # Sent status tracking
            [("first_activated_at", 1)],

            # Feed queries: global
            [("status", 1), ("visibility.type", 1), ("schedule.start_date", 1), ("schedule.end_date", 1), ("deleted_at", 1)],
        ]

    @field_validator("products")
    @classmethod
    def validate_products(cls, v: List[PromotionProduct], info) -> List[PromotionProduct]:
        """Validate product count based on promotion type"""
        promotion_type = info.data.get("promotion_type")

        if promotion_type == PromotionType.CAMPAIGN:
            if len(v) < 2 or len(v) > 3:
                raise ValueError("Campaign promotions must have 2-3 products")

        elif promotion_type in [PromotionType.SINGLE, PromotionType.DEFAULT]:
            if len(v) != 1:
                raise ValueError("Single and default promotions must have exactly 1 product")

        # Validate discounts for default promotions
        if promotion_type == PromotionType.DEFAULT:
            for product in v:
                if product.discount_percent > 0:
                    raise ValueError("Default promotions cannot have discounts")

        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: PromotionVisibility) -> PromotionVisibility:
        """Update computed fields based on visibility type"""
        v.is_global = v.type in [VisibilityType.GLOBAL, VisibilityType.BOTH]
        v.community_count = len(v.community_ids)
        return v

    # Helper methods
    @property
    def is_sent(self) -> bool:
        """Check if promotion has been sent (ever reached ACTIVE status)"""
        return self.first_activated_at is not None

    def can_delete(self) -> tuple:
        """
        Check if promotion can be hard deleted.
        Returns (can_delete: bool, error_code: str | None)
        """
        if self.is_auto_generated:
            return False, "AUTO_GENERATED_PROMO_PROTECTED"

        if self.status == PromotionStatus.ACTIVE:
            return False, "STATUS_PREVENTS_DELETE"

        if self.is_sent:
            return False, "CANNOT_DELETE_SENT_PROMOTION"

        return True, None

    def is_active(self) -> bool:
        """Check if promotion is currently active"""
        if self.status != PromotionStatus.ACTIVE:
            return False

        now = utc_now()
        start_date = self.schedule.start_date
        end_date = self.schedule.end_date
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        return start_date <= now <= end_date

    def is_scheduled(self) -> bool:
        """Check if promotion is scheduled for future"""
        now = utc_now()
        start_date = self.schedule.start_date
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        return (
            self.status == PromotionStatus.SCHEDULED
            and now < start_date
        )

    def is_ended(self) -> bool:
        """Check if promotion has ended"""
        return (
            self.status == PromotionStatus.ENDED
            or utc_now() > self.schedule.end_date
        )

    def has_discount(self) -> bool:
        """Check if promotion has any discount"""
        return any(p.discount_percent > 0 for p in self.products)

    def get_total_discount_value(self) -> int:
        """Calculate total discount value in cents"""
        return sum(
            p.product_snapshot.original_price_cents - p.discounted_price_cents
            for p in self.products
        )

    def get_bundle_price(self) -> int:
        """Get total bundle price for campaign promotions"""
        if self.promotion_type != PromotionType.CAMPAIGN:
            raise ValueError("Only campaign promotions have bundle pricing")

        return sum(p.discounted_price_cents for p in self.products)

    def get_original_bundle_price(self) -> int:
        """Get original total price for campaign promotions"""
        if self.promotion_type != PromotionType.CAMPAIGN:
            raise ValueError("Only campaign promotions have bundle pricing")

        return sum(p.product_snapshot.original_price_cents for p in self.products)

    def calculate_savings(self) -> Dict[str, int]:
        """Calculate savings amount and percentage"""
        total_original = sum(p.product_snapshot.original_price_cents for p in self.products)
        total_discounted = sum(p.discounted_price_cents for p in self.products)
        savings = total_original - total_discounted

        return {
            "savings_cents": savings,
            "savings_percent": int((savings / total_original * 100)) if total_original > 0 else 0
        }

    async def activate_promotion(self) -> None:
        """Activate a scheduled promotion"""
        if self.status != PromotionStatus.SCHEDULED:
            raise ValueError("Only scheduled promotions can be activated")

        now = utc_now()

        # Set first_activated_at only once (immutable)
        if self.first_activated_at is None:
            self.first_activated_at = now

        self.status = PromotionStatus.ACTIVE
        self.paused_at = None  # Clear any previous pause
        self.updated_at = now
        self.version += 1
        await self.save()

    async def pause_promotion(self, reason: str) -> None:
        """Pause an active promotion"""
        if self.status != PromotionStatus.ACTIVE:
            raise ValueError("Only active promotions can be paused")

        now = utc_now()
        self.status = PromotionStatus.PAUSED
        self.paused_at = now
        self.status_reasons.append(f"Paused: {reason}")
        self.updated_at = now
        self.version += 1
        await self.save()

    async def resume_promotion(self) -> None:
        """Resume a paused promotion"""
        if self.status != PromotionStatus.PAUSED:
            raise ValueError("Only paused promotions can be resumed")

        # Check if promotion has expired
        now = utc_now()
        end_date = self.schedule.end_date
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if now > end_date:
            raise ValueError("Cannot resume: promotion end date has passed")

        self.status = PromotionStatus.ACTIVE
        self.paused_at = None
        self.status_reasons.append("Resumed")
        self.updated_at = now
        self.version += 1
        await self.save()

    async def end_promotion(self) -> None:
        """End the promotion"""
        self.status = PromotionStatus.ENDED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def cancel_promotion(self, reason: str) -> None:
        """Cancel the promotion (soft delete)"""
        if self.status == PromotionStatus.ENDED:
            raise ValueError("Cannot cancel an ended promotion")

        now = utc_now()
        self.status = PromotionStatus.CANCELLED
        self.cancellation_reason = reason
        self.deleted_at = now
        self.status_reasons.append(f"Cancelled: {reason}")
        self.updated_at = now
        self.version += 1
        await self.save()

    async def schedule_promotion(self) -> None:
        """Schedule a draft promotion (draft -> scheduled)"""
        if self.status != PromotionStatus.DRAFT:
            raise ValueError("Only draft promotions can be scheduled")

        now = utc_now()
        start_date = self.schedule.start_date
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        # If start date is in the past or now, activate immediately
        if now >= start_date:
            self.status = PromotionStatus.ACTIVE
            if self.first_activated_at is None:
                self.first_activated_at = now
            self.status_reasons.append("Activated immediately")
        else:
            self.status = PromotionStatus.SCHEDULED
            self.status_reasons.append("Scheduled")

        self.updated_at = now
        self.version += 1
        await self.save()

    async def soft_delete(self) -> None:
        """Soft delete promotion"""
        self.deleted_at = utc_now()
        self.status = PromotionStatus.CANCELLED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def increment_impressions(self, community_id: Optional[str] = None) -> None:
        """Increment impression counter"""
        self.stats.impressions += 1
        self.stats.last_impression_at = utc_now()

        # Update community stats if applicable
        if community_id:
            if community_id not in self.stats.community_stats:
                self.stats.community_stats[community_id] = {
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0
                }
            self.stats.community_stats[community_id]["impressions"] += 1

        # Update CTR
        if self.stats.impressions > 0:
            self.stats.click_through_rate = (self.stats.clicks / self.stats.impressions) * 100

        await self.save()

    async def increment_clicks(self, community_id: Optional[str] = None) -> None:
        """Increment click counter"""
        self.stats.clicks += 1

        # Update community stats if applicable
        if community_id:
            if community_id not in self.stats.community_stats:
                self.stats.community_stats[community_id] = {
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0
                }
            self.stats.community_stats[community_id]["clicks"] += 1

        # Update CTR
        if self.stats.impressions > 0:
            self.stats.click_through_rate = (self.stats.clicks / self.stats.impressions) * 100

        await self.save()

    async def record_conversion(self, revenue_cents: int, community_id: Optional[str] = None) -> None:
        """Record a conversion (purchase)"""
        self.stats.conversions += 1
        self.stats.revenue_cents += revenue_cents
        self.stats.last_conversion_at = utc_now()

        # Update community stats if applicable
        if community_id:
            if community_id not in self.stats.community_stats:
                self.stats.community_stats[community_id] = {
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0
                }
            self.stats.community_stats[community_id]["conversions"] += 1

        # Update conversion rate
        if self.stats.clicks > 0:
            self.stats.conversion_rate = (self.stats.conversions / self.stats.clicks) * 100

        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe promotion data"""
        savings = self.calculate_savings()

        result = {
            "id": str(self.id),
            "type": self.promotion_type.value,
            "supplier": {
                "id": str(self.supplier.supplier_id),
                "name": self.supplier.business_name,
                "logo": self.supplier.logo
            },
            "title": self.title,
            "description": self.description,
            "banner_image": self.banner_image,
            "products": [
                {
                    "id": str(p.product_snapshot.product_id),
                    "name": p.product_snapshot.product_name,
                    "image": p.product_snapshot.product_image,
                    "original_price": p.product_snapshot.original_price_cents / 100,
                    "discounted_price": p.discounted_price_cents / 100,
                    "discount_percent": p.discount_percent,
                    "variant": p.product_snapshot.variant_name
                }
                for p in self.products
            ],
            "schedule": {
                "start_date": self.schedule.start_date.isoformat(),
                "end_date": self.schedule.end_date.isoformat(),
                "timezone": self.schedule.timezone
            },
            "savings": {
                "amount": savings["savings_cents"] / 100,
                "percent": savings["savings_percent"]
            },
            "status": self.status.value,
            "is_active": self.is_active(),
            "created_at": self.created_at.isoformat()
        }

        # Add bundle pricing for campaigns
        if self.promotion_type == PromotionType.CAMPAIGN:
            result["bundle_pricing"] = {
                "original_total": self.get_original_bundle_price() / 100,
                "discounted_total": self.get_bundle_price() / 100,
                "currency": self.products[0].product_snapshot.currency
            }

        # Add terms if any
        if self.terms:
            result["terms"] = {
                "text": self.terms.terms_text,
                "restrictions": self.terms.restrictions
            }

        return result

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
