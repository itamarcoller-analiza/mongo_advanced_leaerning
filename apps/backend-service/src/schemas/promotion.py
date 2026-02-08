"""
Promotion Response Schemas - All response schemas for promotion endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


# ============================================================================
# Response Schemas
# ============================================================================

class SupplierInfoResponse(BaseModel):
    """Supplier info in promotion response"""
    id: str
    business_name: str
    logo: Optional[str]


class ProductSnapshotResponse(BaseModel):
    """Product snapshot in promotion response"""
    product_id: str
    name: str
    slug: str
    image: str
    original_price_cents: int
    currency: str
    variant_name: Optional[str]


class PromotionProductResponse(BaseModel):
    """Product in promotion response"""
    product_snapshot: ProductSnapshotResponse
    discount_percent: int
    discounted_price_cents: int
    final_price: float
    current_status: str
    price_discrepancy: bool


class VisibilityResponse(BaseModel):
    """Visibility settings response"""
    type: str
    community_ids: List[str]
    is_global: bool
    community_count: int


class ScheduleResponse(BaseModel):
    """Schedule response"""
    start_date: datetime
    end_date: datetime
    timezone: str


class StatsResponse(BaseModel):
    """Promotion stats response"""
    impressions: int
    clicks: int
    conversions: int
    revenue_cents: int
    click_through_rate: float
    conversion_rate: float


class ApprovalRecordResponse(BaseModel):
    """Single approval record response"""
    status: str
    reviewer_id: Optional[str]
    reviewer_type: Optional[str]
    reviewed_at: Optional[datetime]
    notes: Optional[str]


class ApprovalInfoResponse(BaseModel):
    """Approval info response"""
    global_approval: Optional[ApprovalRecordResponse]
    community_approvals: Dict[str, ApprovalRecordResponse]
    pending_approvals: List[str]


class RejectionRecordResponse(BaseModel):
    """Rejection record response"""
    scope: str
    reason: str
    reviewer_id: str
    reviewer_type: str
    rejected_at: datetime


class PromotionResponse(BaseModel):
    """Full promotion response"""
    id: str
    type: str
    status: str
    version: int
    title: str
    description: str
    banner_image: str
    supplier: SupplierInfoResponse
    products: List[PromotionProductResponse]
    visibility: VisibilityResponse
    schedule: ScheduleResponse
    stats: StatsResponse
    approval: ApprovalInfoResponse
    rejection_history: List[RejectionRecordResponse]
    is_auto_generated: bool
    is_sent: bool
    first_activated_at: Optional[datetime]
    paused_at: Optional[datetime]
    cancellation_reason: Optional[str]
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PromotionListItemResponse(BaseModel):
    """Promotion list item (summary)"""
    id: str
    type: str
    status: str
    title: str
    supplier_name: str
    product_count: int
    visibility_type: str
    start_date: datetime
    end_date: datetime
    is_sent: bool
    impressions: int
    conversions: int
    created_at: datetime
    updated_at: datetime


class PaginationResponse(BaseModel):
    """Pagination metadata"""
    page: int
    limit: int
    total: int
    total_pages: int
    next_cursor: Optional[str] = None
    has_more: bool


class PromotionListResponse(BaseModel):
    """Promotion list response"""
    items: List[PromotionListItemResponse]
    pagination: PaginationResponse


# ============================================================================
# Public Feed Response Schemas
# ============================================================================

class FeedProductResponse(BaseModel):
    """Product in feed promotion response"""
    id: str
    name: str
    image: str
    original_price: float
    final_price: float
    discount_percent: int


class FeedPromotionResponse(BaseModel):
    """Promotion for feed display"""
    id: str
    type: str
    title: str
    description: str
    banner_image: str
    supplier: SupplierInfoResponse
    products: List[FeedProductResponse]
    ends_at: datetime
    savings_percent: int


class FeedPromotionListResponse(BaseModel):
    """Feed promotion list response"""
    items: List[FeedPromotionResponse]
    cursor: Optional[str]
    has_more: bool


# ============================================================================
# Admin Response Schemas
# ============================================================================

class PendingApprovalItemResponse(BaseModel):
    """Pending approval item for admin view"""
    id: str
    type: str
    title: str
    supplier: SupplierInfoResponse
    visibility_type: str
    community_ids: List[str]
    pending_approvals: List[str]
    submitted_at: datetime
    start_date: datetime


class PendingApprovalListResponse(BaseModel):
    """Pending approval list response"""
    items: List[PendingApprovalItemResponse]
    pagination: PaginationResponse


# ============================================================================
# Error Response Schemas
# ============================================================================

class ErrorDetailResponse(BaseModel):
    """Error detail response"""
    code: str
    message: str
    details: Optional[Dict] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: ErrorDetailResponse


"""
Promotion Request Schemas - All request body schemas for promotion endpoints
"""



# ============================================================================
# Embedded Request Schemas
# ============================================================================

class ProductInPromotionRequest(BaseModel):
    """Product to include in promotion"""
    product_id: str = Field(..., description="Product ID")
    discount_percent: int = Field(default=0, ge=0, le=100, description="Discount percentage")


class VisibilityRequest(BaseModel):
    """Promotion visibility settings"""
    type: str = Field(..., description="Visibility type: global, communities, or both")
    community_ids: List[str] = Field(default_factory=list, description="Target community IDs")


class ScheduleRequest(BaseModel):
    """Promotion schedule"""
    start_date: datetime = Field(..., description="Start date (UTC)")
    end_date: datetime = Field(..., description="End date (UTC)")
    timezone: str = Field(default="UTC", description="Display timezone")


class TermsRequest(BaseModel):
    """Promotion terms and conditions"""
    terms_text: str = Field(..., max_length=2000, description="Terms and conditions text")
    restrictions: List[str] = Field(default_factory=list, description="List of restrictions")
    min_purchase_amount_cents: Optional[int] = Field(None, ge=0, description="Minimum purchase amount")
    max_uses_per_user: Optional[int] = Field(None, ge=1, description="Max uses per customer")


# ============================================================================
# Base Request Schemas
# ============================================================================

class PromotionIdRequest(BaseModel):
    """Base request with promotion ID only"""
    promotion_id: str = Field(..., description="Promotion ID")


class PromotionIdVersionRequest(BaseModel):
    """Base request with promotion ID and version for optimistic locking"""
    promotion_id: str = Field(..., description="Promotion ID")
    version: int = Field(..., ge=1, description="Version for optimistic locking")


# ============================================================================
# CRUD Request Schemas
# ============================================================================

class CreatePromotionRequest(BaseModel):
    """Create promotion request"""
    type: str = Field(..., description="Promotion type: campaign, single, or default")
    title: str = Field(..., min_length=5, max_length=200, description="Promotion title")
    description: str = Field(..., min_length=10, max_length=2000, description="Promotion description")
    banner_image: str = Field(..., description="Banner image URL")
    products: List[ProductInPromotionRequest] = Field(..., min_length=1, max_length=3, description="Products in promotion")
    visibility: VisibilityRequest = Field(..., description="Visibility settings")
    schedule: ScheduleRequest = Field(..., description="Schedule settings")
    terms: Optional[TermsRequest] = Field(None, description="Terms and conditions")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for duplicate prevention")


class GetPromotionRequest(PromotionIdRequest):
    """Get promotion request"""
    pass


class UpdatePromotionRequest(PromotionIdVersionRequest):
    """Update promotion request (partial update)"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    banner_image: Optional[str] = None
    products: Optional[List[ProductInPromotionRequest]] = None
    visibility: Optional[VisibilityRequest] = None
    schedule: Optional[ScheduleRequest] = None
    terms: Optional[TermsRequest] = None


class DeletePromotionRequest(PromotionIdVersionRequest):
    """Delete promotion request"""
    pass


# ============================================================================
# Lifecycle Request Schemas
# ============================================================================

class SubmitForApprovalRequest(PromotionIdVersionRequest):
    """Submit promotion for approval"""
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


class SchedulePromotionRequest(PromotionIdVersionRequest):
    """Schedule promotion request"""
    schedule: ScheduleRequest = Field(..., description="Schedule settings")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


class PausePromotionRequest(PromotionIdVersionRequest):
    """Pause promotion request"""
    reason: str = Field(..., min_length=5, max_length=500, description="Pause reason")


class ResumePromotionRequest(PromotionIdVersionRequest):
    """Resume promotion request"""
    pass


class CancelPromotionRequest(PromotionIdVersionRequest):
    """Cancel promotion request"""
    reason: str = Field(..., min_length=5, max_length=500, description="Cancellation reason")


class EndPromotionRequest(PromotionIdVersionRequest):
    """End promotion early request"""
    pass


# ============================================================================
# Admin Request Schemas
# ============================================================================

class ApprovePromotionRequest(PromotionIdVersionRequest):
    """Approve promotion request"""
    approval_scope: str = Field(..., description="Approval scope: global or community")
    community_id: Optional[str] = Field(None, description="Community ID (required for community scope)")
    notes: Optional[str] = Field(None, max_length=500, description="Approval notes")


class RejectPromotionRequest(PromotionIdVersionRequest):
    """Reject promotion request"""
    rejection_scope: str = Field(..., description="Rejection scope: global or community")
    community_id: Optional[str] = Field(None, description="Community ID (required for community scope)")
    reason: str = Field(..., min_length=10, max_length=1000, description="Rejection reason")


# ============================================================================
# Feed Request Schemas
# ============================================================================

class GlobalFeedRequest(BaseModel):
    """Request for global feed promotions"""
    cursor: Optional[str] = Field(None, description="Pagination cursor")


class CommunityFeedRequest(BaseModel):
    """Request for community feed promotions"""
    community_id: str = Field(..., description="Community ID")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
