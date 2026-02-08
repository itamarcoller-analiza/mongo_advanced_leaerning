"""Kafka topic and event type definitions."""


class Topic:
    """Kafka topics."""
    USER = "user"
    ORDER = "order"
    POST = "post"
    PRODUCT = "product"
    PROMOTION = "promotion"
    COMMUNITY = "community"
    SUPPLIER = "supplier"

    @classmethod
    def all(cls) -> list[str]:
        """Return all topics."""
        return [
            cls.USER,
            cls.ORDER,
            cls.POST,
            cls.PRODUCT,
            cls.PROMOTION,
            cls.COMMUNITY,
            cls.SUPPLIER,
        ]


class EventType:
    """Event types (topic.action)."""

    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_EMAIL_VERIFIED = "user.email_verified"
    USER_ACCOUNT_LOCKED = "user.account_locked"
    USER_PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    USER_PASSWORD_RESET = "user.password_reset"

    # Order events
    ORDER_CREATED = "order.created"
    ORDER_COMPLETED = "order.completed"
    ORDER_CANCELLED = "order.cancelled"

    # Post events
    POST_CREATED = "post.created"
    POST_DELETED = "post.deleted"
    POST_HIDDEN = "post.hidden"
    POST_GLOBAL_DISTRIBUTION_APPROVED = "post.global_distribution_approved"

    # Product events
    PRODUCT_CREATED = "product.created"
    PRODUCT_PUBLISHED = "product.published"
    PRODUCT_DISCONTINUED = "product.discontinued"
    PRODUCT_OUT_OF_STOCK = "product.out_of_stock"
    PRODUCT_DELETED = "product.deleted"

    # Promotion events
    PROMOTION_CREATED = "promotion.created"
    PROMOTION_SUBMITTED = "promotion.submitted"
    PROMOTION_APPROVED = "promotion.approved"
    PROMOTION_REJECTED = "promotion.rejected"
    PROMOTION_PAUSED = "promotion.paused"
    PROMOTION_RESUMED = "promotion.resumed"
    PROMOTION_CANCELLED = "promotion.cancelled"
    PROMOTION_ENDED = "promotion.ended"

    # Community events
    COMMUNITY_CREATED = "community.created"
    COMMUNITY_MEMBER_JOINED = "community.member_joined"
    COMMUNITY_MEMBER_LEFT = "community.member_left"
    COMMUNITY_SUSPENDED = "community.suspended"
    COMMUNITY_VERIFIED = "community.verified"

    # Supplier events
    SUPPLIER_REGISTERED = "supplier.registered"
    SUPPLIER_LOGIN = "supplier.login"
    SUPPLIER_DOCUMENTS_SUBMITTED = "supplier.documents_submitted"
