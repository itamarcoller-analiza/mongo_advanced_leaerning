"""
Community Model - Communities owned and managed by leaders (celebrities/influencers)

Communities are social groups where:
- Leaders can post content and promotions
- Users can follow/join to see community feed
- Can be public or private
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class CommunityStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CommunityVisibility(str, Enum):
    """Community access level"""
    PUBLIC = "public"  # Anyone can see and join
    PRIVATE = "private"  # Invite-only or request to join


class CommunityCategory(str, Enum):
    """Community categories"""
    FASHION = "fashion"
    BEAUTY = "beauty"
    FITNESS = "fitness"
    FOOD = "food"
    TECH = "tech"
    GAMING = "gaming"
    MUSIC = "music"
    ART = "art"
    LIFESTYLE = "lifestyle"
    BUSINESS = "business"
    EDUCATION = "education"
    TRAVEL = "travel"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


# Embedded Schemas
class CommunityOwner(BaseModel):
    """Community owner information (denormalized from User)"""

    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]
    display_name: Annotated[str, Field(description="Owner display name")]
    avatar: Annotated[str, Field(description="Owner avatar URL")]
    business_email: Annotated[Optional[str], Field(None, description="Business contact email")]


class BusinessAddress(BaseModel):
    """Business address for community"""

    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal/ZIP code")]

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()


class CommunityPurpose(BaseModel):
    """Community purpose and mission"""

    mission_statement: Annotated[str, Field(min_length=10, max_length=1000, description="Community mission statement")]
    goals: Annotated[List[str], Field(default_factory=list, description="Community goals")]
    target_audience: Annotated[Optional[str], Field(None, max_length=500, description="Target audience description")]


class CommunitySettings(BaseModel):
    """Community configuration and rules"""

    visibility: Annotated[CommunityVisibility, Field(default=CommunityVisibility.PUBLIC, description="Access level")]
    requires_approval: Annotated[bool, Field(default=False, description="Require approval to join")]
    allow_member_posts: Annotated[bool, Field(default=False, description="Allow members to post")]
    moderate_posts: Annotated[bool, Field(default=True, description="Posts require approval")]
    max_members: Annotated[Optional[int], Field(None, ge=1, description="Maximum members allowed")]
    min_age: Annotated[Optional[int], Field(None, ge=13, le=100, description="Minimum age requirement")]
    allowed_countries: Annotated[List[str], Field(default_factory=list, description="Allowed country codes")]
    blocked_countries: Annotated[List[str], Field(default_factory=list, description="Blocked country codes")]


class CommunityStats(BaseModel):
    """Community statistics (denormalized for performance)"""

    member_count: Annotated[int, Field(default=0, ge=0, description="Total members")]
    active_member_count: Annotated[int, Field(default=0, ge=0, description="Active members (30 days)")]
    post_count: Annotated[int, Field(default=0, ge=0, description="Total posts")]
    promotion_count: Annotated[int, Field(default=0, ge=0, description="Total promotions")]
    total_likes: Annotated[int, Field(default=0, ge=0, description="Total likes")]
    total_comments: Annotated[int, Field(default=0, ge=0, description="Total comments")]
    total_shares: Annotated[int, Field(default=0, ge=0, description="Total shares")]
    last_post_at: Annotated[Optional[datetime], Field(None, description="Last post timestamp")]
    last_active_at: Annotated[Optional[datetime], Field(None, description="Last activity timestamp")]


class CommunityBranding(BaseModel):
    """Visual branding for community"""

    cover_image: Annotated[str, Field(description="Cover/banner image URL")]
    logo: Annotated[Optional[str], Field(None, description="Community logo URL")]
    primary_color: Annotated[Optional[str], Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Primary theme color")]
    secondary_color: Annotated[Optional[str], Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Secondary color")]


class CommunityRules(BaseModel):
    """Community rules and guidelines"""

    rule_title: Annotated[str, Field(max_length=100, description="Rule title")]
    rule_description: Annotated[str, Field(max_length=1000, description="Rule description")]
    display_order: Annotated[int, Field(default=0, description="Display order")]


class CommunityLinks(BaseModel):
    """External links and social media"""

    website: Annotated[Optional[HttpUrl], Field(None, description="Community website")]
    instagram: Annotated[Optional[str], Field(None, description="Instagram handle")]
    twitter: Annotated[Optional[str], Field(None, description="Twitter handle")]
    youtube: Annotated[Optional[str], Field(None, description="YouTube channel")]
    discord: Annotated[Optional[str], Field(None, description="Discord invite link")]


# Main Community Document
class Community(Document):
    """
    Community model - owned and managed by leaders

    Features:
    - Public or private membership
    - Feed for posts and promotions
    - Member management
    - Purpose-driven communities
    - Business location
    """

    # Basic information
    name: Annotated[str, Field(min_length=2, max_length=100, description="Community name")]
    slug: Annotated[str, Field(min_length=2, max_length=150, description="URL-friendly slug")]
    description: Annotated[str, Field(min_length=10, max_length=2000, description="Community description")]
    tagline: Annotated[Optional[str], Field(None, max_length=200, description="Short tagline")]

    # Purpose
    purpose: Annotated[CommunityPurpose, Field(description="Community purpose and mission")]

    # Business address
    business_address: Annotated[BusinessAddress, Field(description="Business location")]

    # Owner
    owner: Annotated[CommunityOwner, Field(description="Community owner information")]

    # Members (references to User IDs)
    # NOTE: For large communities (>10K members), consider using a separate follows collection
    member_ids: Annotated[List[PydanticObjectId], Field(default_factory=list, description="Member user IDs")]

    # Category
    category: Annotated[CommunityCategory, Field(description="Primary category")]
    tags: Annotated[List[str], Field(default_factory=list, description="Additional tags")]

    # Branding
    branding: Annotated[CommunityBranding, Field(description="Visual branding")]

    # Settings
    settings: Annotated[CommunitySettings, Field(default_factory=CommunitySettings, description="Community settings")]

    # Rules
    rules: Annotated[List[CommunityRules], Field(default_factory=list, description="Community rules")]

    # External links
    links: Annotated[Optional[CommunityLinks], Field(None, description="External links")]

    # Statistics
    stats: Annotated[CommunityStats, Field(default_factory=CommunityStats, description="Community statistics")]

    # Status
    status: Annotated[CommunityStatus, Field(default=CommunityStatus.ACTIVE, description="Community status")]
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Featured
    is_featured: Annotated[bool, Field(default=False, description="Featured on discovery page")]
    featured_until: Annotated[Optional[datetime], Field(None, description="Featured expiration date")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "communities"

        indexes = [
            # Unique slug
            [("slug", 1)],

            # Owner's communities
            [("owner.user_id", 1), ("status", 1), ("created_at", -1)],

            # Community discovery
            [("status", 1), ("settings.visibility", 1), ("stats.member_count", -1)],
            [("category", 1), ("status", 1), ("stats.member_count", -1)],

            # Location-based search
            [
                ("business_address.country", 1),
                ("business_address.city", 1),
                ("status", 1)
            ],

            # Featured communities
            [("is_featured", 1), ("featured_until", 1)],

            # Search by tags (multikey index)
            [("tags", 1), ("status", 1)],

            # Member lookup (multikey index)
            [("member_ids", 1)],

            # Active communities
            [("stats.last_active_at", -1), ("status", 1)],

            # Soft delete
            [("deleted_at", 1)],
        ]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Normalize slug to lowercase"""
        slug = v.lower().strip()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError("Slug can only contain letters, numbers, hyphens, underscores")
        return slug

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Normalize tags and remove duplicates"""
        if not v:
            return v
        return list(set(tag.lower().strip() for tag in v if tag.strip()))

    @field_validator("member_ids")
    @classmethod
    def validate_member_ids(cls, v: List[PydanticObjectId]) -> List[PydanticObjectId]:
        """Remove duplicate member IDs and warn if too many"""
        if not v:
            return v

        unique_ids = list(set(v))

        # Warn if approaching document size limits
        if len(unique_ids) > 10000:
            import warnings
            warnings.warn(
                f"Community has {len(unique_ids)} members. "
                "Consider using a separate follows collection for scalability."
            )

        return unique_ids

    # Helper methods
    def is_active(self) -> bool:
        """Check if community is active"""
        return self.status == CommunityStatus.ACTIVE and self.deleted_at is None

    def is_public(self) -> bool:
        """Check if community is public"""
        return self.settings.visibility == CommunityVisibility.PUBLIC

    def can_accept_members(self) -> bool:
        """Check if community can accept new members"""
        if not self.is_active():
            return False

        max_members = self.settings.max_members
        if max_members and len(self.member_ids) >= max_members:
            return False

        return True

    def is_full(self) -> bool:
        """Check if community has reached member limit"""
        if not self.settings.max_members:
            return False
        return len(self.member_ids) >= self.settings.max_members

    def is_user_member(self, user_id: PydanticObjectId) -> bool:
        """Check if user is a member"""
        return user_id in self.member_ids

    def is_user_owner(self, user_id: PydanticObjectId) -> bool:
        """Check if user is the owner"""
        return self.owner.user_id == user_id

    async def add_member(self, user_id: PydanticObjectId) -> bool:
        """Add a member to the community"""
        if user_id in self.member_ids:
            return False  # Already a member

        if not self.can_accept_members():
            raise ValueError("Community cannot accept new members")

        self.member_ids.append(user_id)
        self.stats.member_count = len(self.member_ids)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def remove_member(self, user_id: PydanticObjectId) -> bool:
        """Remove a member from the community"""
        if user_id not in self.member_ids:
            return False  # Not a member

        self.member_ids.remove(user_id)
        self.stats.member_count = len(self.member_ids)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    def get_members(self, limit: int = 100, offset: int = 0) -> List[PydanticObjectId]:
        """Get paginated list of member IDs"""
        return self.member_ids[offset:offset + limit]

    async def add_rule(self, title: str, description: str, order: int = 0) -> None:
        """Add a community rule"""
        rule = CommunityRules(
            rule_title=title,
            rule_description=description,
            display_order=order
        )
        self.rules.append(rule)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def increment_post_count(self) -> None:
        """Increment post count"""
        self.stats.post_count += 1
        self.stats.last_post_at = utc_now()
        self.stats.last_active_at = utc_now()
        self.updated_at = utc_now()
        await self.save()

    async def increment_promotion_count(self) -> None:
        """Increment promotion count"""
        self.stats.promotion_count += 1
        self.stats.last_active_at = utc_now()
        self.updated_at = utc_now()
        await self.save()

    async def archive_community(self) -> None:
        """Archive the community"""
        self.status = CommunityStatus.ARCHIVED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def suspend_community(self) -> None:
        """Suspend the community"""
        self.status = CommunityStatus.SUSPENDED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def soft_delete(self) -> None:
        """Soft delete community"""
        self.deleted_at = utc_now()
        self.status = CommunityStatus.DELETED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def feature_community(self, duration_days: int = 7) -> None:
        """Feature community on discovery page"""
        from datetime import timedelta

        self.is_featured = True
        self.featured_until = utc_now() + timedelta(days=duration_days)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def unfeature_community(self) -> None:
        """Remove community from featured"""
        self.is_featured = False
        self.featured_until = None
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe community data"""
        result = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "tagline": self.tagline,
            "purpose": {
                "mission": self.purpose.mission_statement,
                "goals": self.purpose.goals,
                "target_audience": self.purpose.target_audience
            },
            "business_address": {
                "country": self.business_address.country,
                "city": self.business_address.city,
                "zip_code": self.business_address.zip_code
            },
            "category": self.category.value,
            "tags": self.tags,
            "branding": {
                "cover_image": self.branding.cover_image,
                "logo": self.branding.logo,
                "primary_color": self.branding.primary_color,
                "secondary_color": self.branding.secondary_color
            },
            "owner": {
                "id": str(self.owner.user_id),
                "display_name": self.owner.display_name,
                "avatar": self.owner.avatar
            },
            "stats": {
                "member_count": self.stats.member_count,
                "post_count": self.stats.post_count,
                "promotion_count": self.stats.promotion_count,
                "total_likes": self.stats.total_likes
            },
            "settings": {
                "visibility": self.settings.visibility.value,
                "is_full": self.is_full(),
                "requires_approval": self.settings.requires_approval
            },
            "is_featured": self.is_featured,
            "created_at": self.created_at.isoformat()
        }

        # Add rules if any
        if self.rules:
            result["rules"] = [
                {
                    "title": rule.rule_title,
                    "description": rule.rule_description
                }
                for rule in sorted(self.rules, key=lambda x: x.display_order)
            ]

        # Add links if any
        if self.links:
            result["links"] = {
                "website": str(self.links.website) if self.links.website else None,
                "instagram": self.links.instagram,
                "twitter": self.links.twitter,
                "youtube": self.links.youtube,
                "discord": self.links.discord
            }

        return result

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
