"""
Product Service - Business logic for product management
"""

import re
from typing import Optional, Dict, Any, List
from bson import ObjectId
from beanie import PydanticObjectId

from shared.models.product import *
from shared.models.supplier import Supplier
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.serialization import oid_to_str


class ProductService:
    """Service class for product operations"""

    def __init__(self):
        """Initialize product service"""
        self.default_page_size = 20
        self.max_page_size = 100
        self._kafka = get_kafka_producer()

    # Helper methods
    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from product name"""
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug

    async def _check_supplier_can_create(self, supplier: Supplier) -> None:
        """Check if supplier can create products"""
        # TODO: Re-enable for production
        # if supplier.status.value != "active":
        #     raise ValueError("Supplier account is not active")

        # if supplier.verification.verification_status.value != "verified":
        #     raise ValueError("Supplier must be verified to create products")

        if not supplier.permissions.can_create_products:
            raise ValueError("Insufficient permissions to create products")

        # Count active products (not deleted)
        active_count = len([pid for pid in supplier.product_ids])
        if active_count >= supplier.permissions.max_products:
            raise ValueError(f"Maximum product limit reached ({supplier.permissions.max_products})")

    async def _check_name_uniqueness(self, name: str, exclude_id: Optional[str] = None) -> None:
        """Check if product name is unique (trademark requirement)"""
        query = {"name": name}
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}

        existing = await Product.find_one(query)
        if existing:
            raise ValueError(f"Product name '{name}' already exists")

    async def _check_sku_uniqueness(self, supplier_id: str, base_sku: str, exclude_id: Optional[str] = None) -> None:
        """Check if SKU is unique for this supplier"""
        query = {
            "supplier_id": PydanticObjectId(supplier_id), 
            "metadata.base_sku": base_sku.upper()}
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}

        existing = await Product.find_one(query)
        if existing:
            raise ValueError(f"SKU '{base_sku}' already exists for this supplier")

    async def _add_product_to_supplier(self, supplier: Supplier, product_id: PydanticObjectId) -> None:
        """Add product reference to supplier's product_ids array"""
        try:
            # Use $addToSet to avoid duplicates (idempotent)
            await supplier.update({"$addToSet": {"product_ids": product_id}})
        except Exception as e:
            # Log error but don't fail - reconciliation job will fix
            print(f"Warning: Failed to update supplier array: {e}")

    def _validate_publish_requirements(self, product: Product) -> None:
        """Validate product meets requirements for publishing"""
        errors = []

        # Must have at least one image
        if not product.images or not product.images.primary_image:
            errors.append("At least one image is required")

        # Must have stock available
        if product.get_total_available() <= 0:
            errors.append("Product must have available stock")

        # Must have short description
        if not product.short_description:
            errors.append("Short description is required")

        if errors:
            raise ValueError(f"Cannot publish product: {', '.join(errors)}")

    # Create Product
    async def create_product(
        self,
        supplier_id: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new product
        Returns: product data dictionary
        """
        try:
            # Get supplier and check permissions
            supplier = await Supplier.get(PydanticObjectId(supplier_id))
            if not supplier:
                raise ValueError("Supplier not found")

            await self._check_supplier_can_create(supplier)

            # Check name uniqueness (trademark)
            await self._check_name_uniqueness(product_data["name"])

            # Check SKU uniqueness
            await self._check_sku_uniqueness(supplier_id, product_data["base_sku"])

            # Generate slug
            slug = self._generate_slug(product_data["name"])

            # Build product images
            images_data = product_data.get("images", [])
            primary_img = next((img for img in images_data if img.get("is_primary")), images_data[0] if images_data else None)
            gallery_imgs = [img["url"] for img in images_data if not img.get("is_primary")]

            product_images = ProductImages(
                primary_image=primary_img["url"] if primary_img else "https://placeholder.com/default.jpg",
                gallery_images=gallery_imgs
            )

            # Build metadata
            metadata = ProductMetadata(
                base_sku=product_data["base_sku"],
                barcode=product_data.get("barcode"),
                brand=product_data.get("brand"),
                manufacturer=product_data.get("manufacturer"),
                model_number=product_data.get("model_number"),
                tags=product_data.get("tags", []),
                custom_attributes=product_data.get("custom_attributes", {})
            )

            # Build variants
            variants_dict = {}
            for variant_name, variant_data in product_data.get("variants", {}).items():
                # Build attributes
                attributes = [
                    VariantAttribute(
                        attribute_name=attr["attribute_name"],
                        attribute_value=attr["attribute_value"]
                    )
                    for attr in variant_data.get("attributes", [])
                ]

                # Build package dimensions
                pkg_dims = variant_data["package_dimensions"]
                package_dimensions = PackageDimensions(
                    width_cm=pkg_dims["width_cm"],
                    height_cm=pkg_dims["height_cm"],
                    depth_cm=pkg_dims["depth_cm"],
                    weight_grams=pkg_dims["weight_grams"]
                )

                variants_dict[variant_name] = ProductVariant(
                    variant_id=variant_data["variant_id"],
                    variant_name=variant_name,
                    attributes=attributes,
                    sku=variant_data["sku"],
                    price_cents=variant_data["price_cents"],
                    cost_cents=variant_data.get("cost_cents"),
                    quantity=variant_data.get("quantity", 0),
                    reserved=0,
                    package_dimensions=package_dimensions,
                    image_url=variant_data.get("image_url"),
                    is_active=True
                )

            # Build stock locations
            stock_locations = [
                StockLocation(
                    location_id=loc["location_id"],
                    location_name=loc["location_name"],
                    street_address=loc.get("street_address"),
                    city=loc["city"],
                    state=loc.get("state"),
                    zip_code=loc["zip_code"],
                    country=loc["country"],
                    quantity=loc.get("quantity", 0),
                    reserved=loc.get("reserved", 0)
                )
                for loc in product_data.get("stock_locations", [])
            ]

            # Build topic descriptions
            topic_descriptions = [
                TopicDescription(
                    topic=td["topic"],
                    description=td["description"],
                    display_order=td.get("display_order", 0)
                )
                for td in product_data.get("topic_descriptions", [])
            ]

            # Build shipping info
            shipping_data = product_data["shipping"]
            shipping = ShippingInfo(
                free_shipping=shipping_data.get("free_shipping", False),
                shipping_cost_cents=shipping_data.get("shipping_cost_cents"),
                ships_from_country=shipping_data["ships_from_country"],
                ships_to_countries=shipping_data.get("ships_to_countries", []),
                estimated_delivery_days=shipping_data.get("estimated_delivery_days")
            )

            # Denormalize supplier info
            supplier_info = {
                "id": str(supplier.id),
                "name": supplier.company_info.legal_name,
                "logo": supplier.business_info.logo or ""
            }

            # Create product
            product = Product(
                supplier_id=PydanticObjectId(supplier_id),
                supplier_info=supplier_info,
                name=product_data["name"],
                slug=slug,
                short_description=product_data.get("short_description"),
                topic_descriptions=topic_descriptions,
                category=ProductCategory(product_data["category"]),
                condition=ProductCondition(product_data.get("condition", "new")),
                unit_type=UnitType(product_data.get("unit_type", "piece")),
                images=product_images,
                metadata=metadata,
                stock_locations=stock_locations,
                variants=variants_dict,
                base_price_cents=product_data["base_price_cents"],
                currency=product_data.get("currency", "USD"),
                shipping=shipping,
                status=ProductStatus.DRAFT,
                is_available=False
            )

            # Save product
            await product.insert()

            # Emit product.created event
            product_id = oid_to_str(product.id)
            self._kafka.emit(
                topic=Topic.PRODUCT,
                action="created",
                entity_id=product_id,
                data=product.model_dump(mode="json"),
            )

            # Add to supplier's product array
            await self._add_product_to_supplier(supplier, product.id)

            return {
                "id": product_id,
                "supplier_id": str(product.supplier_id),
                "name": product.name,
                "slug": product.slug,
                "status": product.status.value,
                "is_available": product.is_available,
                "created_at": product.created_at.isoformat(),
                "updated_at": product.updated_at.isoformat()
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to create product: {str(e)}")

    # Get Product
    async def get_product(self, product_id: str, supplier_id: str) -> Optional[Product]:
        """
        Get product by ID (supplier must own it)
        Returns 404 if not found or wrong owner (security)
        """
        try:
            product = await Product.find_one({
                "_id": PydanticObjectId(product_id),
                "supplier_id": PydanticObjectId(supplier_id)
            })

            if not product:
                raise ValueError("Product not found")

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to get product: {str(e)}")

    # List Products
    async def list_products(
        self,
        supplier_id: str,
        page_size: int = 20,
        cursor: Optional[str] = None,
        status_filter: Optional[List[str]] = None,
        category_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List supplier's products with pagination
        """
        try:
            # Build query
            query = {"supplier_id": PydanticObjectId(supplier_id)}

            # Status filter
            if status_filter:
                query["status"] = {"$in": status_filter}

            # Category filter
            if category_filter:
                query["category"] = category_filter

            # Search
            if search:
                query["$text"] = {"$search": search}

            # Cursor pagination
            if cursor:
                # Decode cursor (simplified - in production use base64)
                query["_id"] = {"$gt": PydanticObjectId(cursor)}

            # Limit page size
            page_size = min(page_size, self.max_page_size)

            # Fetch products (+1 to check if more)
            products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

            # Check if more results
            has_more = len(products) > page_size
            if has_more:
                products = products[:-1]

            # Build response
            product_list = [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "slug": p.slug,
                    "status": p.status.value,
                    "category": p.category.value,
                    "base_price_cents": p.base_price_cents,
                    "currency": p.currency,
                    "primary_image": str(p.images.primary_image) if p.images else None,
                    "stock_quantity": p.get_total_inventory(),
                    "is_available": p.is_available,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in products
            ]

            next_cursor = str(products[-1].id) if has_more and products else None

            return {
                "products": product_list,
                "pagination": {
                    "next_cursor": next_cursor,
                    "has_more": has_more,
                    "page_size": page_size
                }
            }
        except Exception as e:
            raise Exception(f"Failed to list products: {str(e)}")

    # Update Product
    async def update_product(
        self,
        product_id: str,
        supplier_id: str,
        updates: Dict[str, Any]
    ) -> Product:
        """
        Update product (partial update)
        """
        try:
            # Get product
            product = await self.get_product(product_id, supplier_id)

            # Cannot update deleted product
            if product.status == ProductStatus.DELETED:
                raise ValueError("Cannot update deleted product. Use restore endpoint first")

            # Check name uniqueness if changing name
            if "name" in updates and updates["name"] != product.name:
                await self._check_name_uniqueness(updates["name"], product_id)
                # Update slug if name changed
                product.slug = self._generate_slug(updates["name"])

            # Check SKU uniqueness if changing SKU
            if "base_sku" in updates and updates["base_sku"] != product.metadata.base_sku:
                await self._check_sku_uniqueness(supplier_id, updates["base_sku"], product_id)

            # Apply updates
            if "name" in updates:
                product.name = updates["name"]
            if "short_description" in updates:
                product.short_description = updates["short_description"]
            if "category" in updates:
                product.category = ProductCategory(updates["category"])
            if "base_price_cents" in updates:
                product.base_price_cents = updates["base_price_cents"]
            if "tags" in updates:
                product.metadata.tags = updates["tags"]

            # Save
            await product.save()

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to update product: {str(e)}")

    # Delete Product (Soft Delete)
    async def delete_product(self, product_id: str, supplier_id: str) -> None:
        """
        Soft delete product
        Idempotent - returns success even if already deleted
        """
        try:
            product = await self.get_product(product_id, supplier_id)

            # If already deleted, return success (idempotent)
            if product.status == ProductStatus.DELETED:
                return

            # Soft delete
            await product.soft_delete()

            # Emit product.deleted event
            self._kafka.emit(
                topic=Topic.PRODUCT,
                action="deleted",
                entity_id=oid_to_str(product.id),
                data={
                    "name": product.name,
                    "supplier_id": oid_to_str(product.supplier_id),
                },
            )
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to delete product: {str(e)}")

    # Publish Product
    async def publish_product(self, product_id: str, supplier_id: str) -> Product:
        """
        Publish product (draft -> active)
        """
        try:
            # Get product
            product = await self.get_product(product_id, supplier_id)

            # Check supplier is verified
            supplier = await Supplier.get(PydanticObjectId(supplier_id))
            if supplier.verification.verification_status.value != "verified":
                raise ValueError("Supplier must be verified to publish products")

            # Check current status
            if product.status != ProductStatus.DRAFT:
                raise ValueError(f"Cannot publish product with status '{product.status.value}'")

            # Validate requirements
            self._validate_publish_requirements(product)

            # Publish
            await product.publish()

            # Emit product.published event
            self._kafka.emit(
                topic=Topic.PRODUCT,
                action="published",
                entity_id=oid_to_str(product.id),
                data={
                    "name": product.name,
                    "supplier_id": oid_to_str(product.supplier_id),
                    "category": product.category.value,
                    "base_price_cents": product.base_price_cents,
                },
            )

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to publish product: {str(e)}")

    # Discontinue Product
    async def discontinue_product(self, product_id: str, supplier_id: str) -> Product:
        """
        Discontinue product (active/out_of_stock -> discontinued)
        """
        try:
            product = await self.get_product(product_id, supplier_id)

            if product.status not in [ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]:
                raise ValueError(f"Cannot discontinue product with status '{product.status.value}'")

            product.status = ProductStatus.DISCONTINUED
            product.is_available = False
            await product.save()

            # Emit product.discontinued event
            self._kafka.emit(
                topic=Topic.PRODUCT,
                action="discontinued",
                entity_id=oid_to_str(product.id),
                data={
                    "name": product.name,
                    "supplier_id": oid_to_str(product.supplier_id),
                },
            )

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to discontinue product: {str(e)}")

    # Mark Out of Stock
    async def mark_out_of_stock(self, product_id: str, supplier_id: str) -> Product:
        """
        Mark product out of stock (active -> out_of_stock)
        """
        try:
            product = await self.get_product(product_id, supplier_id)

            if product.status != ProductStatus.ACTIVE:
                raise ValueError(f"Cannot mark product with status '{product.status.value}' as out of stock")

            product.status = ProductStatus.OUT_OF_STOCK
            product.is_available = False
            await product.save()

            # Emit product.out_of_stock event
            self._kafka.emit(
                topic=Topic.PRODUCT,
                action="out_of_stock",
                entity_id=oid_to_str(product.id),
                data={
                    "name": product.name,
                    "supplier_id": oid_to_str(product.supplier_id),
                },
            )

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to mark product out of stock: {str(e)}")

    # Restore Product
    async def restore_product(self, product_id: str, supplier_id: str) -> Product:
        """
        Restore deleted product (deleted -> draft)
        """
        try:
            product = await self.get_product(product_id, supplier_id)

            if product.status != ProductStatus.DELETED:
                raise ValueError(f"Product is not deleted (current status: '{product.status.value}')")

            product.status = ProductStatus.DRAFT
            product.deleted_at = None
            product.is_available = False
            await product.save()

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to restore product: {str(e)}")

    # Public Product Methods
    async def get_public_product(self, product_id: str) -> Optional[Product]:
        """
        Get product for public viewing (only active products)
        """
        try:
            product = await Product.find_one({
                "_id": PydanticObjectId(product_id),
                "status": ProductStatus.ACTIVE,
                "is_available": True,
                "deleted_at": None
            })

            if not product:
                raise ValueError("Product not found")

            return product
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to get public product: {str(e)}")

    async def list_public_products(
        self,
        page_size: int = 20,
        cursor: Optional[str] = None,
        category_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        min_price_cents: Optional[int] = None,
        max_price_cents: Optional[int] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List active products for public viewing
        """
        try:
            # Build query
            query = {
                "status": ProductStatus.ACTIVE,
                "is_available": True,
                "deleted_at": None
            }

            # Category filter
            if category_filter:
                query["category"] = category_filter

            # Tags filter (must have all specified tags)
            if tags_filter:
                query["metadata.tags"] = {"$all": tags_filter}

            # Price range filter
            if min_price_cents is not None or max_price_cents is not None:
                price_filter = {}
                if min_price_cents is not None:
                    price_filter["$gte"] = min_price_cents
                if max_price_cents is not None:
                    price_filter["$lte"] = max_price_cents
                query["base_price_cents"] = price_filter

            # Search
            if search:
                query["$text"] = {"$search": search}

            # Cursor pagination
            if cursor:
                query["_id"] = {"$gt": PydanticObjectId(cursor)}

            # Limit page size
            page_size = min(page_size, self.max_page_size)

            # Fetch products
            products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

            # Check if more
            has_more = len(products) > page_size
            if has_more:
                products = products[:-1]

            # Build response
            product_list = [p.to_public_dict() for p in products]

            next_cursor = str(products[-1].id) if has_more and products else None

            return {
                "products": product_list,
                "pagination": {
                    "next_cursor": next_cursor,
                    "has_more": has_more
                }
            }
        except Exception as e:
            raise Exception(f"Failed to list public products: {str(e)}")
