"""
Promotion Service - Business logic for promotion management
"""

from typing import Optional, Dict, Any, List
from beanie import PydanticObjectId

from shared.models.promotion import (
    Promotion, PromotionStatus, PromotionType, VisibilityType,
    SupplierInfo, ProductSnapshot, PromotionProduct,
    PromotionVisibility, PromotionSchedule, PromotionTerms,
    ApprovalStatus
)
from shared.models.supplier import Supplier
from shared.models.product import Product, ProductStatus
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.serialization import oid_to_str


class PromotionService:
    """Service class for promotion operations"""

    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100
        self._kafka = get_kafka_producer()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_supplier(self, supplier_id: str) -> Supplier:
        """Get supplier by ID"""
        supplier = await Supplier.get(PydanticObjectId(supplier_id))
        if not supplier:
            raise ValueError("Supplier not found")
        return supplier

    async def _check_supplier_can_create(self, supplier: Supplier) -> None:
        """Check if supplier can create promotions"""
        # Check supplier is active and verified
        if supplier.status.value != "active":
            raise ValueError("Supplier account is not active")

        if supplier.verification.verification_status.value != "verified":
            raise ValueError("Supplier must be verified to create promotions")

    async def _validate_product_ownership(
        self,
        supplier_id: str,
        product_ids: List[str]
    ) -> List[Product]:
        """Validate all products are owned by supplier"""
        products = []
        for pid in product_ids:
            product = await Product.find_one({
                "_id": PydanticObjectId(pid),
                "supplier_id": PydanticObjectId(supplier_id)
            })
            if not product:
                raise ValueError(f"Product {pid} not found or not owned by supplier")
            if product.status == ProductStatus.DELETED:
                raise ValueError(f"Product {pid} has been deleted")
            products.append(product)
        return products

    async def _check_product_active_promotion(
        self,
        product_ids: List[str],
        exclude_promotion_id: Optional[str] = None
    ) -> None:
        """Check if any product already has an active promotion"""
        query = {
            "products.product_snapshot.product_id": {"$in": [PydanticObjectId(pid) for pid in product_ids]},
            "status": PromotionStatus.ACTIVE
        }
        if exclude_promotion_id:
            query["_id"] = {"$ne": PydanticObjectId(exclude_promotion_id)}

        existing = await Promotion.find_one(query)
        if existing:
            # Find which product has the conflict
            existing_product_ids = [str(p.product_snapshot.product_id) for p in existing.products]
            conflicting = set(product_ids) & set(existing_product_ids)
            raise ValueError(
                f"Product(s) {list(conflicting)} already have an active promotion",
                {"existing_promotion_id": str(existing.id), "product_ids": list(conflicting)}
            )

    def _build_product_snapshot(self, product: Product) -> ProductSnapshot:
        """Build product snapshot from product"""
        return ProductSnapshot(
            product_id=product.id,
            product_name=product.name,
            product_slug=product.slug,
            product_image=str(product.images.primary_image) if product.images else "",
            original_price_cents=product.base_price_cents,
            currency=product.currency,
            snapshot_at=utc_now()
        )

    def _calculate_discounted_price(self, original_cents: int, discount_percent: int) -> int:
        """Calculate discounted price in cents"""
        if discount_percent == 0:
            return original_cents
        discount_amount = int(original_cents * discount_percent / 100)
        return original_cents - discount_amount

    # ========================================================================
    # Create Promotion
    # ========================================================================

    async def create_promotion(
        self,
        supplier_id: str,
        promotion_data: Dict[str, Any]
    ) -> Promotion:
        """Create a new promotion"""
        try:
            # Get and validate supplier
            supplier = await self._get_supplier(supplier_id)
            await self._check_supplier_can_create(supplier)

            # Validate promotion type
            promo_type = PromotionType(promotion_data["type"])

            # Suppliers cannot create DEFAULT promotions
            if promo_type == PromotionType.DEFAULT:
                raise ValueError("Default promotions can only be created by the system")

            # Validate product count
            products_data = promotion_data["products"]
            if promo_type == PromotionType.CAMPAIGN:
                if len(products_data) < 2 or len(products_data) > 3:
                    raise ValueError("Campaign promotions must have 2-3 products")
            elif promo_type == PromotionType.SINGLE:
                if len(products_data) != 1:
                    raise ValueError("Single promotions must have exactly 1 product")

            # Validate product ownership
            product_ids = [p["product_id"] for p in products_data]
            products = await self._validate_product_ownership(supplier_id, product_ids)

            # Build product snapshots
            promotion_products = []
            for i, product in enumerate(products):
                discount_percent = products_data[i].get("discount_percent", 0)
                discounted_price = self._calculate_discounted_price(
                    product.base_price_cents,
                    discount_percent
                )

                promotion_products.append(PromotionProduct(
                    product_snapshot=self._build_product_snapshot(product),
                    discount_percent=discount_percent,
                    discounted_price_cents=discounted_price,
                    current_status=product.status.value,
                    current_price_cents=product.base_price_cents
                ))

            # Build visibility
            visibility_data = promotion_data["visibility"]
            visibility = PromotionVisibility(
                type=VisibilityType(visibility_data["type"]),
                community_ids=[PydanticObjectId(cid) for cid in visibility_data.get("community_ids", [])]
            )

            # Build schedule
            schedule_data = promotion_data["schedule"]
            schedule = PromotionSchedule(
                start_date=schedule_data["start_date"],
                end_date=schedule_data["end_date"],
                timezone=schedule_data.get("timezone", "UTC")
            )

            # Build terms if provided
            terms = None
            if promotion_data.get("terms"):
                terms_data = promotion_data["terms"]
                terms = PromotionTerms(
                    terms_text=terms_data["terms_text"],
                    restrictions=terms_data.get("restrictions", []),
                    min_purchase_amount_cents=terms_data.get("min_purchase_amount_cents"),
                    max_uses_per_user=terms_data.get("max_uses_per_user")
                )

            # Build supplier info (denormalized)
            supplier_info = SupplierInfo(
                supplier_id=supplier.id,
                business_name=supplier.company_info.legal_name,
                logo=supplier.business_info.logo
            )

            # Create promotion
            promotion = Promotion(
                promotion_type=promo_type,
                supplier=supplier_info,
                title=promotion_data["title"],
                description=promotion_data["description"],
                banner_image=promotion_data["banner_image"],
                products=promotion_products,
                visibility=visibility,
                schedule=schedule,
                terms=terms,
                status=PromotionStatus.DRAFT,
                is_auto_generated=False
            )

            await promotion.insert()

            # Emit promotion.created event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="created",
                entity_id=oid_to_str(promotion.id),
                data=promotion.model_dump(mode="json"),
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to create promotion: {str(e)}")

    # ========================================================================
    # Get Promotion
    # ========================================================================

    async def get_promotion(self, promotion_id: str, supplier_id: str) -> Promotion:
        """Get promotion by ID (supplier must own it)"""
        try:
            promotion = await Promotion.find_one({
                "_id": PydanticObjectId(promotion_id),
                "supplier.supplier_id": PydanticObjectId(supplier_id)
            })

            if not promotion:
                raise ValueError("Promotion not found")

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to get promotion: {str(e)}")

    async def get_promotion_by_id(self, promotion_id: str) -> Promotion:
        """Get promotion by ID (admin use)"""
        try:
            promotion = await Promotion.get(PydanticObjectId(promotion_id))
            if not promotion:
                raise ValueError("Promotion not found")
            return promotion
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to get promotion: {str(e)}")

    # ========================================================================
    # List Promotions
    # ========================================================================

    async def list_promotions(
        self,
        supplier_id: str,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[List[str]] = None,
        type_filter: Optional[str] = None,
        include_deleted: bool = False
    ) -> Dict[str, Any]:
        """List supplier's promotions with pagination"""
        try:
            # Build query
            query = {"supplier.supplier_id": PydanticObjectId(supplier_id)}

            if status_filter:
                query["status"] = {"$in": status_filter}

            if type_filter:
                query["promotion_type"] = type_filter

            if not include_deleted:
                query["deleted_at"] = None

            # Limit page size
            limit = min(limit, self.max_page_size)
            skip = (page - 1) * limit

            # Get total count
            total = await Promotion.find(query).count()

            # Fetch promotions
            promotions = await Promotion.find(query).sort("-created_at").skip(skip).limit(limit).to_list()

            return {
                "items": promotions,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": (total + limit - 1) // limit,
                    "has_more": skip + len(promotions) < total
                }
            }

        except Exception as e:
            raise Exception(f"Failed to list promotions: {str(e)}")

    # ========================================================================
    # Update Promotion
    # ========================================================================

    async def update_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int,
        updates: Dict[str, Any]
    ) -> Promotion:
        """Update promotion (partial update with optimistic locking)"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version for optimistic locking
            if promotion.version != version:
                raise ValueError(
                    "Version conflict: promotion was modified by another request",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Cannot update auto-generated promotions
            if promotion.is_auto_generated:
                raise ValueError("Cannot modify auto-generated promotions")

            # Check status-based edit permissions
            if promotion.status == PromotionStatus.DRAFT:
                # Full edit allowed
                pass
            elif promotion.status == PromotionStatus.PAUSED:
                # Limited edit: only title, description, extend end_date
                allowed_fields = {"title", "description", "schedule"}
                update_fields = set(updates.keys())
                if not update_fields.issubset(allowed_fields):
                    raise ValueError(f"In paused status, only these fields can be updated: {allowed_fields}")
            else:
                raise ValueError(f"Cannot update promotion in {promotion.status.value} status")

            # Apply updates
            if "title" in updates:
                promotion.title = updates["title"]

            if "description" in updates:
                promotion.description = updates["description"]

            if "banner_image" in updates:
                promotion.banner_image = updates["banner_image"]

            if "products" in updates and promotion.status == PromotionStatus.DRAFT:
                # Re-validate products
                product_ids = [p["product_id"] for p in updates["products"]]
                products = await self._validate_product_ownership(supplier_id, product_ids)

                # Rebuild product snapshots
                promotion_products = []
                for i, product in enumerate(products):
                    discount_percent = updates["products"][i].get("discount_percent", 0)
                    discounted_price = self._calculate_discounted_price(
                        product.base_price_cents,
                        discount_percent
                    )
                    promotion_products.append(PromotionProduct(
                        product_snapshot=self._build_product_snapshot(product),
                        discount_percent=discount_percent,
                        discounted_price_cents=discounted_price,
                        current_status=product.status.value,
                        current_price_cents=product.base_price_cents
                    ))
                promotion.products = promotion_products

            if "visibility" in updates and promotion.status == PromotionStatus.DRAFT:
                visibility_data = updates["visibility"]
                promotion.visibility = PromotionVisibility(
                    type=VisibilityType(visibility_data["type"]),
                    community_ids=[PydanticObjectId(cid) for cid in visibility_data.get("community_ids", [])]
                )

            if "schedule" in updates:
                schedule_data = updates["schedule"]
                new_end_date = schedule_data.get("end_date", promotion.schedule.end_date)

                # If paused, can only extend end_date
                if promotion.status == PromotionStatus.PAUSED:
                    if new_end_date < promotion.schedule.end_date:
                        raise ValueError("Can only extend end_date when paused")

                promotion.schedule = PromotionSchedule(
                    start_date=schedule_data.get("start_date", promotion.schedule.start_date),
                    end_date=new_end_date,
                    timezone=schedule_data.get("timezone", promotion.schedule.timezone)
                )

            if "terms" in updates:
                if updates["terms"]:
                    terms_data = updates["terms"]
                    promotion.terms = PromotionTerms(
                        terms_text=terms_data["terms_text"],
                        restrictions=terms_data.get("restrictions", []),
                        min_purchase_amount_cents=terms_data.get("min_purchase_amount_cents"),
                        max_uses_per_user=terms_data.get("max_uses_per_user")
                    )
                else:
                    promotion.terms = None

            promotion.version += 1
            await promotion.save()

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to update promotion: {str(e)}")

    # ========================================================================
    # Delete Promotion
    # ========================================================================

    async def delete_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int
    ) -> None:
        """Delete promotion (with restrictions)"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict: promotion was modified by another request",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Check if can delete
            can_delete, error_code = promotion.can_delete()
            if not can_delete:
                if error_code == "AUTO_GENERATED_PROMO_PROTECTED":
                    raise ValueError("Cannot delete auto-generated promotions")
                elif error_code == "STATUS_PREVENTS_DELETE":
                    raise ValueError(
                        f"Cannot delete promotion in {promotion.status.value} status",
                        {"current_status": promotion.status.value}
                    )
                elif error_code == "CANNOT_DELETE_SENT_PROMOTION":
                    raise ValueError(
                        "Promotion has been sent to users and cannot be deleted. Use cancel instead.",
                        {"first_activated_at": promotion.first_activated_at.isoformat() if promotion.first_activated_at else None}
                    )

            # Hard delete
            await promotion.delete()

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to delete promotion: {str(e)}")

    # ========================================================================
    # Lifecycle Operations
    # ========================================================================

    async def submit_for_approval(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int
    ) -> Promotion:
        """Submit promotion for approval"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Validate all required fields are complete
            if not promotion.title or not promotion.description:
                raise ValueError("Title and description are required")

            if not promotion.products:
                raise ValueError("At least one product is required")

            if not promotion.banner_image:
                raise ValueError("Banner image is required")

            # Check products don't have active promotions
            product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
            await self._check_product_active_promotion(product_ids, promotion_id)

            await promotion.submit_for_approval()

            # Emit promotion.submitted event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="submitted",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                    "promotion_type": promotion.promotion_type.value,
                    "status": promotion.status.value,
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to submit promotion: {str(e)}")

    async def approve_promotion(
        self,
        promotion_id: str,
        reviewer_id: str,
        reviewer_type: str,
        scope: str,
        version: int,
        community_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Promotion:
        """Approve promotion"""
        try:
            promotion = await self.get_promotion_by_id(promotion_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Check products don't have active promotions (in case one was activated while pending)
            product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
            await self._check_product_active_promotion(product_ids, promotion_id)

            await promotion.approve(
                scope=scope,
                reviewer_id=PydanticObjectId(reviewer_id),
                reviewer_type=reviewer_type,
                community_id=community_id,
                notes=notes
            )

            # Emit promotion.approved event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="approved",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                    "reviewer_id": reviewer_id,
                    "scope": scope,
                    "status": promotion.status.value,
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to approve promotion: {str(e)}")

    async def reject_promotion(
        self,
        promotion_id: str,
        reviewer_id: str,
        reviewer_type: str,
        scope: str,
        reason: str,
        version: int,
        community_id: Optional[str] = None
    ) -> Promotion:
        """Reject promotion"""
        try:
            promotion = await self.get_promotion_by_id(promotion_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            await promotion.reject(
                scope=scope,
                reviewer_id=PydanticObjectId(reviewer_id),
                reviewer_type=reviewer_type,
                reason=reason,
                community_id=community_id
            )

            # Emit promotion.rejected event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="rejected",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                    "reviewer_id": reviewer_id,
                    "scope": scope,
                    "reason": reason,
                    "status": promotion.status.value,
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to reject promotion: {str(e)}")

    async def pause_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int,
        reason: str
    ) -> Promotion:
        """Pause an active promotion"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            await promotion.pause_promotion(reason)

            # Emit promotion.paused event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="paused",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                    "reason": reason,
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to pause promotion: {str(e)}")

    async def resume_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int
    ) -> Promotion:
        """Resume a paused promotion"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Check products don't have active promotions
            product_ids = [str(p.product_snapshot.product_id) for p in promotion.products]
            await self._check_product_active_promotion(product_ids, promotion_id)

            await promotion.resume_promotion()

            # Emit promotion.resumed event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="resumed",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to resume promotion: {str(e)}")

    async def cancel_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int,
        reason: str
    ) -> Promotion:
        """Cancel a promotion (soft delete)"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            # Cannot cancel auto-generated promotions
            if promotion.is_auto_generated:
                raise ValueError("Cannot cancel auto-generated promotions")

            await promotion.cancel_promotion(reason)

            # Emit promotion.cancelled event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="cancelled",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                    "reason": reason,
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to cancel promotion: {str(e)}")

    async def end_promotion(
        self,
        promotion_id: str,
        supplier_id: str,
        version: int
    ) -> Promotion:
        """End a promotion early"""
        try:
            promotion = await self.get_promotion(promotion_id, supplier_id)

            # Check version
            if promotion.version != version:
                raise ValueError(
                    "Version conflict",
                    {"expected_version": version, "current_version": promotion.version}
                )

            if promotion.status != PromotionStatus.ACTIVE:
                raise ValueError("Only active promotions can be ended")

            await promotion.end_promotion()

            # Emit promotion.ended event
            self._kafka.emit(
                topic=Topic.PROMOTION,
                action="ended",
                entity_id=oid_to_str(promotion.id),
                data={
                    "title": promotion.title,
                    "supplier_id": oid_to_str(promotion.supplier.supplier_id),
                },
            )

            return promotion

        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to end promotion: {str(e)}")

    # ========================================================================
    # Admin Operations
    # ========================================================================

    async def list_pending_approvals(
        self,
        page: int = 1,
        limit: int = 20,
        visibility_filter: Optional[str] = None,
        community_id_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """List promotions pending approval"""
        try:
            query = {"status": PromotionStatus.PENDING_APPROVAL}

            if visibility_filter:
                query["visibility.type"] = visibility_filter

            if community_id_filter:
                query["visibility.community_ids"] = PydanticObjectId(community_id_filter)

            limit = min(limit, self.max_page_size)
            skip = (page - 1) * limit

            total = await Promotion.find(query).count()
            promotions = await Promotion.find(query).sort("created_at").skip(skip).limit(limit).to_list()

            return {
                "items": promotions,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": (total + limit - 1) // limit,
                    "has_more": skip + len(promotions) < total
                }
            }

        except Exception as e:
            raise Exception(f"Failed to list pending approvals: {str(e)}")

    # ========================================================================
    # Public Feed Operations
    # ========================================================================

    async def get_global_feed_promotions(
        self,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get active promotions for global feed"""
        try:
            now = utc_now()

            query = {
                "status": PromotionStatus.ACTIVE,
                "deleted_at": None,
                "visibility.type": {"$in": [VisibilityType.GLOBAL.value, VisibilityType.BOTH.value]},
                "schedule.start_date": {"$lte": now},
                "schedule.end_date": {"$gte": now},
                "approval.global_approval.status": ApprovalStatus.APPROVED.value
            }

            if cursor:
                query["_id"] = {"$gt": PydanticObjectId(cursor)}

            limit = min(limit, 50)
            promotions = await Promotion.find(query).sort("-stats.impressions").limit(limit + 1).to_list()

            has_more = len(promotions) > limit
            if has_more:
                promotions = promotions[:-1]

            next_cursor = str(promotions[-1].id) if has_more and promotions else None

            return {
                "items": promotions,
                "cursor": next_cursor,
                "has_more": has_more
            }

        except Exception as e:
            raise Exception(f"Failed to get global feed: {str(e)}")

    async def get_community_feed_promotions(
        self,
        community_id: str,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get active promotions for a community feed"""
        try:
            now = utc_now()

            query = {
                "status": PromotionStatus.ACTIVE,
                "deleted_at": None,
                "visibility.type": {"$in": [VisibilityType.COMMUNITIES.value, VisibilityType.BOTH.value]},
                "visibility.community_ids": PydanticObjectId(community_id),
                "schedule.start_date": {"$lte": now},
                "schedule.end_date": {"$gte": now},
                f"approval.community_approvals.{community_id}.status": ApprovalStatus.APPROVED.value
            }

            if cursor:
                query["_id"] = {"$gt": PydanticObjectId(cursor)}

            limit = min(limit, 50)
            promotions = await Promotion.find(query).sort("-stats.impressions").limit(limit + 1).to_list()

            has_more = len(promotions) > limit
            if has_more:
                promotions = promotions[:-1]

            next_cursor = str(promotions[-1].id) if has_more and promotions else None

            return {
                "items": promotions,
                "cursor": next_cursor,
                "has_more": has_more
            }

        except Exception as e:
            raise Exception(f"Failed to get community feed: {str(e)}")
