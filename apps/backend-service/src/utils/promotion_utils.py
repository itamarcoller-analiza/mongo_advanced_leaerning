"""
Promotion utility functions for converting models to response schemas
"""

from fastapi import Request

from src.schemas.promotion import *
from shared.models.promotion import Promotion


def get_supplier_id_from_request(request: Request) -> str:
    """Extract supplier ID from JWT token (placeholder)"""
    # TODO: Implement proper JWT authentication
    return request.headers.get("X-Supplier-ID", "test_supplier_id")


def get_admin_id_from_request(request: Request) -> tuple:
    """Extract admin ID and type from JWT token (placeholder)"""
    # TODO: Implement proper JWT authentication
    admin_id = request.headers.get("X-Admin-ID", "test_admin_id")
    admin_type = request.headers.get("X-Admin-Type", "admin")
    return admin_id, admin_type


def promotion_to_response(promotion: Promotion) -> PromotionResponse:
    """Convert Promotion model to full response schema"""
    return PromotionResponse(
        id=str(promotion.id),
        type=promotion.promotion_type.value,
        status=promotion.status.value,
        version=promotion.version,
        title=promotion.title,
        description=promotion.description,
        banner_image=promotion.banner_image,
        supplier=SupplierInfoResponse(
            id=str(promotion.supplier.supplier_id),
            business_name=promotion.supplier.business_name,
            logo=promotion.supplier.logo
        ),
        products=[
            PromotionProductResponse(
                product_snapshot=ProductSnapshotResponse(
                    product_id=str(p.product_snapshot.product_id),
                    name=p.product_snapshot.product_name,
                    slug=p.product_snapshot.product_slug,
                    image=p.product_snapshot.product_image,
                    original_price_cents=p.product_snapshot.original_price_cents,
                    currency=p.product_snapshot.currency,
                    variant_name=p.product_snapshot.variant_name
                ),
                discount_percent=p.discount_percent,
                discounted_price_cents=p.discounted_price_cents,
                final_price=p.discounted_price_cents / 100,
                current_status=p.current_status,
                price_discrepancy=p.price_discrepancy
            )
            for p in promotion.products
        ],
        visibility=VisibilityResponse(
            type=promotion.visibility.type.value,
            community_ids=[str(cid) for cid in promotion.visibility.community_ids],
            is_global=promotion.visibility.is_global,
            community_count=promotion.visibility.community_count
        ),
        schedule=ScheduleResponse(
            start_date=promotion.schedule.start_date,
            end_date=promotion.schedule.end_date,
            timezone=promotion.schedule.timezone
        ),
        stats=StatsResponse(
            impressions=promotion.stats.impressions,
            clicks=promotion.stats.clicks,
            conversions=promotion.stats.conversions,
            revenue_cents=promotion.stats.revenue_cents,
            click_through_rate=promotion.stats.click_through_rate,
            conversion_rate=promotion.stats.conversion_rate
        ),
        approval=ApprovalInfoResponse(
            global_approval=ApprovalRecordResponse(
                status=promotion.approval.global_approval.status.value,
                reviewer_id=str(promotion.approval.global_approval.reviewer_id) if promotion.approval.global_approval.reviewer_id else None,
                reviewer_type=promotion.approval.global_approval.reviewer_type,
                reviewed_at=promotion.approval.global_approval.reviewed_at,
                notes=promotion.approval.global_approval.notes
            ) if promotion.approval.global_approval else None,
            community_approvals={
                cid: ApprovalRecordResponse(
                    status=record.status.value,
                    reviewer_id=str(record.reviewer_id) if record.reviewer_id else None,
                    reviewer_type=record.reviewer_type,
                    reviewed_at=record.reviewed_at,
                    notes=record.notes
                )
                for cid, record in promotion.approval.community_approvals.items()
            },
            pending_approvals=promotion.approval.get_pending_approvals(promotion.visibility)
        ),
        rejection_history=[
            RejectionRecordResponse(
                scope=r.scope,
                reason=r.reason,
                reviewer_id=str(r.reviewer_id),
                reviewer_type=r.reviewer_type,
                rejected_at=r.rejected_at
            )
            for r in promotion.rejection_history
        ],
        is_auto_generated=promotion.is_auto_generated,
        is_sent=promotion.is_sent,
        first_activated_at=promotion.first_activated_at,
        paused_at=promotion.paused_at,
        cancellation_reason=promotion.cancellation_reason,
        deleted_at=promotion.deleted_at,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at
    )


def promotion_to_list_item(promotion: Promotion) -> PromotionListItemResponse:
    """Convert Promotion to list item response"""
    return PromotionListItemResponse(
        id=str(promotion.id),
        type=promotion.promotion_type.value,
        status=promotion.status.value,
        title=promotion.title,
        supplier_name=promotion.supplier.business_name,
        product_count=len(promotion.products),
        visibility_type=promotion.visibility.type.value,
        start_date=promotion.schedule.start_date,
        end_date=promotion.schedule.end_date,
        is_sent=promotion.is_sent,
        impressions=promotion.stats.impressions,
        conversions=promotion.stats.conversions,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at
    )


def promotion_to_feed_response(promotion: Promotion) -> FeedPromotionResponse:
    """Convert Promotion to feed response for public display"""
    savings = promotion.calculate_savings()
    return FeedPromotionResponse(
        id=str(promotion.id),
        type=promotion.promotion_type.value,
        title=promotion.title,
        description=promotion.description,
        banner_image=promotion.banner_image,
        supplier=SupplierInfoResponse(
            id=str(promotion.supplier.supplier_id),
            business_name=promotion.supplier.business_name,
            logo=promotion.supplier.logo
        ),
        products=[
            FeedProductResponse(
                id=str(p.product_snapshot.product_id),
                name=p.product_snapshot.product_name,
                image=p.product_snapshot.product_image,
                original_price=p.product_snapshot.original_price_cents / 100,
                final_price=p.discounted_price_cents / 100,
                discount_percent=p.discount_percent
            )
            for p in promotion.products
        ],
        ends_at=promotion.schedule.end_date,
        savings_percent=savings["savings_percent"]
    )


def promotion_to_pending_item(promotion: Promotion) -> PendingApprovalItemResponse:
    """Convert Promotion to pending approval item response"""
    return PendingApprovalItemResponse(
        id=str(promotion.id),
        type=promotion.promotion_type.value,
        title=promotion.title,
        supplier=SupplierInfoResponse(
            id=str(promotion.supplier.supplier_id),
            business_name=promotion.supplier.business_name,
            logo=promotion.supplier.logo
        ),
        visibility_type=promotion.visibility.type.value,
        community_ids=[str(cid) for cid in promotion.visibility.community_ids],
        pending_approvals=promotion.approval.get_pending_approvals(promotion.visibility),
        submitted_at=promotion.updated_at,
        start_date=promotion.schedule.start_date
    )
