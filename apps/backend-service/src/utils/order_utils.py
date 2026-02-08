"""
Order utility functions for converting models to response schemas
"""

from fastapi import Request

from src.schemas.order import (
    OrderResponse, OrderListItemResponse, OrderItemResponse,
    ProductSnapshotResponse, OrderTotalsResponse, ShippingAddressResponse,
    BillingAddressResponse, PaymentInfoResponse, TimelineEventResponse,
    OrderAttributionResponse
)
from shared.models.order import Order


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from JWT token (placeholder)"""
    # TODO: Implement proper JWT authentication
    return request.headers.get("X-User-ID", "test_user_id")


def get_idempotency_key(request: Request) -> str:
    """Extract idempotency key from request header"""
    key = request.headers.get("X-Idempotency-Key")
    if not key:
        raise ValueError("X-Idempotency-Key header is required")
    return key


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def order_to_response(order: Order) -> OrderResponse:
    """Convert Order model to full response schema"""
    return OrderResponse(
        id=str(order.id),
        order_number=order.order_number,
        status=order.status.value,
        items=[
            OrderItemResponse(
                item_id=item.item_id,
                product_snapshot=ProductSnapshotResponse(
                    product_id=str(item.product_snapshot.product_id),
                    supplier_id=str(item.product_snapshot.supplier_id),
                    product_name=item.product_snapshot.product_name,
                    product_slug=item.product_snapshot.product_slug,
                    sku=item.product_snapshot.sku,
                    variant_name=item.product_snapshot.variant_name,
                    variant_attributes=item.product_snapshot.variant_attributes,
                    image_url=item.product_snapshot.image_url,
                    supplier_name=item.product_snapshot.supplier_name
                ),
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                subtotal_cents=item.subtotal_cents,
                discount_cents=item.discount_cents,
                final_price_cents=item.final_price_cents,
                fulfillment_status=item.fulfillment_status.value,
                tracking_number=item.tracking_number,
                carrier=item.carrier,
                shipped_at=item.shipped_at,
                delivered_at=item.delivered_at
            )
            for item in order.items
        ],
        totals=OrderTotalsResponse(
            subtotal_cents=order.totals.subtotal_cents,
            discount_cents=order.totals.discount_cents,
            tax_cents=order.totals.tax_cents,
            shipping_cents=order.totals.shipping_cents,
            total_cents=order.totals.total_cents,
            currency=order.totals.currency
        ),
        shipping_address=ShippingAddressResponse(
            recipient_name=order.shipping_address.recipient_name,
            phone=order.shipping_address.phone,
            street_address_1=order.shipping_address.street_address_1,
            street_address_2=order.shipping_address.street_address_2,
            city=order.shipping_address.city,
            state=order.shipping_address.state,
            zip_code=order.shipping_address.zip_code,
            country=order.shipping_address.country,
            delivery_notes=order.shipping_address.delivery_notes
        ),
        billing_address=BillingAddressResponse(
            billing_name=order.billing_address.billing_name,
            street_address_1=order.billing_address.street_address_1,
            street_address_2=order.billing_address.street_address_2,
            city=order.billing_address.city,
            state=order.billing_address.state,
            zip_code=order.billing_address.zip_code,
            country=order.billing_address.country
        ) if order.billing_address else None,
        payment=PaymentInfoResponse(
            payment_method=order.payment.payment_method.value,
            payment_provider=order.payment.payment_provider,
            status=order.payment.status.value,
            card_last4=order.payment.card_last4,
            card_brand=order.payment.card_brand,
            transaction_id=order.payment.transaction_id,
            authorized_at=order.payment.authorized_at,
            captured_at=order.payment.captured_at
        ),
        attribution=OrderAttributionResponse(
            promotion_id=str(order.attribution.promotion_id) if order.attribution and order.attribution.promotion_id else None,
            promotion_title=order.attribution.promotion_title if order.attribution else None,
            community_id=str(order.attribution.community_id) if order.attribution and order.attribution.community_id else None,
            community_name=order.attribution.community_name if order.attribution else None,
            referral_code=order.attribution.referral_code if order.attribution else None,
            utm_source=order.attribution.utm_source if order.attribution else None,
            utm_medium=order.attribution.utm_medium if order.attribution else None,
            utm_campaign=order.attribution.utm_campaign if order.attribution else None
        ) if order.attribution else None,
        timeline=[
            TimelineEventResponse(
                status=event.status,
                timestamp=event.timestamp,
                note=event.note
            )
            for event in order.timeline
        ],
        estimated_delivery_date=order.estimated_delivery_date,
        created_at=order.created_at,
        updated_at=order.updated_at
    )


def order_to_list_item(order: Order) -> OrderListItemResponse:
    """Convert Order to list item (summary) response"""
    # Get primary image from first item
    primary_image = None
    if order.items:
        primary_image = order.items[0].product_snapshot.image_url

    return OrderListItemResponse(
        id=str(order.id),
        order_number=order.order_number,
        status=order.status.value,
        payment_status=order.payment.status.value,
        item_count=len(order.items),
        total_cents=order.totals.total_cents,
        currency=order.totals.currency,
        primary_image=primary_image,
        created_at=order.created_at
    )
