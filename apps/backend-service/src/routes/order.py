"""
Order Routes - User endpoints for order management
"""

from fastapi import APIRouter, HTTPException, Request, status, Query
from typing import Optional

from src.schemas.order import *
from src.services.order import OrderService
from src.utils.order_utils import (
    get_user_id_from_request, get_idempotency_key, get_client_ip,
    order_to_response, order_to_list_item
)


router = APIRouter(prefix="/orders", tags=["Orders"])
order_service = OrderService()


# ============================================================================
# Create Order
# ============================================================================

@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def create_order(request_data: CreateOrderRequest, request: Request):
    """
    Create a new pending order.

    Requires X-Idempotency-Key header for duplicate prevention.
    """
    try:
        user_id = get_user_id_from_request(request)
        idempotency_key = get_idempotency_key(request)
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")

        order = await order_service.create_order(
            user_id=user_id,
            order_data=request_data.model_dump(),
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return order_to_response(order)

    except ValueError as e:
        error_msg = str(e)
        if "Idempotency" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_IDEMPOTENCY_KEY", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "RESOURCE_NOT_FOUND", "message": error_msg}}
            )
        elif "Insufficient stock" in error_msg or "not available" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INSUFFICIENT_STOCK", "message": error_msg}}
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


# ============================================================================
# List Orders
# ============================================================================

@router.get(
    "/list",
    response_model=OrderListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def list_orders(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Number of orders per page"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    status: Optional[str] = Query(None, description="Filter by status (comma-separated)")
):
    """List user's orders with cursor pagination"""
    try:
        user_id = get_user_id_from_request(request)
        status_filter = status.split(",") if status else None

        result = await order_service.list_user_orders(
            user_id=user_id,
            page_size=limit,
            cursor=cursor,
            status_filter=status_filter
        )

        return OrderListResponse(
            orders=[order_to_list_item(o) for o in result["orders"]],
            pagination=PaginationResponse(**result["pagination"])
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Get Order by ID
# ============================================================================

@router.post(
    "/get",
    response_model=OrderResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_order(request_data: GetOrderRequest, request: Request):
    """Get order by ID"""
    try:
        user_id = get_user_id_from_request(request)
        order = await order_service.get_order(request_data.order_id, user_id)
        return order_to_response(order)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Get Order by Order Number
# ============================================================================

@router.post(
    "/get-by-number",
    response_model=OrderResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_order_by_number(request_data: GetOrderByNumberRequest, request: Request):
    """Get order by order number (e.g., ORD-20241215-ABC1)"""
    try:
        user_id = get_user_id_from_request(request)
        order = await order_service.get_order_by_number(request_data.order_number, user_id)
        return order_to_response(order)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Complete Order
# ============================================================================

@router.post(
    "/complete",
    response_model=OrderResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def complete_order(request_data: CompleteOrderRequest, request: Request):
    """
    Complete order (authorize payment and reserve inventory).

    Requires X-Idempotency-Key header.
    """
    try:
        user_id = get_user_id_from_request(request)
        idempotency_key = get_idempotency_key(request)

        order = await order_service.complete_order(
            order_id=request_data.order_id,
            user_id=user_id,
            idempotency_key=idempotency_key
        )
        return order_to_response(order)

    except ValueError as e:
        error_msg = str(e)
        if "Idempotency" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_IDEMPOTENCY_KEY", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ORDER_NOT_FOUND", "message": error_msg}}
            )
        elif "cannot be completed" in error_msg.lower() or "already been processed" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_ORDER_STATE", "message": error_msg}}
            )
        elif "Insufficient stock" in error_msg or "no longer available" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INSUFFICIENT_STOCK", "message": error_msg}}
            )
        elif "changed significantly" in error_msg or "Price" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "PRICE_DRIFT", "message": error_msg}}
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


# ============================================================================
# Update Order
# ============================================================================

@router.post(
    "/update",
    response_model=OrderResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def update_order(request_data: UpdateOrderRequest, request: Request):
    """
    Update a pending order.

    Only PENDING orders with PENDING payment can be modified.
    """
    try:
        user_id = get_user_id_from_request(request)
        updates = {k: v for k, v in request_data.model_dump().items() if v is not None and k != "order_id"}

        order = await order_service.modify_order(
            order_id=request_data.order_id,
            user_id=user_id,
            updates=updates
        )
        return order_to_response(order)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ORDER_NOT_FOUND", "message": error_msg}}
            )
        elif "pending" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "ORDER_NOT_MODIFIABLE", "message": error_msg}}
            )
        elif "Insufficient stock" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INSUFFICIENT_STOCK", "message": error_msg}}
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


# ============================================================================
# Cancel Order
# ============================================================================

@router.post(
    "/cancel",
    response_model=OrderResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def cancel_order(request_data: CancelOrderRequest, request: Request):
    """
    Cancel an order.

    Only PENDING or CONFIRMED orders (not yet shipped) can be cancelled.
    """
    try:
        user_id = get_user_id_from_request(request)

        order = await order_service.cancel_order(
            order_id=request_data.order_id,
            user_id=user_id,
            reason=request_data.reason
        )
        return order_to_response(order)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ORDER_NOT_FOUND", "message": error_msg}}
            )
        elif "cannot be cancelled" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "ORDER_NOT_CANCELLABLE", "message": error_msg}}
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
