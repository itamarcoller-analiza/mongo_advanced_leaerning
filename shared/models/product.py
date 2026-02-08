"""
Product Model - Products created by suppliers

Products are owned by suppliers and can be featured in promotions.
Supports:
- Multi-location inventory tracking
- Product variants with individual pricing and attributes
- Package dimensions per variant
- Topic-based descriptions
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    DELETED = "deleted"


class ProductCategory(str, Enum):
    """Product categories matching supplier industry categories"""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    BEAUTY = "beauty"
    HOME_GARDEN = "home_garden"
    SPORTS_OUTDOORS = "sports_outdoors"
    FOOD_BEVERAGE = "food_beverage"
    HEALTH_WELLNESS = "health_wellness"
    TOYS_GAMES = "toys_games"
    BOOKS_MEDIA = "books_media"
    AUTOMOTIVE = "automotive"
    OTHER = "other"


class ProductCondition(str, Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED_LIKE_NEW = "used_like_new"
    USED_GOOD = "used_good"
    USED_ACCEPTABLE = "used_acceptable"


class UnitType(str, Enum):
    """Unit of measurement for the product"""
    PIECE = "piece"
    PAIR = "pair"
    SET = "set"
    BOX = "box"
    PACK = "pack"
    BUNDLE = "bundle"
    KG = "kg"
    GRAM = "gram"
    LITER = "liter"
    ML = "ml"
    METER = "meter"
    OTHER = "other"


# Embedded Schemas
class StockLocation(BaseModel):
    """Physical location where product inventory is stored"""

    location_id: Annotated[str, Field(description="Unique location identifier")]
    location_name: Annotated[str, Field(min_length=1, max_length=200, description="Warehouse/store name")]

    # Address
    street_address: Annotated[Optional[str], Field(None, max_length=200, description="Street address")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[Optional[str], Field(None, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]

    # Inventory at this location
    quantity: Annotated[int, Field(default=0, ge=0, description="Available quantity at location")]
    reserved: Annotated[int, Field(default=0, ge=0, description="Reserved quantity at location")]

    # Location-specific pricing (optional override)
    price_cents: Annotated[Optional[int], Field(None, ge=0, description="Location-specific price override")]

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()

    @property
    def available(self) -> int:
        """Calculate available quantity"""
        return max(0, self.quantity - self.reserved)


class PackageDimensions(BaseModel):
    """Package dimensions for shipping calculations"""

    width_cm: Annotated[float, Field(gt=0, description="Package width in cm")]
    height_cm: Annotated[float, Field(gt=0, description="Package height in cm")]
    depth_cm: Annotated[float, Field(gt=0, description="Package depth in cm")]
    weight_grams: Annotated[int, Field(gt=0, description="Package weight in grams")]

    @property
    def volume_cubic_cm(self) -> float:
        """Calculate package volume"""
        return self.width_cm * self.height_cm * self.depth_cm

    def to_display_weight(self, unit: str = "kg") -> float:
        """Convert weight to display unit"""
        if unit == "kg":
            return self.weight_grams / 1000
        elif unit == "lb":
            return self.weight_grams / 453.592
        return float(self.weight_grams)


class VariantAttribute(BaseModel):
    """Product variant attribute (e.g., color, size, material)"""

    attribute_name: Annotated[str, Field(min_length=1, max_length=50, description="Attribute name (e.g., 'Color', 'Size')")]
    attribute_value: Annotated[str, Field(min_length=1, max_length=100, description="Attribute value (e.g., 'Red', 'Large')")]


class ProductVariant(BaseModel):
    """Product variant with unique attributes, pricing, and inventory"""

    variant_id: Annotated[str, Field(description="Unique variant identifier")]
    variant_name: Annotated[str, Field(min_length=1, max_length=200, description="Variant display name")]

    # Variant attributes (e.g., color: red, size: large)
    attributes: Annotated[List[VariantAttribute], Field(default_factory=list, description="Variant attributes")]

    # SKU specific to this variant
    sku: Annotated[str, Field(min_length=1, max_length=100, description="Variant SKU")]

    # Pricing for this variant
    price_cents: Annotated[int, Field(ge=0, description="Variant price in cents")]
    cost_cents: Annotated[Optional[int], Field(None, ge=0, description="Variant cost in cents")]

    # Inventory for this variant (total across all locations)
    quantity: Annotated[int, Field(default=0, ge=0, description="Total quantity")]
    reserved: Annotated[int, Field(default=0, ge=0, description="Reserved quantity")]

    # Package dimensions specific to this variant
    package_dimensions: Annotated[PackageDimensions, Field(description="Shipping dimensions")]

    # Variant-specific image
    image_url: Annotated[Optional[HttpUrl], Field(None, description="Variant-specific image")]

    # Variant status
    is_active: Annotated[bool, Field(default=True, description="Is variant active")]

    @property
    def available(self) -> int:
        """Calculate available quantity"""
        return max(0, self.quantity - self.reserved)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        """Normalize SKU to uppercase"""
        return v.strip().upper()


class ProductImages(BaseModel):
    """Product-level images (different from variant images)"""

    primary_image: Annotated[HttpUrl, Field(description="Primary product image")]
    gallery_images: Annotated[List[HttpUrl], Field(default_factory=list, description="Additional product images")]
    video_url: Annotated[Optional[HttpUrl], Field(None, description="Product video URL")]

    def get_all_images(self) -> List[str]:
        """Get all image URLs"""
        return [str(self.primary_image)] + [str(img) for img in self.gallery_images]


class TopicDescription(BaseModel):
    """Topic-based product description (e.g., Features, Specifications, Care Instructions)"""

    topic: Annotated[str, Field(min_length=1, max_length=100, description="Topic name")]
    description: Annotated[str, Field(min_length=1, max_length=5000, description="Topic description")]
    display_order: Annotated[int, Field(default=0, description="Display order for topics")]


class ProductMetadata(BaseModel):
    """Product metadata and categorization"""

    # Primary identifiers
    base_sku: Annotated[str, Field(min_length=1, max_length=100, description="Base SKU (product-level, not variant)")]
    barcode: Annotated[Optional[str], Field(None, max_length=50, description="UPC/EAN/ISBN")]

    # Brand/manufacturer
    brand: Annotated[Optional[str], Field(None, max_length=100, description="Brand name")]
    manufacturer: Annotated[Optional[str], Field(None, max_length=100, description="Manufacturer")]
    model_number: Annotated[Optional[str], Field(None, max_length=100, description="Model number")]

    # Tags for search and filtering
    tags: Annotated[List[str], Field(default_factory=list, description="Product tags")]

    # Custom attributes (flexible key-value pairs)
    custom_attributes: Annotated[Dict[str, str], Field(default_factory=dict, description="Custom attributes")]

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Normalize tags and remove duplicates"""
        if not v:
            return v
        return list(set(tag.lower().strip() for tag in v if tag.strip()))

    @field_validator("base_sku")
    @classmethod
    def validate_base_sku(cls, v: str) -> str:
        """Normalize SKU"""
        return v.strip().upper()


class ProductStats(BaseModel):
    """Product statistics (denormalized for performance)"""

    view_count: Annotated[int, Field(default=0, ge=0, description="Total views")]
    favorite_count: Annotated[int, Field(default=0, ge=0, description="Times favorited")]
    purchase_count: Annotated[int, Field(default=0, ge=0, description="Total purchases")]
    active_promotion_count: Annotated[int, Field(default=0, ge=0, description="Active promotions")]

    # Ratings
    average_rating: Annotated[float, Field(default=0.0, ge=0.0, le=5.0, description="Average rating")]
    total_reviews: Annotated[int, Field(default=0, ge=0, description="Total reviews")]

    # Performance
    conversion_rate: Annotated[float, Field(default=0.0, ge=0.0, le=100.0, description="View to purchase %")]
    last_purchase_at: Annotated[Optional[datetime], Field(None, description="Last purchase timestamp")]
    last_viewed_at: Annotated[Optional[datetime], Field(None, description="Last viewed timestamp")]


class ShippingInfo(BaseModel):
    """Shipping configuration"""

    free_shipping: Annotated[bool, Field(default=False, description="Offers free shipping")]
    shipping_cost_cents: Annotated[Optional[int], Field(None, ge=0, description="Base shipping cost")]
    ships_from_country: Annotated[str, Field(min_length=2, max_length=2, description="Origin country")]
    ships_to_countries: Annotated[List[str], Field(default_factory=list, description="Destination countries")]
    estimated_delivery_days: Annotated[Optional[int], Field(None, ge=1, description="Estimated delivery")]

    @field_validator("ships_from_country")
    @classmethod
    def validate_from_country(cls, v: str) -> str:
        return v.upper()

    @field_validator("ships_to_countries")
    @classmethod
    def validate_to_countries(cls, v: List[str]) -> List[str]:
        return list(set(code.upper() for code in v))


# Main Product Document
class Product(Document):
    """
    Product model - created and managed by suppliers

    Supports:
    - Multi-location inventory tracking
    - Product variants with individual attributes and pricing
    - Topic-based descriptions
    - Package dimensions per variant
    """

    # Supplier relationship
    supplier_id: Annotated[PydanticObjectId, Field(description="Reference to Supplier")]

    # Supplier info (denormalized)
    supplier_info: Annotated[Dict[str, str], Field(default_factory=dict, description="Cached supplier data")]

    # Basic information
    name: Annotated[str, Field(min_length=1, max_length=200, description="Product name")]
    slug: Annotated[str, Field(min_length=1, max_length=250, description="URL slug")]

    # Short summary
    short_description: Annotated[Optional[str], Field(None, max_length=500, description="Brief summary")]

    # Topic-based descriptions
    topic_descriptions: Annotated[List[TopicDescription], Field(
        default_factory=list,
        description="Structured descriptions by topic"
    )]

    # Categorization
    category: Annotated[ProductCategory, Field(description="Primary category")]
    condition: Annotated[ProductCondition, Field(default=ProductCondition.NEW, description="Product condition")]

    # Unit type
    unit_type: Annotated[UnitType, Field(default=UnitType.PIECE, description="Unit of measurement")]

    # Product-level images (not variant images)
    images: Annotated[ProductImages, Field(description="Product images")]

    # Metadata (SKU, brand, tags)
    metadata: Annotated[ProductMetadata, Field(description="Product metadata")]

    # Stock locations (multiple warehouses/stores)
    stock_locations: Annotated[List[StockLocation], Field(
        default_factory=list,
        description="Physical stock locations"
    )]

    # Product variants (sizes, colors, etc.) - stored as dict with variant_name as key
    variants: Annotated[Dict[str, ProductVariant], Field(
        default_factory=dict,
        description="Product variants keyed by variant name"
    )]

    # Base price (if no variants, or default price)
    base_price_cents: Annotated[int, Field(ge=0, description="Base price in cents")]
    currency: Annotated[str, Field(default="USD", min_length=3, max_length=3, description="Currency code")]

    # Shipping
    shipping: Annotated[ShippingInfo, Field(description="Shipping configuration")]

    # Statistics
    stats: Annotated[ProductStats, Field(default_factory=ProductStats, description="Performance stats")]

    # Status
    status: Annotated[ProductStatus, Field(default=ProductStatus.DRAFT, description="Product status")]
    is_available: Annotated[bool, Field(default=False, description="Is product available for purchase")]
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Publishing
    published_at: Annotated[Optional[datetime], Field(None, description="First published timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "products"

        indexes = [
            # Supplier's products
            [("supplier_id", 1), ("status", 1), ("created_at", -1)],

            # Product discovery
            [("category", 1), ("status", 1), ("stats.average_rating", -1)],

            # Search by slug (unique)
            [("slug", 1)],

            # Product name uniqueness (trademark requirement)
            [("name", 1)],

            # Search by SKU (unique per supplier)
            [("supplier_id", 1), ("metadata.base_sku", 1)],

            # Tags (multikey index)
            [("metadata.tags", 1), ("status", 1)],

            # Variant SKU search
            [("variants.sku", 1)],

            # Stock location search
            [("stock_locations.location_id", 1)],

            # Public product listing
            [("status", 1), ("deleted_at", 1), ("is_available", 1), ("created_at", -1)],

            # Soft delete
            [("deleted_at", 1)],

            # Popular products
            [("stats.purchase_count", -1), ("status", 1)],
        ]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Normalize slug"""
        slug = v.lower().strip()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError("Slug can only contain letters, numbers, hyphens, underscores")
        return slug

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Ensure currency code is uppercase"""
        return v.upper()

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, v: Dict[str, ProductVariant]) -> Dict[str, ProductVariant]:
        """Ensure variant names match keys and SKUs are unique"""
        if not v:
            return v

        # Ensure dict keys match variant names
        for variant_name, variant in v.items():
            if variant.variant_name != variant_name:
                raise ValueError(f"Dict key '{variant_name}' must match variant_name '{variant.variant_name}'")

        # Ensure variant IDs are unique
        variant_ids = [var.variant_id for var in v.values()]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("Variant IDs must be unique")

        # Ensure SKUs are unique
        skus = [var.sku for var in v.values()]
        if len(skus) != len(set(skus)):
            raise ValueError("Variant SKUs must be unique")

        return v

    @field_validator("stock_locations")
    @classmethod
    def validate_stock_locations(cls, v: List[StockLocation]) -> List[StockLocation]:
        """Ensure location IDs are unique"""
        if not v:
            return v

        location_ids = [loc.location_id for loc in v]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("Stock location IDs must be unique")

        return v

    # Helper methods
    def get_total_inventory(self) -> int:
        """Calculate total inventory across all locations and variants"""
        total = sum(loc.quantity for loc in self.stock_locations)
        total += sum(var.quantity for var in self.variants.values())
        return total

    def get_total_available(self) -> int:
        """Calculate total available inventory"""
        total = sum(loc.available for loc in self.stock_locations)
        total += sum(var.available for var in self.variants.values())
        return total

    def is_active(self) -> bool:
        """Check if product is active"""
        return (
            self.status == ProductStatus.ACTIVE
            and self.deleted_at is None
            and self.get_total_available() > 0
        )

    def get_variant_by_name(self, variant_name: str) -> Optional[ProductVariant]:
        """Get variant by name (dict key)"""
        return self.variants.get(variant_name)

    def get_variant_by_id(self, variant_id: str) -> Optional[ProductVariant]:
        """Get variant by ID"""
        for variant in self.variants.values():
            if variant.variant_id == variant_id:
                return variant
        return None

    def get_location_by_id(self, location_id: str) -> Optional[StockLocation]:
        """Get stock location by ID"""
        for location in self.stock_locations:
            if location.location_id == location_id:
                return location
        return None

    def get_price_range(self) -> Dict[str, int]:
        """Get min and max price across variants"""
        if not self.variants:
            return {"min": self.base_price_cents, "max": self.base_price_cents}

        prices = [var.price_cents for var in self.variants.values()]
        return {"min": min(prices), "max": max(prices)}

    def add_topic_description(self, topic: str, description: str, order: int = 0) -> None:
        """Add or update a topic description"""
        # Check if topic already exists
        for td in self.topic_descriptions:
            if td.topic == topic:
                td.description = description
                td.display_order = order
                return

        # Add new topic
        self.topic_descriptions.append(
            TopicDescription(topic=topic, description=description, display_order=order)
        )

    def get_topic_description(self, topic: str) -> Optional[str]:
        """Get description for a specific topic"""
        for td in self.topic_descriptions:
            if td.topic == topic:
                return td.description
        return None

    async def publish(self) -> None:
        """Publish product"""
        if self.status == ProductStatus.DRAFT:
            self.status = ProductStatus.ACTIVE
            self.is_available = True
            if self.published_at is None:
                self.published_at = utc_now()
            self.updated_at = utc_now()
            self.version += 1
            await self.save()

    async def soft_delete(self) -> None:
        """Soft delete product"""
        self.deleted_at = utc_now()
        self.status = ProductStatus.DELETED
        self.is_available = False
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def reserve_variant_inventory(self, variant_name: str, quantity: int) -> bool:
        """Reserve inventory for a specific variant by name"""
        variant = self.variants.get(variant_name)
        if not variant or variant.available < quantity:
            return False

        variant.reserved += quantity
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def reserve_variant_inventory_by_id(self, variant_id: str, quantity: int) -> bool:
        """Reserve inventory for a specific variant by ID"""
        variant = self.get_variant_by_id(variant_id)
        if not variant or variant.available < quantity:
            return False

        variant.reserved += quantity
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def reserve_location_inventory(self, location_id: str, quantity: int) -> bool:
        """Reserve inventory at a specific location"""
        location = self.get_location_by_id(location_id)
        if not location or location.available < quantity:
            return False

        location.reserved += quantity
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def release_variant_inventory(self, variant_name: str, quantity: int) -> bool:
        """Release reserved inventory for a specific variant by name"""
        variant = self.variants.get(variant_name)
        if not variant:
            return False

        variant.reserved = max(0, variant.reserved - quantity)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def release_variant_inventory_by_id(self, variant_id: str, quantity: int) -> bool:
        """Release reserved inventory for a specific variant by ID"""
        variant = self.get_variant_by_id(variant_id)
        if not variant:
            return False

        variant.reserved = max(0, variant.reserved - quantity)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    async def release_location_inventory(self, location_id: str, quantity: int) -> bool:
        """Release reserved inventory at a specific location"""
        location = self.get_location_by_id(location_id)
        if not location:
            return False

        location.reserved = max(0, location.reserved - quantity)
        self.updated_at = utc_now()
        self.version += 1
        await self.save()
        return True

    def to_public_dict(self) -> dict:
        """Return public-safe product data"""
        price_range = self.get_price_range()

        return {
            "id": str(self.id),
            "supplier": self.supplier_info,
            "name": self.name,
            "slug": self.slug,
            "short_description": self.short_description,
            "topic_descriptions": [
                {"topic": td.topic, "description": td.description}
                for td in sorted(self.topic_descriptions, key=lambda x: x.display_order)
            ],
            "category": self.category.value,
            "condition": self.condition.value,
            "unit_type": self.unit_type.value,
            "images": {
                "primary": str(self.images.primary_image),
                "gallery": [str(img) for img in self.images.gallery_images],
                "video": str(self.images.video_url) if self.images.video_url else None
            },
            "price": {
                "base": self.base_price_cents / 100,
                "min": price_range["min"] / 100,
                "max": price_range["max"] / 100,
                "currency": self.currency
            },
            "variants": {
                variant_name: {
                    "id": var.variant_id,
                    "name": var.variant_name,
                    "sku": var.sku,
                    "attributes": [
                        {"name": attr.attribute_name, "value": attr.attribute_value}
                        for attr in var.attributes
                    ],
                    "price": var.price_cents / 100,
                    "available": var.available,
                    "image": str(var.image_url) if var.image_url else None,
                    "package": {
                        "width_cm": var.package_dimensions.width_cm,
                        "height_cm": var.package_dimensions.height_cm,
                        "depth_cm": var.package_dimensions.depth_cm,
                        "weight_kg": var.package_dimensions.to_display_weight("kg")
                    }
                }
                for variant_name, var in self.variants.items() if var.is_active
            },
            "stock_locations": [
                {
                    "id": loc.location_id,
                    "name": loc.location_name,
                    "city": loc.city,
                    "country": loc.country,
                    "available": loc.available
                }
                for loc in self.stock_locations
            ],
            "tags": self.metadata.tags,
            "stats": {
                "average_rating": self.stats.average_rating,
                "total_reviews": self.stats.total_reviews,
                "purchase_count": self.stats.purchase_count
            },
            "status": self.status.value,
            "created_at": self.created_at.isoformat()
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
