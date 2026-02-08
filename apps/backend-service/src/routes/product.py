"""
Product Routes - Supplier endpoints for product management
"""

from fastapi import APIRouter, HTTPException, Request, status, Query
from typing import Optional, List

from src.schemas.product import *
from src.services.product import ProductService


router = APIRouter(prefix="/products", tags=["Products - Supplier"])
product_service = ProductService()


# Helper to extract supplier_id from JWT (simplified - implement proper JWT auth)
def get_supplier_id_from_request(request: Request) -> str:
    """Extract supplier ID from JWT token (placeholder)"""
    # TODO: Implement proper JWT authentication
    # For now, return a test supplier ID
    return request.headers.get("X-Supplier-ID", "test_supplier_id")


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def create_product(request_data: CreateProductRequest, request: Request):
    """Create a new product (draft status)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        # Convert request to dict
        product_data = request_data.model_dump()

        result = await product_service.create_product(supplier_id, product_data)

        return ProductResponse(
            id=result["id"],
            supplier_id=result["supplier_id"],
            supplier_info=None,
            name=result["name"],
            slug=result["slug"],
            short_description=None,
            category="",
            condition="new",
            status=result["status"],
            is_available=result["is_available"],
            base_price_cents=0,
            currency="USD",
            images=[],
            tags=[],
            stock_quantity=0,
            variant_count=0,
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            published_at=None,
            deleted_at=None
        )

    except ValueError as e:
        error_msg = str(e)

        # Handle specific error types
        if "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PRODUCT_NAME_EXISTS" if "name" in error_msg else "SKU_CONFLICT", "message": error_msg}
            )
        elif "not active" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "SUPPLIER_NOT_ACTIVE", "message": error_msg}
            )
        elif "Maximum product limit" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "MAX_PRODUCTS_REACHED", "message": error_msg}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": error_msg}
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred while creating the product"}
        )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    responses={
        404: {"model": ErrorResponse}
    }
)
async def get_product(product_id: str, request: Request):
    """Get a single product (own products only)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        product = await product_service.get_product(product_id, supplier_id)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],  # Simplified
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred"}
        )


@router.get(
    "",
    response_model=ProductListResponse,
    responses={
        400: {"model": ErrorResponse}
    }
)
async def list_products(
    request: Request,
    page_size: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Comma-separated status values"),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """List supplier's products (paginated)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        # Parse status filter
        status_filter = status.split(",") if status else None

        result = await product_service.list_products(
            supplier_id=supplier_id,
            page_size=page_size,
            cursor=cursor,
            status_filter=status_filter,
            category_filter=category,
            search=search
        )

        return ProductListResponse(
            products=[
                ProductListItemResponse(**p) for p in result["products"]
            ],
            pagination=PaginationResponse(**result["pagination"])
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred"}
        )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def update_product(product_id: str, request_data: UpdateProductRequest, request: Request):
    """Update product (partial update)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        # Convert to dict and filter None values
        updates = {k: v for k, v in request_data.dict().items() if v is not None}

        product = await product_service.update_product(product_id, supplier_id, updates)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        error_msg = str(e)

        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": error_msg}
            )
        elif "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PRODUCT_NAME_EXISTS", "message": error_msg}
            )
        elif "Cannot update deleted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "CANNOT_UPDATE_DELETED", "message": error_msg}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": error_msg}
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred"}
        )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse}
    }
)
async def delete_product(product_id: str, request: Request):
    """Soft delete product"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        await product_service.delete_product(product_id, supplier_id)

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred"}
        )


# Lifecycle Endpoints
@router.post(
    "/{product_id}/publish",
    response_model=ProductResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse}
    }
)
async def publish_product(product_id: str, request: Request):
    """Publish product (draft -> active)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        product = await product_service.publish_product(product_id, supplier_id)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        error_msg = str(e)

        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": error_msg}
            )
        elif "Cannot publish" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_STATUS_TRANSITION", "message": error_msg}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": error_msg}
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "An error occurred"}
        )


@router.post(
    "/{product_id}/discontinue",
    response_model=ProductResponse
)
async def discontinue_product(product_id: str, request: Request):
    """Discontinue product (active/out_of_stock -> discontinued)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        product = await product_service.discontinue_product(product_id, supplier_id)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": error_msg})
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATUS_TRANSITION", "message": error_msg})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.post(
    "/{product_id}/mark-out-of-stock",
    response_model=ProductResponse
)
async def mark_out_of_stock(product_id: str, request: Request):
    """Mark product out of stock (active -> out_of_stock)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        product = await product_service.mark_out_of_stock(product_id, supplier_id)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": error_msg})
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATUS_TRANSITION", "message": error_msg})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.post(
    "/{product_id}/restore",
    response_model=ProductResponse
)
async def restore_product(product_id: str, request: Request):
    """Restore deleted product (deleted -> draft)"""
    try:
        supplier_id = get_supplier_id_from_request(request)

        product = await product_service.restore_product(product_id, supplier_id)

        return ProductResponse(
            id=str(product.id),
            supplier_id=str(product.supplier_id),
            supplier_info=None,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            category=product.category.value,
            condition=product.condition.value,
            status=product.status.value,
            is_available=product.is_available,
            base_price_cents=product.base_price_cents,
            currency=product.currency,
            images=[],
            tags=product.metadata.tags,
            stock_quantity=product.get_total_inventory(),
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
            published_at=product.published_at,
            deleted_at=product.deleted_at
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": error_msg})
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATUS_TRANSITION", "message": error_msg})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})
