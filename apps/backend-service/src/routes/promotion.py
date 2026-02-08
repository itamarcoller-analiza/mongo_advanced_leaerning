"""
Promotion Routes - Supplier endpoints for promotion management
"""

from fastapi import APIRouter, HTTPException, Request, status, Query
from typing import Optional

from src.schemas.promotion import *
from src.services.promotion import PromotionService
from src.utils.promotion_utils import *

router = APIRouter(prefix="/promotions", tags=["Promotions"])
promotion_service = PromotionService()


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post(
    "",
    response_model=PromotionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def create_promotion(request_data: CreatePromotionRequest, request: Request):
    """Create a new promotion (draft status)"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion_data = request_data.model_dump()

        promotion = await promotion_service.create_promotion(supplier_id, promotion_data)
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not verified" in error_msg or "not active" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "SUPPLIER_NOT_VERIFIED", "message": error_msg}}
            )
        elif "not found" in error_msg or "not owned" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "PRODUCT_NOT_OWNED_BY_SUPPLIER", "message": error_msg}}
            )
        elif "Default promotions" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "DEFAULT_PROMO_SUPPLIER_CREATE_FORBIDDEN", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/get",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_promotion(request_data: GetPromotionRequest, request: Request):
    """Get a single promotion by ID"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.get_promotion(request_data.promotion_id, supplier_id)
        return promotion_to_response(promotion)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found"}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.get(
    "/list",
    response_model=PromotionListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def list_promotions(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Comma-separated status values"),
    type: Optional[str] = Query(None, description="Promotion type filter"),
    include_deleted: bool = Query(False)
):
    """List supplier's promotions (paginated)"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        status_filter = status.split(",") if status else None

        result = await promotion_service.list_promotions(
            supplier_id=supplier_id,
            page=page,
            limit=limit,
            status_filter=status_filter,
            type_filter=type,
            include_deleted=include_deleted
        )

        return PromotionListResponse(
            items=[promotion_to_list_item(p) for p in result["items"]],
            pagination=PaginationResponse(**result["pagination"])
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/update",
    response_model=PromotionResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def update_promotion(request_data: UpdatePromotionRequest, request: Request):
    """Update promotion (partial update)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        updates = {k: v for k, v in request_data.model_dump().items()
                   if v is not None and k not in ["version", "promotion_id"]}

        promotion = await promotion_service.update_promotion(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version,
            updates=updates
        )

        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}}
            )
        elif "Version conflict" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "Cannot update" in error_msg or "Cannot modify" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse}
    }
)
async def delete_promotion(request_data: DeletePromotionRequest, request: Request):
    """Delete promotion (with restrictions)"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        await promotion_service.delete_promotion(
            request_data.promotion_id,
            supplier_id,
            request_data.version
        )
        return None

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found"}}
            )
        elif "Version conflict" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "Cannot delete" in error_msg:
            if "auto-generated" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "AUTO_GENERATED_PROMO_PROTECTED", "message": error_msg}}
                )
            elif "sent" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": {"code": "CANNOT_DELETE_SENT_PROMOTION", "message": error_msg}}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": {"code": "STATUS_PREVENTS_DELETE", "message": error_msg}}
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "DELETE_FAILED", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Lifecycle Endpoints
# ============================================================================

@router.post(
    "/submit",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
)
async def submit_for_approval(request_data: PromotionIdVersionRequest, request: Request):
    """Submit promotion for approval"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.submit_for_approval(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version
        )
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}})
        elif "Version conflict" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}})
        elif "Only draft" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}})
        else:
            raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}})

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


@router.post(
    "/pause",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
)
async def pause_promotion(request_data: PausePromotionRequest, request: Request):
    """Pause an active promotion"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.pause_promotion(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version,
            reason=request_data.reason
        )
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}})
        elif "Version conflict" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}})
        else:
            raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}})

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


@router.post(
    "/resume",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
)
async def resume_promotion(request_data: PromotionIdVersionRequest, request: Request):
    """Resume a paused promotion"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.resume_promotion(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version
        )
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}})
        elif "Version conflict" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}})
        elif "end date has passed" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "PROMOTION_EXPIRED", "message": error_msg}})
        else:
            raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}})

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


@router.post(
    "/cancel",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
)
async def cancel_promotion(request_data: CancelPromotionRequest, request: Request):
    """Cancel a promotion (soft delete)"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.cancel_promotion(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version,
            reason=request_data.reason
        )
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}})
        elif "Version conflict" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}})
        elif "auto-generated" in error_msg:
            raise HTTPException(status_code=403, detail={"error": {"code": "AUTO_GENERATED_PROMO_PROTECTED", "message": error_msg}})
        else:
            raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}})

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


@router.post(
    "/end",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
)
async def end_promotion(request_data: PromotionIdVersionRequest, request: Request):
    """End a promotion early"""
    try:
        supplier_id = get_supplier_id_from_request(request)
        promotion = await promotion_service.end_promotion(
            promotion_id=request_data.promotion_id,
            supplier_id=supplier_id,
            version=request_data.version
        )
        return promotion_to_response(promotion)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": error_msg}})
        elif "Version conflict" in error_msg:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}})
        else:
            raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}})

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


# ============================================================================
# Public Feed Endpoints
# ============================================================================

@router.post(
    "/global",
    response_model=FeedPromotionListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def get_global_feed_promotions(
    request_data: GlobalFeedRequest,
    limit: int = Query(20, ge=1, le=50)
):
    """Get active promotions for global feed"""
    try:
        result = await promotion_service.get_global_feed_promotions(
            limit=limit,
            cursor=request_data.cursor
        )

        return FeedPromotionListResponse(
            items=[promotion_to_feed_response(p) for p in result["items"]],
            cursor=result["cursor"],
            has_more=result["has_more"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})


@router.post(
    "/community",
    response_model=FeedPromotionListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def get_community_feed_promotions(
    request_data: CommunityFeedRequest,
    limit: int = Query(20, ge=1, le=50)
):
    """Get active promotions for a community feed"""
    try:
        result = await promotion_service.get_community_feed_promotions(
            community_id=request_data.community_id,
            limit=limit,
            cursor=request_data.cursor
        )

        return FeedPromotionListResponse(
            items=[promotion_to_feed_response(p) for p in result["items"]],
            cursor=result["cursor"],
            has_more=result["has_more"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}})
