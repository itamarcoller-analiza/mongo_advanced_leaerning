"""
Order Service - Business logic for order operations
"""

import secrets
from typing import Optional, Dict, Any, List, Tuple

from beanie import PydanticObjectId

from shared.models.order import *
from shared.models.product import Product, ProductStatus
from shared.models.user import User
from shared.models.promotion import Promotion, PromotionStatus, VisibilityType
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.serialization import oid_to_str


class OrderService:
    """Service class for order operations"""

    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100
        self.price_drift_threshold = 0.05  # 5%
        self.high_value_threshold_cents = 100000  # $1000
        self.velocity_window_hours = 24
        self.velocity_threshold = 5  # max orders per window
        self.tax_rate = 0.08  # 8% flat tax for MVP
        self.shipping_cost_cents = 599  # $5.99 flat rate
        self.free_shipping_threshold_cents = 5000  # Free shipping over $50
        self._kafka = get_kafka_producer()

    # ============================================================
    # Helper Methods
    # ============================================================

    def _generate_order_number(self) -> str:
        """Generate unique order number: ORD-YYYYMMDD-XXXX"""
        date_part = utc_now().strftime("%Y%m%d")
        random_part = secrets.token_hex(2).upper()
        return f"ORD-{date_part}-{random_part}"

    async def _get_user_order(self, order_id: str, user_id: str) -> Order:
        """
        Get order by ID that belongs to a specific user.
        Raises ValueError if not found or invalid IDs.
        """
        try:
            order = await Order.find_one({
                "_id": PydanticObjectId(order_id),
                "customer.user_id": PydanticObjectId(user_id)
            })
        except Exception:
            raise ValueError("Invalid order or user ID")

        if not order:
            raise ValueError("Order not found")

        return order

    async def _validate_product_for_order(
        self,
        product_id: str,
        variant_name: Optional[str],
        quantity: int
    ) -> Tuple[Product, Optional[Dict]]:
        """
        Validate product is active and has inventory.
        Returns (product, variant_dict) tuple.
        """
        try:
            product = await Product.get(PydanticObjectId(product_id))
        except Exception:
            raise ValueError(f"Invalid product ID: {product_id}")

        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.deleted_at:
            raise ValueError(f"Product '{product.name}' is no longer available")

        if product.status != ProductStatus.ACTIVE:
            raise ValueError(f"Product '{product.name}' is not available for purchase")

        # Check variant if specified
        variant = None
        if variant_name:
            variant = product.get_variant_by_name(variant_name)
            if not variant:
                raise ValueError(f"Variant '{variant_name}' not found for product '{product.name}'")
            if not variant.is_active:
                raise ValueError(f"Variant '{variant_name}' is not available")
            if variant.available < quantity:
                raise ValueError(f"Insufficient stock for '{product.name}' - '{variant_name}'. Available: {variant.available}")
        else:
            # Check total available across locations
            total_available = product.get_total_available()
            if total_available < quantity:
                raise ValueError(f"Insufficient stock for '{product.name}'. Available: {total_available}")

        return product, variant

    async def _validate_promotion(
        self,
        promotion_id: str,
        user_id: str,
        product_ids: List[str],
        community_id: Optional[str] = None
    ) -> Optional[Promotion]:
        """Validate promotion is active and applicable. Returns None if validation fails."""
        try:
            promotion = await Promotion.get(PydanticObjectId(promotion_id))
        except Exception:
            return None

        if not promotion or promotion.deleted_at:
            return None

        # Check promotion is active
        if promotion.status not in [PromotionStatus.ACTIVE, PromotionStatus.SCHEDULED]:
            return None

        # Check schedule window
        now = utc_now()
        if promotion.schedule.start_date and now < promotion.schedule.start_date:
            return None
        if promotion.schedule.end_date and now > promotion.schedule.end_date:
            return None

        # Check visibility
        if promotion.visibility.type == VisibilityType.COMMUNITIES:
            if not community_id:
                return None
            try:
                community_oid = PydanticObjectId(community_id)
                if community_oid not in promotion.visibility.community_ids:
                    return None
            except Exception:
                return None

        # Check if any product is in the promotion
        promo_product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
        if not any(pid in promo_product_ids for pid in product_ids):
            return None

        return promotion

    # async def _basic_fraud_check(
    #     self,
    #     user_id: str,
    #     total_cents: int,
    #     ip_address: str
    # ) -> Tuple[float, List[str], bool]:
    #     """
    #     Basic fraud detection.
    #     Returns: (risk_score, fraud_flags, requires_review)
    #     """
    #     risk_score = 0.0
    #     flags = []
    #
    #     # High value order
    #     if total_cents > self.high_value_threshold_cents:
    #         risk_score += 0.3
    #         flags.append("HIGH_VALUE_ORDER")
    #
    #     # Velocity check - orders in last 24 hours
    #     try:
    #         cutoff = utc_now() - timedelta(hours=self.velocity_window_hours)
    #         recent_orders = await Order.find({
    #             "customer.user_id": PydanticObjectId(user_id),
    #             "created_at": {"$gte": cutoff}
    #         }).count()
    #
    #         if recent_orders >= self.velocity_threshold:
    #             risk_score += 0.4
    #             flags.append("HIGH_VELOCITY")
    #     except Exception:
    #         pass  # Don't fail on velocity check errors
    #
    #     requires_review = risk_score >= 0.5
    #     return min(risk_score, 1.0), flags, requires_review

    def _calculate_totals(
        self,
        items_data: List[Dict],
        promotion: Optional[Promotion] = None
    ) -> Tuple[OrderTotals, List[Dict]]:
        """
        Calculate order totals and item-level discounts.
        Returns: (totals, items_with_discounts)
        """
        subtotal = 0
        total_discount = 0

        # Calculate item-level prices and discounts
        for item in items_data:
            item_subtotal = item["unit_price_cents"] * item["quantity"]
            subtotal += item_subtotal

            # Calculate discount if promotion applies
            item_discount = 0
            if promotion:
                for promo_product in promotion.products:
                    if str(promo_product.product_snapshot.product_id) == item["product_id"]:
                        item_discount = int(item_subtotal * promo_product.discount_percent / 100)
                        break

            item["discount_cents"] = item_discount
            item["final_price_cents"] = item_subtotal - item_discount
            total_discount += item_discount

        # Tax calculation (MVP: flat 8% on discounted subtotal)
        taxable_amount = subtotal - total_discount
        tax = int(taxable_amount * self.tax_rate)

        # Shipping (MVP: flat $5.99 or free over $50)
        if taxable_amount >= self.free_shipping_threshold_cents:
            shipping = 0
        else:
            shipping = self.shipping_cost_cents

        total = taxable_amount + tax + shipping

        totals = OrderTotals(
            subtotal_cents=subtotal,
            discount_cents=total_discount,
            tax_cents=tax,
            shipping_cents=shipping,
            total_cents=total,
            currency="USD"
        )

        return totals, items_data

    def _build_product_snapshot(
        self,
        product: Product,
        variant: Optional[Dict]
    ) -> ProductSnapshot:
        """Build product snapshot for order item"""
        variant_name = None
        variant_attributes = {}
        sku = product.metadata.base_sku
        image_url = str(product.images.primary_image)

        if variant:
            variant_name = variant.variant_name
            variant_attributes = {
                attr.attribute_name: attr.attribute_value
                for attr in variant.attributes
            }
            sku = variant.sku
            if variant.image_url:
                image_url = str(variant.image_url)

        return ProductSnapshot(
            product_id=product.id,
            supplier_id=product.supplier_id,
            product_name=product.name,
            product_slug=product.slug,
            sku=sku,
            variant_name=variant_name,
            variant_attributes=variant_attributes,
            image_url=image_url,
            supplier_name=product.supplier_info.get("name", "Unknown Supplier")
        )

    # ============================================================
    # Main Service Methods
    # ============================================================

    async def create_order(
        self,
        user_id: str,
        order_data: Dict[str, Any],
        idempotency_key: str,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> Order:
        """
        Create a new pending order.

        Steps:
        1. Check idempotency key
        2. Validate user
        3. Validate all products
        4. Validate promotion (if provided)
        5. Calculate totals
        6. Create order with PENDING status
        """
        # 1. Check idempotency
        existing = await Order.find_one({"idempotency_key": idempotency_key})
        if existing:
            return existing

        # 2. Get user info
        try:
            user = await User.get(PydanticObjectId(user_id))
        except Exception:
            raise ValueError("Invalid user ID")

        if not user:
            raise ValueError("User not found")

        if user.deleted_at:
            raise ValueError("User account is not active")

        # 3. Validate products and build items data
        items_data = []
        product_ids = []

        for item_req in order_data["items"]:
            product, variant = await self._validate_product_for_order(
                item_req["product_id"],
                item_req.get("variant_name"),
                item_req["quantity"]
            )
            product_ids.append(str(product.id))

            unit_price = variant.price_cents if variant else product.base_price_cents

            items_data.append({
                "product": product,
                "variant": variant,
                "product_id": str(product.id),
                "variant_name": item_req.get("variant_name"),
                "quantity": item_req["quantity"],
                "unit_price_cents": unit_price
            })

        # 4. Validate promotion (if provided)
        attribution_data = order_data.get("attribution", {}) or {}
        promotion = None
        if attribution_data.get("promotion_id"):
            promotion = await self._validate_promotion(
                attribution_data["promotion_id"],
                user_id,
                product_ids,
                attribution_data.get("community_id")
            )

        # 5. Calculate totals
        totals, items_data = self._calculate_totals(items_data, promotion)

        # 6. Build order items
        order_items = []
        for i, item_data in enumerate(items_data):
            product = item_data["product"]
            variant = item_data["variant"]
            subtotal = item_data["unit_price_cents"] * item_data["quantity"]

            order_items.append(OrderItem(
                item_id=f"item_{i+1}",
                product_snapshot=self._build_product_snapshot(product, variant),
                quantity=item_data["quantity"],
                unit_price_cents=item_data["unit_price_cents"],
                subtotal_cents=subtotal,
                discount_cents=item_data.get("discount_cents", 0),
                final_price_cents=item_data.get("final_price_cents", subtotal),
                fulfillment_status=FulfillmentStatus.PENDING
            ))

        # Build customer info
        customer = OrderCustomer(
            user_id=user.id,
            display_name=user.profile.display_name if user.profile else "Customer",
            email=user.contact_info.primary_email,
            phone=user.contact_info.phone if user.contact_info else None
        )

        # Build addresses
        shipping_data = order_data["shipping_address"]
        shipping_address = ShippingAddress(
            recipient_name=shipping_data["recipient_name"],
            phone=shipping_data.get("phone"),
            street_address_1=shipping_data["street_address_1"],
            street_address_2=shipping_data.get("street_address_2"),
            city=shipping_data["city"],
            state=shipping_data["state"],
            zip_code=shipping_data["zip_code"],
            country=shipping_data["country"].upper(),
            delivery_notes=shipping_data.get("delivery_notes")
        )

        billing_address = None
        if order_data.get("billing_address"):
            billing_data = order_data["billing_address"]
            billing_address = BillingAddress(
                billing_name=billing_data["billing_name"],
                street_address_1=billing_data["street_address_1"],
                street_address_2=billing_data.get("street_address_2"),
                city=billing_data["city"],
                state=billing_data["state"],
                zip_code=billing_data["zip_code"],
                country=billing_data["country"].upper()
            )

        # Build payment info
        payment_data = order_data["payment_info"]
        try:
            payment_method = PaymentMethod(payment_data["payment_method"])
        except ValueError:
            payment_method = PaymentMethod.CREDIT_CARD

        payment = PaymentInfo(
            payment_method=payment_method,
            payment_provider=payment_data.get("payment_provider", "stripe"),
            status=PaymentStatus.PENDING,
            card_last4=payment_data.get("card_last4"),
            card_brand=payment_data.get("card_brand")
        )

        # Build attribution
        order_attribution = None
        if promotion or attribution_data:
            order_attribution = OrderAttribution(
                promotion_id=promotion.id if promotion else None,
                promotion_title=promotion.title if promotion else None,
                community_id=PydanticObjectId(attribution_data["community_id"]) if attribution_data.get("community_id") else None,
                community_name=None,  # Would need to fetch community
                referral_code=attribution_data.get("referral_code"),
                utm_source=attribution_data.get("utm_source"),
                utm_medium=attribution_data.get("utm_medium"),
                utm_campaign=attribution_data.get("utm_campaign")
            )

        # Build audit (no fraud check for now)
        audit = OrderAudit(
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=0.0,
            fraud_flags=[],
            requires_review=False
        )

        # Create order
        order = Order(
            order_number=self._generate_order_number(),
            customer=customer,
            items=order_items,
            totals=totals,
            shipping_address=shipping_address,
            billing_address=billing_address,
            payment=payment,
            status=OrderStatus.PENDING,
            audit=audit,
            attribution=order_attribution,
            idempotency_key=idempotency_key,
            timeline=[OrderTimeline(
                status="pending",
                timestamp=utc_now(),
                note="Order created"
            )]
        )

        await order.insert()

        # Emit order.created event
        self._kafka.emit(
            topic=Topic.ORDER,
            action="created",
            entity_id=oid_to_str(order.id),
            data=order.model_dump(mode="json"),
        )

        return order

    async def complete_order(
        self,
        order_id: str,
        user_id: str,
        idempotency_key: str
    ) -> Order:
        """
        Complete order (authorize payment, reserve inventory).

        Steps:
        1. Validate order exists and owned by user
        2. Validate order status is PENDING
        3. Re-validate pricing (5% drift threshold)
        4. Reserve inventory atomically
        5. Authorize payment (mock for MVP)
        6. Transition to CONFIRMED
        """
        # 1. Get order
        order = await self._get_user_order(order_id, user_id)

        # 2. Validate order status
        if order.status == OrderStatus.CONFIRMED:
            return order  # Idempotent - already completed

        if order.status != OrderStatus.PENDING:
            raise ValueError(f"Order cannot be completed - status is {order.status.value}")

        if order.payment.status != PaymentStatus.PENDING:
            raise ValueError("Payment has already been processed")

        # 3. Re-validate pricing
        for item in order.items:
            try:
                product = await Product.get(item.product_snapshot.product_id)
            except Exception:
                raise ValueError(f"Product {item.product_snapshot.product_name} is no longer available")

            if not product or product.status != ProductStatus.ACTIVE:
                raise ValueError(f"Product '{item.product_snapshot.product_name}' is no longer available")

            current_price = product.base_price_cents
            if item.product_snapshot.variant_name:
                variant = product.get_variant_by_name(item.product_snapshot.variant_name)
                if variant:
                    current_price = variant.price_cents

            # Check price drift
            original_price = item.unit_price_cents
            if original_price > 0:
                drift = abs(current_price - original_price) / original_price
                if drift > self.price_drift_threshold:
                    raise ValueError(
                        f"Price for '{item.product_snapshot.product_name}' has changed significantly. "
                        f"Original: ${original_price/100:.2f}, Current: ${current_price/100:.2f}"
                    )

        # 4. Reserve inventory
        reserved_items = []
        try:
            for item in order.items:
                product = await Product.get(item.product_snapshot.product_id)
                if not product:
                    raise ValueError(f"Product not found for reservation")

                success = False
                if item.product_snapshot.variant_name:
                    success = await product.reserve_variant_inventory(
                        item.product_snapshot.variant_name,
                        item.quantity
                    )
                else:
                    # Reserve from first available location
                    for location in product.stock_locations:
                        if location.available >= item.quantity:
                            success = await product.reserve_location_inventory(
                                location.location_id,
                                item.quantity
                            )
                            if success:
                                break

                if not success:
                    raise ValueError(f"Insufficient stock for '{item.product_snapshot.product_name}'")

                reserved_items.append((product, item))

        except ValueError:
            # Rollback reservations on failure
            for product, item in reserved_items:
                try:
                    if item.product_snapshot.variant_name:
                        await product.release_variant_inventory(
                            item.product_snapshot.variant_name,
                            item.quantity
                        )
                    else:
                        for location in product.stock_locations:
                            await product.release_location_inventory(
                                location.location_id,
                                item.quantity
                            )
                            break
                except Exception:
                    pass  # Best effort rollback
            raise

        # 5. Authorize payment (mock for MVP)
        order.payment.status = PaymentStatus.AUTHORIZED
        order.payment.authorized_at = utc_now()
        order.payment.transaction_id = f"mock_txn_{order.order_number}"
        order.payment.authorization_code = f"AUTH_{secrets.token_hex(4).upper()}"

        # 6. Update order status
        order.status = OrderStatus.CONFIRMED
        order.timeline.append(OrderTimeline(
            status="confirmed",
            timestamp=utc_now(),
            note="Payment authorized and inventory reserved"
        ))

        await order.save()

        # Emit order.completed event
        self._kafka.emit(
            topic=Topic.ORDER,
            action="completed",
            entity_id=oid_to_str(order.id),
            data={
                "order_number": order.order_number,
                "customer_id": oid_to_str(order.customer.user_id),
                "total_cents": order.totals.total_cents,
                "currency": order.totals.currency,
                "item_count": len(order.items),
                "status": order.status.value,
            },
        )

        # Record promotion conversion if applicable
        if order.attribution and order.attribution.promotion_id:
            try:
                promotion = await Promotion.get(order.attribution.promotion_id)
                if promotion:
                    await promotion.record_conversion(
                        order.totals.total_cents,
                        str(order.attribution.community_id) if order.attribution.community_id else None
                    )
            except Exception:
                pass  # Don't fail order completion on analytics error

        return order

    async def cancel_order(
        self,
        order_id: str,
        user_id: str,
        reason: str
    ) -> Order:
        """
        Cancel order.

        Steps:
        1. Validate order can be cancelled
        2. Release inventory if reserved
        3. Void payment if authorized
        4. Update status to CANCELLED
        """
        order = await self._get_user_order(order_id, user_id)

        if not order.can_be_cancelled():
            raise ValueError(f"Order cannot be cancelled - status is {order.status.value}")

        # Release inventory if confirmed
        if order.status == OrderStatus.CONFIRMED:
            for item in order.items:
                try:
                    product = await Product.get(item.product_snapshot.product_id)
                    if product:
                        if item.product_snapshot.variant_name:
                            await product.release_variant_inventory(
                                item.product_snapshot.variant_name,
                                item.quantity
                            )
                        else:
                            for location in product.stock_locations:
                                await product.release_location_inventory(
                                    location.location_id,
                                    item.quantity
                                )
                                break
                except Exception:
                    pass  # Best effort release

        # Void payment if authorized
        if order.payment.status == PaymentStatus.AUTHORIZED:
            order.payment.status = PaymentStatus.PENDING  # Voided
            # In real implementation, call payment provider to void

        await order.cancel_order(reason, user_id)

        # Emit order.cancelled event
        self._kafka.emit(
            topic=Topic.ORDER,
            action="cancelled",
            entity_id=oid_to_str(order.id),
            data={
                "order_number": order.order_number,
                "customer_id": oid_to_str(order.customer.user_id),
                "total_cents": order.totals.total_cents,
                "reason": reason,
            },
        )

        return order

    async def modify_order(
        self,
        order_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Order:
        """
        Modify pending order.
        Only PENDING orders with PENDING payment can be modified.
        """
        order = await self._get_user_order(order_id, user_id)

        if order.status != OrderStatus.PENDING:
            raise ValueError("Only pending orders can be modified")

        if order.payment.status != PaymentStatus.PENDING:
            raise ValueError("Cannot modify order with processed payment")

        # Update shipping address
        if "shipping_address" in updates and updates["shipping_address"]:
            addr = updates["shipping_address"]
            order.shipping_address = ShippingAddress(
                recipient_name=addr["recipient_name"],
                phone=addr.get("phone"),
                street_address_1=addr["street_address_1"],
                street_address_2=addr.get("street_address_2"),
                city=addr["city"],
                state=addr["state"],
                zip_code=addr["zip_code"],
                country=addr["country"].upper(),
                delivery_notes=addr.get("delivery_notes")
            )

        # Update billing address
        if "billing_address" in updates:
            if updates["billing_address"]:
                addr = updates["billing_address"]
                order.billing_address = BillingAddress(
                    billing_name=addr["billing_name"],
                    street_address_1=addr["street_address_1"],
                    street_address_2=addr.get("street_address_2"),
                    city=addr["city"],
                    state=addr["state"],
                    zip_code=addr["zip_code"],
                    country=addr["country"].upper()
                )
            else:
                order.billing_address = None

        # Update items (requires recalculation)
        if "items" in updates and updates["items"]:
            items_data = []

            for item_req in updates["items"]:
                product, variant = await self._validate_product_for_order(
                    item_req["product_id"],
                    item_req.get("variant_name"),
                    item_req["quantity"]
                )

                unit_price = variant.price_cents if variant else product.base_price_cents

                items_data.append({
                    "product": product,
                    "variant": variant,
                    "product_id": str(product.id),
                    "variant_name": item_req.get("variant_name"),
                    "quantity": item_req["quantity"],
                    "unit_price_cents": unit_price
                })

            # Recalculate totals
            promotion = None
            if order.attribution and order.attribution.promotion_id:
                promotion = await Promotion.get(order.attribution.promotion_id)

            totals, items_data = self._calculate_totals(items_data, promotion)
            order.totals = totals

            # Rebuild order items
            order_items = []
            for i, item_data in enumerate(items_data):
                product = item_data["product"]
                variant = item_data["variant"]
                subtotal = item_data["unit_price_cents"] * item_data["quantity"]

                order_items.append(OrderItem(
                    item_id=f"item_{i+1}",
                    product_snapshot=self._build_product_snapshot(product, variant),
                    quantity=item_data["quantity"],
                    unit_price_cents=item_data["unit_price_cents"],
                    subtotal_cents=subtotal,
                    discount_cents=item_data.get("discount_cents", 0),
                    final_price_cents=item_data.get("final_price_cents", subtotal),
                    fulfillment_status=FulfillmentStatus.PENDING
                ))

            order.items = order_items

        order.timeline.append(OrderTimeline(
            status="modified",
            timestamp=utc_now(),
            note="Order modified by customer"
        ))

        await order.save()
        return order

    async def list_user_orders(
        self,
        user_id: str,
        page_size: int = 20,
        cursor: Optional[str] = None,
        status_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """List user's orders with cursor pagination"""
        query = {"customer.user_id": PydanticObjectId(user_id)}

        if status_filter:
            query["status"] = {"$in": status_filter}

        if cursor:
            try:
                query["_id"] = {"$lt": PydanticObjectId(cursor)}
            except Exception:
                pass  # Invalid cursor, ignore

        page_size = min(page_size, self.max_page_size)

        orders = await Order.find(query).sort("-created_at").limit(page_size + 1).to_list()

        has_more = len(orders) > page_size
        if has_more:
            orders = orders[:-1]

        next_cursor = str(orders[-1].id) if has_more and orders else None

        return {
            "orders": orders,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size
            }
        }

    async def get_order(self, order_id: str, user_id: str) -> Order:
        """Get order by ID (user must own it)"""
        return await self._get_user_order(order_id, user_id)

    async def get_order_by_number(self, order_number: str, user_id: str) -> Order:
        """Get order by order number (user must own it)"""
        try:
            order = await Order.find_one({
                "order_number": order_number.upper(),
                "customer.user_id": PydanticObjectId(user_id)
            })
        except Exception:
            raise ValueError("Invalid user ID")

        if not order:
            raise ValueError("Order not found")

        return order
