"""
FeedItem Model - Unified feed collection

FeedItems are lightweight references to posts and promotions that appear in feeds.
This collection enables:
- Fast feed queries without lookups
- Time-bucketed collections (feed_items_2025_02)
- TTL auto-deletion of old items
- Efficient pagination

Strategy:
1. Posts and Promotions are stored in their own collections (full data)
2. FeedItems reference them with denormalized preview data
3. Feed queries hit feed_items only (fast)
4. Full content fetched on-demand when user clicks
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Annotated
from datetime import datetime, timedelta
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class FeedItemType(str, Enum):
    POST = "post"
    PROMOTION = "promotion"


class FeedType(str, Enum):
    GLOBAL = "global"
    COMMUNITY = "community"


class FeedItemStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    DELETED = "deleted"


# Embedded Schemas
class FeedItemAuthor(BaseModel):
    """Author information for feed preview"""

    id: Annotated[PydanticObjectId, Field(description="Author user/supplier ID")]
    name: Annotated[str, Field(description="Display name")]
    avatar: Annotated[Optional[str], Field(None, description="Avatar URL")]
    type: Annotated[str, Field(description="user, leader, or supplier")]


class FeedItemPreview(BaseModel):
    """Preview data for fast feed rendering (no lookups needed)"""

    title: Annotated[Optional[str], Field(None, max_length=200, description="Title (promotions have titles, posts don't)")]
    content_snippet: Annotated[str, Field(max_length=300, description="Text preview")]
    image: Annotated[Optional[str], Field(None, description="Primary image URL")]
    author: Annotated[FeedItemAuthor, Field(description="Author information")]
    stats: Annotated[Dict[str, int], Field(default_factory=dict, description="Quick stats (likes, comments)")]


# Main FeedItem Document
class FeedItem(Document):
    """
    FeedItem model - unified feed with references to posts and promotions

    This is the collection queried for feed display.
    Contains minimal denormalized data for fast scrolling.
    Full content is fetched on-demand from posts or promotions collections.

    Collection naming: feed_items_YYYY_MM (time-bucketed)
    Example: feed_items_2025_02, feed_items_2025_03
    """

    # Item type and reference
    item_type: Annotated[FeedItemType, Field(description="Type of content (post or promotion)")]
    item_id: Annotated[PydanticObjectId, Field(description="Reference to Post or Promotion document")]

    # Feed location
    feed_type: Annotated[FeedType, Field(description="Global or community feed")]
    community_id: Annotated[Optional[PydanticObjectId], Field(None, description="Community ID (null if feed_type=global)")]

    # Denormalized preview (for 80% of feed scrolling, no lookup needed)
    preview: Annotated[FeedItemPreview, Field(description="Preview data for fast rendering")]

    # Status
    status: Annotated[FeedItemStatus, Field(default=FeedItemStatus.ACTIVE, description="Feed item status")]

    # TTL for auto-deletion
    expires_at: Annotated[datetime, Field(description="Auto-delete after this date")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="When item was added to feed")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update")]

    class Settings:
        # Collection name will be dynamic: feed_items_YYYY_MM
        # This is the base name
        name = "feed_items"

        indexes = [
            # Main feed query (MOST CRITICAL INDEX)
            [("feed_type", 1), ("status", 1), ("created_at", -1), ("_id", -1)],

            # Community feed query
            [("community_id", 1), ("status", 1), ("created_at", -1), ("_id", -1)],

            # Item lookup (for updates/deletes)
            [("item_type", 1), ("item_id", 1)],

            # TTL index (auto-delete old items)
            [("expires_at", 1)],
        ]

    @field_validator("community_id")
    @classmethod
    def validate_community_id(cls, v: Optional[PydanticObjectId], info) -> Optional[PydanticObjectId]:
        """Ensure community_id is set for community feeds"""
        feed_type = info.data.get("feed_type")

        if feed_type == FeedType.COMMUNITY and not v:
            raise ValueError("community_id required for community feeds")

        if feed_type == FeedType.GLOBAL and v:
            raise ValueError("community_id must be null for global feeds")

        return v

    @field_validator("expires_at", mode="before")
    @classmethod
    def set_default_expiration(cls, v):
        """Set default expiration to 90 days if not provided"""
        if v is None:
            return utc_now() + timedelta(days=90)
        return v

    # Helper methods
    def is_active(self) -> bool:
        """Check if feed item is active"""
        return (
            self.status == FeedItemStatus.ACTIVE
            and utc_now() < self.expires_at
        )

    def is_expired(self) -> bool:
        """Check if feed item has expired"""
        return utc_now() >= self.expires_at

    def is_post(self) -> bool:
        """Check if this is a post"""
        return self.item_type == FeedItemType.POST

    def is_promotion(self) -> bool:
        """Check if this is a promotion"""
        return self.item_type == FeedItemType.PROMOTION

    async def hide_item(self) -> None:
        """Hide the feed item"""
        self.status = FeedItemStatus.HIDDEN
        self.updated_at = utc_now()
        await self.save()

    async def delete_item(self) -> None:
        """Mark feed item as deleted"""
        self.status = FeedItemStatus.DELETED
        self.updated_at = utc_now()
        await self.save()

    async def extend_expiration(self, days: int = 30) -> None:
        """Extend expiration date"""
        self.expires_at = self.expires_at + timedelta(days=days)
        self.updated_at = utc_now()
        await self.save()

    def to_dict(self) -> dict:
        """Return feed item as dictionary"""
        return {
            "id": str(self.id),
            "item_type": self.item_type.value,
            "item_id": str(self.item_id),
            "feed_type": self.feed_type.value,
            "community_id": str(self.community_id) if self.community_id else None,
            "preview": {
                "title": self.preview.title,
                "content_snippet": self.preview.content_snippet,
                "image": self.preview.image,
                "author": {
                    "id": str(self.preview.author.id),
                    "name": self.preview.author.name,
                    "avatar": self.preview.author.avatar,
                    "type": self.preview.author.type
                },
                "stats": self.preview.stats
            },
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
