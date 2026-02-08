"""
Community Schemas - Request and Response models for Community API
"""

from pydantic import BaseModel, Field,  field_validator
from typing import Optional, List


# ============================================================
# Embedded Schema Requests
# ============================================================

class PurposeRequest(BaseModel):
    """Community purpose and mission"""
    mission_statement: str = Field(..., min_length=10, max_length=1000, description="Mission statement")
    goals: Optional[List[str]] = Field(None, max_length=10, description="Community goals")
    target_audience: Optional[str] = Field(None, max_length=500, description="Target audience")


class BusinessAddressRequest(BaseModel):
    """Business address"""
    country: str = Field(..., min_length=2, max_length=2, description="ISO country code")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    zip_code: str = Field(..., min_length=1, max_length=20, description="Postal code")

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        return v.upper()


class BrandingRequest(BaseModel):
    """Visual branding"""
    cover_image: str = Field(..., description="Cover image URL")
    logo: Optional[str] = Field(None, description="Logo URL")
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Primary color hex")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Secondary color hex")


class SettingsRequest(BaseModel):
    """Community settings"""
    visibility: str = Field(default="public", description="public or private")
    requires_approval: bool = Field(default=False, description="Require approval to join")
    allow_member_posts: bool = Field(default=False, description="Allow members to post")
    moderate_posts: bool = Field(default=True, description="Posts require approval")
    max_members: Optional[int] = Field(None, ge=1, description="Maximum members")
    min_age: Optional[int] = Field(None, ge=13, le=100, description="Minimum age")
    allowed_countries: Optional[List[str]] = Field(None, description="Allowed country codes")
    blocked_countries: Optional[List[str]] = Field(None, description="Blocked country codes")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in ["public", "private"]:
            raise ValueError("Visibility must be 'public' or 'private'")
        return v


class RuleRequest(BaseModel):
    """Community rule"""
    rule_title: str = Field(..., max_length=100, description="Rule title")
    rule_description: str = Field(..., max_length=1000, description="Rule description")
    display_order: int = Field(default=0, description="Display order")


class LinksRequest(BaseModel):
    """External links"""
    website: Optional[str] = Field(None, description="Website URL")
    instagram: Optional[str] = Field(None, description="Instagram handle")
    twitter: Optional[str] = Field(None, description="Twitter handle")
    youtube: Optional[str] = Field(None, description="YouTube channel")
    discord: Optional[str] = Field(None, description="Discord invite")


# ============================================================
# Community CRUD Requests
# ============================================================

class CreateCommunityRequest(BaseModel):
    """Create a new community"""
    name: str = Field(..., min_length=2, max_length=100, description="Community name")
    slug: str = Field(..., min_length=2, max_length=150, description="URL-friendly slug")
    description: str = Field(..., min_length=10, max_length=2000, description="Description")
    tagline: Optional[str] = Field(None, max_length=200, description="Short tagline")
    category: str = Field(..., description="Category enum value")
    tags: Optional[List[str]] = Field(None, max_length=20, description="Additional tags")
    purpose: PurposeRequest = Field(..., description="Purpose and mission")
    business_address: BusinessAddressRequest = Field(..., description="Business address")
    branding: BrandingRequest = Field(..., description="Visual branding")
    settings: Optional[SettingsRequest] = Field(None, description="Community settings")
    rules: Optional[List[RuleRequest]] = Field(None, max_length=20, description="Community rules")
    links: Optional[LinksRequest] = Field(None, description="External links")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        slug = v.lower().strip()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError("Slug can only contain letters, numbers, hyphens, underscores")
        return slug


class GetCommunityRequest(BaseModel):
    """Get community by ID"""
    community_id: str = Field(..., description="Community ID")


class GetCommunityBySlugRequest(BaseModel):
    """Get community by slug"""
    slug: str = Field(..., description="Community slug")


class DiscoverCommunitiesRequest(BaseModel):
    """Discover/list communities"""
    category: Optional[str] = Field(None, description="Filter by category")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    country: Optional[str] = Field(None, description="Filter by country")
    city: Optional[str] = Field(None, description="Filter by city")
    is_featured: Optional[bool] = Field(None, description="Only featured communities")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Results per page")


class UpdateCommunityRequest(BaseModel):
    """Update community"""
    community_id: str = Field(..., description="Community ID")
    expected_version: int = Field(..., ge=1, description="Expected version for optimistic locking")
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Community name")
    slug: Optional[str] = Field(None, min_length=2, max_length=150, description="URL-friendly slug")
    description: Optional[str] = Field(None, min_length=10, max_length=2000, description="Description")
    tagline: Optional[str] = Field(None, max_length=200, description="Short tagline")
    category: Optional[str] = Field(None, description="Category enum value")
    tags: Optional[List[str]] = Field(None, max_length=20, description="Additional tags")
    purpose: Optional[PurposeRequest] = Field(None, description="Purpose and mission")
    branding: Optional[BrandingRequest] = Field(None, description="Visual branding")
    settings: Optional[SettingsRequest] = Field(None, description="Community settings")
    rules: Optional[List[RuleRequest]] = Field(None, max_length=20, description="Community rules")
    links: Optional[LinksRequest] = Field(None, description="External links")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        slug = v.lower().strip()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError("Slug can only contain letters, numbers, hyphens, underscores")
        return slug


class DeleteCommunityRequest(BaseModel):
    """Soft delete community"""
    community_id: str = Field(..., description="Community ID")
    expected_version: int = Field(..., ge=1, description="Expected version")


class ArchiveCommunityRequest(BaseModel):
    """Archive/unarchive community"""
    community_id: str = Field(..., description="Community ID")
    expected_version: int = Field(..., ge=1, description="Expected version")


# ============================================================
# Membership Requests
# ============================================================

class JoinCommunityRequest(BaseModel):
    """Join a community"""
    community_id: str = Field(..., description="Community ID")


class LeaveCommunityRequest(BaseModel):
    """Leave a community"""
    community_id: str = Field(..., description="Community ID")


class CheckMembershipRequest(BaseModel):
    """Check membership status"""
    community_id: str = Field(..., description="Community ID")


class ListMembersRequest(BaseModel):
    """List community members"""
    community_id: str = Field(..., description="Community ID")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Results per page")


class RemoveMemberRequest(BaseModel):
    """Remove member from community"""
    community_id: str = Field(..., description="Community ID")
    user_id: str = Field(..., description="User ID to remove")
    expected_version: int = Field(..., ge=1, description="Expected version")


# ============================================================
# Admin Requests
# ============================================================

class SuspendCommunityRequest(BaseModel):
    """Suspend community (admin only)"""
    community_id: str = Field(..., description="Community ID")
    reason: str = Field(..., min_length=5, max_length=1000, description="Suspension reason")
    expected_version: int = Field(..., ge=1, description="Expected version")


class UnsuspendCommunityRequest(BaseModel):
    """Unsuspend community (admin only)"""
    community_id: str = Field(..., description="Community ID")
    reason: str = Field(..., min_length=5, max_length=1000, description="Unsuspension reason")
    expected_version: int = Field(..., ge=1, description="Expected version")


class FeatureCommunityRequest(BaseModel):
    """Feature community (admin only)"""
    community_id: str = Field(..., description="Community ID")
    duration_days: int = Field(default=7, ge=1, le=90, description="Days to feature")


class UnfeatureCommunityRequest(BaseModel):
    """Unfeature community (admin only)"""
    community_id: str = Field(..., description="Community ID")


# ============================================================
# Response Schemas
# ============================================================

class OwnerResponse(BaseModel):
    """Owner information in response"""
    id: str
    display_name: str
    avatar: str


class StatsResponse(BaseModel):
    """Community statistics"""
    member_count: int
    post_count: int
    promotion_count: int
    total_likes: int


class SettingsResponse(BaseModel):
    """Community settings in response"""
    visibility: str
    is_full: bool
    requires_approval: bool


class PurposeResponse(BaseModel):
    """Purpose in response"""
    mission: str
    goals: List[str]
    target_audience: Optional[str] = None


class BrandingResponse(BaseModel):
    """Branding in response"""
    cover_image: str
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None


class BusinessAddressResponse(BaseModel):
    """Business address in response"""
    country: str
    city: str
    zip_code: str


class RuleResponse(BaseModel):
    """Rule in response"""
    title: str
    description: str


class LinksResponse(BaseModel):
    """Links in response"""
    website: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    discord: Optional[str] = None


class CommunityResponse(BaseModel):
    """Full community response"""
    id: str
    name: str
    slug: str
    description: str
    tagline: Optional[str] = None
    category: str
    tags: List[str]
    purpose: PurposeResponse
    business_address: BusinessAddressResponse
    branding: BrandingResponse
    owner: OwnerResponse
    stats: StatsResponse
    settings: SettingsResponse
    rules: Optional[List[RuleResponse]] = None
    links: Optional[LinksResponse] = None
    status: str
    is_featured: bool
    version: int
    created_at: str
    updated_at: str


class CommunityListItemResponse(BaseModel):
    """Community item in list response"""
    id: str
    name: str
    slug: str
    tagline: Optional[str] = None
    category: str
    owner: OwnerResponse
    stats: StatsResponse
    settings: SettingsResponse
    branding: BrandingResponse
    is_featured: bool
    created_at: str


class PaginatedCommunitiesResponse(BaseModel):
    """Paginated list of communities"""
    communities: List[CommunityListItemResponse]
    next_cursor: Optional[str] = None
    has_more: bool


class JoinResultResponse(BaseModel):
    """Result of join attempt"""
    success: bool
    community_id: str
    member_count: Optional[int] = None
    already_member: Optional[bool] = None
    requires_approval: Optional[bool] = None
    request_id: Optional[str] = None
    message: Optional[str] = None


class MembershipResponse(BaseModel):
    """Membership check response"""
    community_id: str
    is_member: bool
    is_owner: bool


class MemberResponse(BaseModel):
    """Member in list"""
    user_id: str
    joined_at: Optional[str] = None


class PaginatedMembersResponse(BaseModel):
    """Paginated members list"""
    members: List[MemberResponse]
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: int


