"""
Order Model - Purchase orders created by users

Orders capture complete purchase information including:
- Product snapshots at purchase time
- Payment and shipping details
- Order timeline and status tracking
- Idempotency for preventing duplicate orders
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class OrderStatus(str, Enum):
    """Overall order status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    """Payment processing status"""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class FulfillmentStatus(str, Enum):
    """Order fulfillment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentMethod(str, Enum):
    """Payment method types"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    BANK_TRANSFER = "bank_transfer"
    COD = "cash_on_delivery"


# Embedded Schemas
class OrderCustomer(BaseModel):
    """Customer information (denormalized from User)"""

    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]
    display_name: Annotated[str, Field(description="Customer display name")]
    email: Annotated[EmailStr, Field(description="Customer email for receipts")]
    phone: Annotated[Optional[str], Field(None, description="Customer phone number")]


class ProductSnapshot(BaseModel):
    """Immutable snapshot of product at time of purchase"""

    product_id: Annotated[PydanticObjectId, Field(description="Reference to Product document")]
    supplier_id: Annotated[PydanticObjectId, Field(description="Reference to Supplier document")]

    # Product details at purchase time
    product_name: Annotated[str, Field(description="Product name")]
    product_slug: Annotated[str, Field(description="Product slug")]
    sku: Annotated[str, Field(description="Product or variant SKU")]

    # Variant details (if applicable)
    variant_name: Annotated[Optional[str], Field(None, description="Variant name")]
    variant_attributes: Annotated[Dict[str, str], Field(default_factory=dict, description="Variant attributes")]

    # Visual
    image_url: Annotated[str, Field(description="Product/variant image URL")]

    # Supplier info
    supplier_name: Annotated[str, Field(description="Supplier business name")]


class OrderItem(BaseModel):
    """Individual item in the order"""

    item_id: Annotated[str, Field(description="Unique item identifier within order")]

    # Product snapshot
    product_snapshot: Annotated[ProductSnapshot, Field(description="Product details at purchase time")]

    # Quantity and pricing
    quantity: Annotated[int, Field(ge=1, description="Quantity ordered")]
    unit_price_cents: Annotated[int, Field(ge=0, description="Price per unit in cents")]
    subtotal_cents: Annotated[int, Field(ge=0, description="Item subtotal (quantity × unit_price)")]

    # Discounts applied to this item
    discount_cents: Annotated[int, Field(default=0, ge=0, description="Discount amount in cents")]
    final_price_cents: Annotated[int, Field(ge=0, description="Final price after discount")]

    # Fulfillment
    fulfillment_status: Annotated[FulfillmentStatus, Field(default=FulfillmentStatus.PENDING, description="Item fulfillment status")]
    shipped_quantity: Annotated[int, Field(default=0, ge=0, description="Quantity shipped")]

    # Tracking
    tracking_number: Annotated[Optional[str], Field(None, description="Shipping tracking number")]
    carrier: Annotated[Optional[str], Field(None, description="Shipping carrier")]
    shipped_at: Annotated[Optional[datetime], Field(None, description="Shipment timestamp")]
    delivered_at: Annotated[Optional[datetime], Field(None, description="Delivery timestamp")]


class OrderTotals(BaseModel):
    """Order financial totals (all in cents)"""

    subtotal_cents: Annotated[int, Field(ge=0, description="Sum of all items before tax/shipping")]
    discount_cents: Annotated[int, Field(default=0, ge=0, description="Total discount applied")]
    tax_cents: Annotated[int, Field(default=0, ge=0, description="Tax amount")]
    shipping_cents: Annotated[int, Field(default=0, ge=0, description="Shipping cost")]
    total_cents: Annotated[int, Field(ge=0, description="Grand total")]
    currency: Annotated[str, Field(default="USD", min_length=3, max_length=3, description="Currency code")]

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Ensure currency code is uppercase"""
        return v.upper()

    def to_decimal_totals(self) -> Dict[str, float]:
        """Convert all amounts to decimal for display"""
        return {
            "subtotal": self.subtotal_cents / 100,
            "discount": self.discount_cents / 100,
            "tax": self.tax_cents / 100,
            "shipping": self.shipping_cents / 100,
            "total": self.total_cents / 100,
            "currency": self.currency
        }


class ShippingAddress(BaseModel):
    """Shipping address details"""

    recipient_name: Annotated[str, Field(min_length=1, max_length=200, description="Recipient full name")]
    phone: Annotated[Optional[str], Field(None, description="Contact phone number")]

    street_address_1: Annotated[str, Field(min_length=1, max_length=200, description="Street address line 1")]
    street_address_2: Annotated[Optional[str], Field(None, max_length=200, description="Street address line 2")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]

    # Delivery instructions
    delivery_notes: Annotated[Optional[str], Field(None, max_length=500, description="Special delivery instructions")]

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()


class BillingAddress(BaseModel):
    """Billing address details"""

    billing_name: Annotated[str, Field(min_length=1, max_length=200, description="Name on payment method")]

    street_address_1: Annotated[str, Field(min_length=1, max_length=200, description="Street address line 1")]
    street_address_2: Annotated[Optional[str], Field(None, max_length=200, description="Street address line 2")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        return v.upper()


class PaymentInfo(BaseModel):
    """Payment details and transaction information"""

    payment_method: Annotated[PaymentMethod, Field(description="Payment method used")]
    payment_provider: Annotated[str, Field(description="Payment gateway (stripe, paypal, etc.)")]

    # Transaction details
    transaction_id: Annotated[Optional[str], Field(None, description="Payment gateway transaction ID")]
    authorization_code: Annotated[Optional[str], Field(None, description="Authorization code")]

    # Payment status
    status: Annotated[PaymentStatus, Field(default=PaymentStatus.PENDING, description="Payment status")]

    # Card details (last 4 digits only, never store full card)
    card_last4: Annotated[Optional[str], Field(None, max_length=4, description="Last 4 digits of card")]
    card_brand: Annotated[Optional[str], Field(None, description="Card brand (Visa, Mastercard, etc.)")]

    # Timestamps
    authorized_at: Annotated[Optional[datetime], Field(None, description="Payment authorization timestamp")]
    captured_at: Annotated[Optional[datetime], Field(None, description="Payment capture timestamp")]
    failed_at: Annotated[Optional[datetime], Field(None, description="Payment failure timestamp")]

    # Failure details
    failure_reason: Annotated[Optional[str], Field(None, max_length=500, description="Payment failure reason")]


class RefundInfo(BaseModel):
    """Refund details"""

    refund_amount_cents: Annotated[int, Field(ge=0, description="Refund amount in cents")]
    refund_reason: Annotated[str, Field(max_length=1000, description="Reason for refund")]
    refund_transaction_id: Annotated[Optional[str], Field(None, description="Refund transaction ID")]
    refunded_at: Annotated[datetime, Field(description="Refund timestamp")]
    refunded_by: Annotated[Optional[str], Field(None, description="Admin who processed refund")]

    # Items refunded (list of item_ids)
    refunded_items: Annotated[List[str], Field(default_factory=list, description="Item IDs refunded")]


class OrderTimeline(BaseModel):
    """Order status change event"""

    status: Annotated[str, Field(description="Status at this point")]
    timestamp: Annotated[datetime, Field(description="When status changed")]
    note: Annotated[Optional[str], Field(None, max_length=500, description="Optional note")]
    updated_by: Annotated[Optional[str], Field(None, description="Who made the change")]


class OrderAudit(BaseModel):
    """Security and fraud detection audit trail"""

    ip_address: Annotated[str, Field(description="Customer IP address")]
    user_agent: Annotated[Optional[str], Field(None, description="Browser user agent")]

    # Fraud detection
    risk_score: Annotated[float, Field(default=0.0, ge=0.0, le=1.0, description="Fraud risk score (0-1)")]
    fraud_flags: Annotated[List[str], Field(default_factory=list, description="Fraud detection flags")]

    # Review
    requires_review: Annotated[bool, Field(default=False, description="Flagged for manual review")]
    reviewed_by: Annotated[Optional[str], Field(None, description="Admin who reviewed")]
    reviewed_at: Annotated[Optional[datetime], Field(None, description="Review timestamp")]
    review_notes: Annotated[Optional[str], Field(None, max_length=1000, description="Review notes")]


class OrderAttribution(BaseModel):
    """Marketing attribution - how customer found this product"""

    # Promotion reference
    promotion_id: Annotated[Optional[PydanticObjectId], Field(None, description="Promotion that led to purchase")]
    promotion_title: Annotated[Optional[str], Field(None, description="Promotion title")]

    # Community reference
    community_id: Annotated[Optional[PydanticObjectId], Field(None, description="Community where customer saw promotion")]
    community_name: Annotated[Optional[str], Field(None, description="Community name")]

    # Referral
    referral_code: Annotated[Optional[str], Field(None, description="Referral code used")]
    utm_source: Annotated[Optional[str], Field(None, description="UTM source")]
    utm_medium: Annotated[Optional[str], Field(None, description="UTM medium")]
    utm_campaign: Annotated[Optional[str], Field(None, description="UTM campaign")]


class CustomerNote(BaseModel):
    """Note added to order (by customer or support)"""

    note_id: Annotated[str, Field(description="Unique note identifier")]
    author_type: Annotated[str, Field(description="'customer' or 'support'")]
    author_id: Annotated[Optional[str], Field(None, description="User ID or admin ID")]
    content: Annotated[str, Field(max_length=2000, description="Note content")]
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Note creation time")]


# Main Order Document
class Order(Document):
    """
    Order model - purchase orders created by users

    Captures complete purchase information with:
    - Product snapshots (immutable)
    - Payment and shipping tracking
    - Order timeline and audit trail
    - Attribution for analytics
    """

    # Order identification
    order_number: Annotated[str, Field(description="Human-readable order number (e.g., ORD-20250203-1234)")]

    # Customer
    customer: Annotated[OrderCustomer, Field(description="Customer information")]

    # Order items
    items: Annotated[List[OrderItem], Field(description="Products purchased")]

    # Financial totals
    totals: Annotated[OrderTotals, Field(description="Order totals")]

    # Addresses
    shipping_address: Annotated[ShippingAddress, Field(description="Delivery address")]
    billing_address: Annotated[Optional[BillingAddress], Field(None, description="Billing address (if different)")]

    # Payment
    payment: Annotated[PaymentInfo, Field(description="Payment details")]

    # Refund info (if applicable)
    refunds: Annotated[List[RefundInfo], Field(default_factory=list, description="Refund history")]

    # Order status
    status: Annotated[OrderStatus, Field(default=OrderStatus.PENDING, description="Overall order status")]

    # Timeline
    timeline: Annotated[List[OrderTimeline], Field(default_factory=list, description="Order status history")]

    # Audit
    audit: Annotated[OrderAudit, Field(description="Security audit trail")]

    # Attribution
    attribution: Annotated[Optional[OrderAttribution], Field(None, description="Marketing attribution")]

    # Notes
    notes: Annotated[List[CustomerNote], Field(default_factory=list, description="Order notes")]

    # Idempotency
    idempotency_key: Annotated[str, Field(description="Unique key to prevent duplicate orders")]

    # Estimated delivery
    estimated_delivery_date: Annotated[Optional[datetime], Field(None, description="Estimated delivery date")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Order creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "orders"

        indexes = [
            # Unique order number
            [("order_number", 1)],

            # Unique idempotency key (prevent duplicates)
            [("idempotency_key", 1)],

            # Customer's orders
            [("customer.user_id", 1), ("created_at", -1)],

            # Order status filtering
            [("status", 1), ("created_at", -1)],

            # Payment status
            [("payment.status", 1), ("created_at", -1)],

            # Supplier's orders (for fulfillment)
            [("items.product_snapshot.supplier_id", 1), ("status", 1)],

            # Promotion attribution
            [("attribution.promotion_id", 1), ("created_at", -1)],

            # Orders requiring review
            [("audit.requires_review", 1), ("audit.reviewed_at", 1)],

            # Orders by date range
            [("created_at", -1)],
        ]

    @field_validator("order_number")
    @classmethod
    def validate_order_number(cls, v: str) -> str:
        """Ensure order number is uppercase"""
        return v.upper()

    # Helper methods
    def get_total_items(self) -> int:
        """Get total number of items"""
        return sum(item.quantity for item in self.items)

    def get_total_amount_display(self) -> str:
        """Get formatted total amount"""
        amount = self.totals.total_cents / 100
        return f"{self.totals.currency} {amount:.2f}"

    def is_paid(self) -> bool:
        """Check if order is paid"""
        return self.payment.status in [PaymentStatus.CAPTURED, PaymentStatus.AUTHORIZED]

    def is_shipped(self) -> bool:
        """Check if all items are shipped"""
        return all(
            item.fulfillment_status == FulfillmentStatus.SHIPPED
            for item in self.items
        )

    def is_delivered(self) -> bool:
        """Check if all items are delivered"""
        return all(
            item.fulfillment_status == FulfillmentStatus.DELIVERED
            for item in self.items
        )

    def can_be_cancelled(self) -> bool:
        """Check if order can be cancelled"""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED] and not self.is_shipped()

    def get_refund_total(self) -> int:
        """Calculate total refunded amount in cents"""
        return sum(refund.refund_amount_cents for refund in self.refunds)

    async def add_timeline_event(self, status: str, note: Optional[str] = None, updated_by: Optional[str] = None) -> None:
        """Add status change to timeline"""
        self.timeline.append(
            OrderTimeline(
                status=status,
                timestamp=utc_now(),
                note=note,
                updated_by=updated_by
            )
        )
        await self.save()

    async def confirm_order(self) -> None:
        """Confirm order after payment"""
        self.status = OrderStatus.CONFIRMED
        await self.add_timeline_event("confirmed", "Order confirmed")

    async def start_processing(self) -> None:
        """Mark order as processing"""
        self.status = OrderStatus.PROCESSING
        await self.add_timeline_event("processing", "Order is being processed")

    async def mark_shipped(self, tracking_info: Dict[str, str]) -> None:
        """Mark order as shipped"""
        self.status = OrderStatus.SHIPPED

        # Update all items
        for item in self.items:
            item.fulfillment_status = FulfillmentStatus.SHIPPED
            item.tracking_number = tracking_info.get("tracking_number")
            item.carrier = tracking_info.get("carrier")
            item.shipped_at = utc_now()

        await self.add_timeline_event("shipped", f"Shipped via {tracking_info.get('carrier')}")

    async def mark_delivered(self) -> None:
        """Mark order as delivered"""
        self.status = OrderStatus.DELIVERED

        # Update all items
        for item in self.items:
            item.fulfillment_status = FulfillmentStatus.DELIVERED
            item.delivered_at = utc_now()

        await self.add_timeline_event("delivered", "Order delivered successfully")

    async def cancel_order(self, reason: str, cancelled_by: Optional[str] = None) -> None:
        """Cancel order"""
        if not self.can_be_cancelled():
            raise ValueError("Order cannot be cancelled")

        self.status = OrderStatus.CANCELLED

        # Cancel all items
        for item in self.items:
            item.fulfillment_status = FulfillmentStatus.CANCELLED

        await self.add_timeline_event("cancelled", reason, cancelled_by)

    async def add_refund(self, refund: RefundInfo) -> None:
        """Add refund to order"""
        self.refunds.append(refund)

        # Check if fully refunded
        total_refunded = self.get_refund_total()
        if total_refunded >= self.totals.total_cents:
            self.status = OrderStatus.REFUNDED
            self.payment.status = PaymentStatus.REFUNDED
        else:
            self.payment.status = PaymentStatus.PARTIALLY_REFUNDED

        await self.add_timeline_event(
            "refunded",
            f"Refund of {refund.refund_amount_cents / 100} {self.totals.currency}"
        )

    async def add_note(self, author_type: str, content: str, author_id: Optional[str] = None) -> None:
        """Add note to order"""
        import uuid

        note = CustomerNote(
            note_id=str(uuid.uuid4()),
            author_type=author_type,
            author_id=author_id,
            content=content,
            created_at=utc_now()
        )

        self.notes.append(note)
        await self.save()

    async def flag_for_review(self, reason: str) -> None:
        """Flag order for manual review"""
        self.audit.requires_review = True
        self.audit.fraud_flags.append(reason)
        await self.save()

    async def mark_reviewed(self, reviewed_by: str, notes: str) -> None:
        """Mark order as reviewed"""
        self.audit.requires_review = False
        self.audit.reviewed_by = reviewed_by
        self.audit.reviewed_at = utc_now()
        self.audit.review_notes = notes
        await self.save()

    def to_public_dict(self) -> dict:
        """Return customer-facing order data"""
        return {
            "order_number": self.order_number,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "items": [
                {
                    "product_name": item.product_snapshot.product_name,
                    "variant": item.product_snapshot.variant_name,
                    "image": item.product_snapshot.image_url,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price_cents / 100,
                    "total": item.final_price_cents / 100,
                    "fulfillment_status": item.fulfillment_status.value,
                    "tracking_number": item.tracking_number
                }
                for item in self.items
            ],
            "totals": self.totals.to_decimal_totals(),
            "shipping_address": {
                "recipient": self.shipping_address.recipient_name,
                "street": self.shipping_address.street_address_1,
                "city": self.shipping_address.city,
                "state": self.shipping_address.state,
                "zip": self.shipping_address.zip_code,
                "country": self.shipping_address.country
            },
            "payment": {
                "method": self.payment.payment_method.value,
                "status": self.payment.status.value,
                "card_last4": self.payment.card_last4
            },
            "estimated_delivery": self.estimated_delivery_date.isoformat() if self.estimated_delivery_date else None,
            "timeline": [
                {
                    "status": event.status,
                    "timestamp": event.timestamp.isoformat(),
                    "note": event.note
                }
                for event in self.timeline
            ]
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
