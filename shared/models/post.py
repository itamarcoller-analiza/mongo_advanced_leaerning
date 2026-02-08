"""
Post Model - Social content created by users and leaders

Posts are social feed content that can appear in:
- Global feed (main page)
- Community feeds (specific communities)

Posts are referenced by feed_items for unified feed display.

Permissions:
- Any community member can create posts
- Only the leader can remove posts or post promotions
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


# Enums
class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    DELETED = "deleted"


class GlobalDistributionStatus(str, Enum):
    """Status of global distribution request"""
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class PostType(str, Enum):
    """Type of post content"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    POLL = "poll"


class AuthorType(str, Enum):
    """Who created the post"""
    USER = "user"
    LEADER = "leader"


# Embedded Schemas
class PostAuthor(BaseModel):
    """Post author information (denormalized)"""

    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]
    display_name: Annotated[str, Field(description="Author display name")]
    avatar: Annotated[str, Field(description="Author avatar URL")]
    author_type: Annotated[AuthorType, Field(description="User or leader")]
    is_verified: Annotated[bool, Field(default=False, description="Verified badge")]


class MediaAttachment(BaseModel):
    """Media attachment (image, video)"""

    media_type: Annotated[str, Field(description="image, video, gif")]
    media_url: Annotated[HttpUrl, Field(description="Media file URL")]
    thumbnail_url: Annotated[Optional[HttpUrl], Field(None, description="Thumbnail for videos")]
    width: Annotated[Optional[int], Field(None, ge=0, description="Media width in pixels")]
    height: Annotated[Optional[int], Field(None, ge=0, description="Media height in pixels")]
    duration_seconds: Annotated[Optional[int], Field(None, ge=0, description="Video duration")]
    size_bytes: Annotated[Optional[int], Field(None, ge=0, description="File size")]


class LinkPreview(BaseModel):
    """Preview for shared links"""

    url: Annotated[HttpUrl, Field(description="Shared URL")]
    title: Annotated[str, Field(max_length=200, description="Link title")]
    description: Annotated[Optional[str], Field(None, max_length=500, description="Link description")]
    image: Annotated[Optional[HttpUrl], Field(None, description="Preview image")]
    site_name: Annotated[Optional[str], Field(None, description="Site name")]


class PollOption(BaseModel):
    """Poll option"""

    option_id: Annotated[str, Field(description="Unique option identifier")]
    option_text: Annotated[str, Field(max_length=100, description="Option text")]
    vote_count: Annotated[int, Field(default=0, ge=0, description="Number of votes")]


class PollData(BaseModel):
    """Poll data for poll-type posts"""

    question: Annotated[str, Field(max_length=300, description="Poll question")]
    options: Annotated[List[PollOption], Field(min_length=2, max_length=6, description="Poll options")]
    allows_multiple_votes: Annotated[bool, Field(default=False, description="Allow multiple selections")]
    ends_at: Annotated[Optional[datetime], Field(None, description="Poll end date")]
    total_votes: Annotated[int, Field(default=0, ge=0, description="Total votes cast")]


class GlobalDistribution(BaseModel):
    """Global distribution state for a post"""

    requested: Annotated[bool, Field(default=False, description="Whether global distribution was requested")]
    status: Annotated[GlobalDistributionStatus, Field(default=GlobalDistributionStatus.NONE, description="Distribution status")]
    requested_at: Annotated[Optional[datetime], Field(None, description="When distribution was requested")]
    reviewed_at: Annotated[Optional[datetime], Field(None, description="When reviewed by admin")]
    reviewed_by: Annotated[Optional[PydanticObjectId], Field(None, description="Admin who reviewed")]
    rejection_reason: Annotated[Optional[str], Field(None, max_length=1000, description="Reason for rejection")]
    revoked_at: Annotated[Optional[datetime], Field(None, description="When approval was revoked")]
    revoked_by: Annotated[Optional[PydanticObjectId], Field(None, description="Admin who revoked")]
    revoke_reason: Annotated[Optional[str], Field(None, max_length=1000, description="Reason for revocation")]


class PostStats(BaseModel):
    """Post engagement statistics"""

    view_count: Annotated[int, Field(default=0, ge=0, description="Total views")]
    like_count: Annotated[int, Field(default=0, ge=0, description="Total likes")]
    comment_count: Annotated[int, Field(default=0, ge=0, description="Total comments")]
    share_count: Annotated[int, Field(default=0, ge=0, description="Total shares")]
    save_count: Annotated[int, Field(default=0, ge=0, description="Times saved/bookmarked")]
    engagement_rate: Annotated[float, Field(default=0.0, ge=0.0, description="Engagement rate %")]
    last_comment_at: Annotated[Optional[datetime], Field(None, description="Last comment timestamp")]


class PostMentions(BaseModel):
    """User mentions in the post"""

    user_id: Annotated[PydanticObjectId, Field(description="Mentioned user ID")]
    display_name: Annotated[str, Field(description="Mentioned user name")]


# Main Post Document
class Post(Document):
    """
    Post model - social content for feeds

    Posts are the full content documents.
    They are referenced by feed_items for unified feed display.

    Permissions:
    - Any community member can post
    - Only the post author can edit their own post
    - Only the community leader can remove any post
    """

    # Post type
    post_type: Annotated[PostType, Field(description="Type of post")]

    # Author
    author: Annotated[PostAuthor, Field(description="Post author information")]

    # Content
    text_content: Annotated[str, Field(max_length=5000, description="Post text content")]

    # Media attachments (images, videos)
    media: Annotated[List[MediaAttachment], Field(default_factory=list, description="Media attachments")]

    # Link preview (if sharing a link)
    link_preview: Annotated[Optional[LinkPreview], Field(None, description="Shared link preview")]

    # Poll data (if post is a poll)
    poll: Annotated[Optional[PollData], Field(None, description="Poll data")]

    # Community (optional - null if posted to global feed)
    community_id: Annotated[Optional[PydanticObjectId], Field(None, description="Community where posted")]
    community_name: Annotated[Optional[str], Field(None, description="Community name (denormalized)")]

    # Tags and mentions
    tags: Annotated[List[str], Field(default_factory=list, description="Hashtags")]
    mentions: Annotated[List[PostMentions], Field(default_factory=list, description="User mentions")]

    # Statistics
    stats: Annotated[PostStats, Field(default_factory=PostStats, description="Engagement stats")]

    # Status
    status: Annotated[PostStatus, Field(default=PostStatus.DRAFT, description="Post status")]
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Global distribution
    global_distribution: Annotated[GlobalDistribution, Field(default_factory=GlobalDistribution, description="Global distribution state")]

    # Pinned (only leaders can pin)
    is_pinned: Annotated[bool, Field(default=False, description="Pinned in community")]
    pinned_at: Annotated[Optional[datetime], Field(None, description="When pinned")]
    pinned_by: Annotated[Optional[PydanticObjectId], Field(None, description="Who pinned")]

    # Hidden (moderation)
    hidden_at: Annotated[Optional[datetime], Field(None, description="When hidden")]
    hidden_by: Annotated[Optional[PydanticObjectId], Field(None, description="Who hid the post")]
    hidden_reason: Annotated[Optional[str], Field(None, max_length=500, description="Reason for hiding")]

    # Published timestamp (different from created_at)
    published_at: Annotated[Optional[datetime], Field(None, description="Publication timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "posts"

        indexes = [
            # Author's posts
            [("author.user_id", 1), ("status", 1), ("created_at", -1)],

            # Community posts
            [("community_id", 1), ("status", 1), ("published_at", -1)],

            # Global posts (community_id is null)
            [("community_id", 1), ("status", 1), ("created_at", -1)],

            # Published posts
            [("status", 1), ("published_at", -1)],

            # Tags (multikey index)
            [("tags", 1), ("status", 1)],

            # Mentions (multikey index)
            [("mentions.user_id", 1)],

            # Popular posts
            [("stats.like_count", -1), ("status", 1)],
            [("stats.engagement_rate", -1), ("status", 1)],

            # Pinned posts
            [("community_id", 1), ("is_pinned", 1), ("status", 1)],

            # Soft delete
            [("deleted_at", 1)],

            # Global distribution
            [("global_distribution.status", 1), ("status", 1), ("published_at", -1)],
            [("global_distribution.status", 1), ("global_distribution.requested_at", 1)],
        ]

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Normalize tags and remove duplicates"""
        if not v:
            return v
        # Remove # symbol if present, lowercase, remove duplicates
        normalized = [tag.lstrip('#').lower().strip() for tag in v if tag.strip()]
        return list(set(normalized))

    @field_validator("text_content")
    @classmethod
    def validate_text_content(cls, v: str) -> str:
        """Ensure text content is not empty"""
        if not v.strip():
            raise ValueError("Post text content cannot be empty")
        return v.strip()

    @field_validator("poll")
    @classmethod
    def validate_poll(cls, v: Optional[PollData], info) -> Optional[PollData]:
        """Ensure poll posts have poll data"""
        post_type = info.data.get("post_type")
        if post_type == PostType.POLL and not v:
            raise ValueError("Poll posts must have poll data")
        if post_type != PostType.POLL and v:
            raise ValueError("Only poll posts can have poll data")
        return v

    # Helper methods
    def is_published(self) -> bool:
        """Check if post is published"""
        return self.status == PostStatus.PUBLISHED and self.deleted_at is None

    def is_in_community(self) -> bool:
        """Check if post belongs to a community"""
        return self.community_id is not None

    def can_be_edited_by(self, user_id: PydanticObjectId) -> bool:
        """Check if user can edit this post (only author)"""
        return self.author.user_id == user_id

    def can_be_deleted_by(self, user_id: PydanticObjectId, is_community_leader: bool = False) -> bool:
        """Check if user can delete this post (author or community leader)"""
        # Author can always delete their own post
        if self.author.user_id == user_id:
            return True

        # Community leader can delete any post in their community
        if self.is_in_community() and is_community_leader:
            return True

        return False

    def get_preview_text(self, max_length: int = 200) -> str:
        """Get preview text for feed items"""
        if len(self.text_content) <= max_length:
            return self.text_content
        return self.text_content[:max_length] + "..."

    def get_primary_image(self) -> Optional[str]:
        """Get primary image for preview"""
        # Check media attachments first
        for media in self.media:
            if media.media_type == "image":
                return str(media.media_url)

        # Check link preview
        if self.link_preview and self.link_preview.image:
            return str(self.link_preview.image)

        return None

    async def publish(self) -> None:
        """Publish the post"""
        if self.status != PostStatus.DRAFT:
            raise ValueError("Only draft posts can be published")

        self.status = PostStatus.PUBLISHED
        self.published_at = utc_now()
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def hide_post(self, actor_id: PydanticObjectId, reason: Optional[str] = None) -> None:
        """Hide the post (only leader can hide)"""
        if self.status != PostStatus.PUBLISHED:
            raise ValueError("Can only hide published posts")
        self.status = PostStatus.HIDDEN
        self.hidden_at = utc_now()
        self.hidden_by = actor_id
        self.hidden_reason = reason
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def unhide_post(self) -> None:
        """Unhide a hidden post"""
        if self.status != PostStatus.HIDDEN:
            raise ValueError("Post is not hidden")
        self.status = PostStatus.PUBLISHED
        self.hidden_at = None
        self.hidden_by = None
        self.hidden_reason = None
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def soft_delete(self) -> None:
        """Soft delete post"""
        self.deleted_at = utc_now()
        self.status = PostStatus.DELETED
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def pin_post(self, actor_id: PydanticObjectId) -> None:
        """Pin post in community (only leader can pin)"""
        if not self.is_in_community():
            raise ValueError("Only community posts can be pinned")
        if self.status != PostStatus.PUBLISHED:
            raise ValueError("Can only pin published posts")

        self.is_pinned = True
        self.pinned_at = utc_now()
        self.pinned_by = actor_id
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def unpin_post(self) -> None:
        """Unpin post"""
        if not self.is_pinned:
            raise ValueError("Post is not pinned")
        self.is_pinned = False
        self.pinned_at = None
        self.pinned_by = None
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    # Global Distribution Methods
    def is_globally_tagged(self) -> bool:
        """Check if post is globally tagged (pending or approved) - requires change request for edits"""
        return self.global_distribution.status in [
            GlobalDistributionStatus.PENDING,
            GlobalDistributionStatus.APPROVED
        ]

    def is_globally_distributed(self) -> bool:
        """Check if post is approved for global distribution"""
        return self.global_distribution.status == GlobalDistributionStatus.APPROVED

    def can_request_global_distribution(self) -> bool:
        """Check if global distribution can be requested"""
        if self.status != PostStatus.PUBLISHED:
            return False
        if not self.is_in_community():
            return False  # Only community posts can request global distribution
        # Can request if status is none, rejected, or revoked
        return self.global_distribution.status in [
            GlobalDistributionStatus.NONE,
            GlobalDistributionStatus.REJECTED,
            GlobalDistributionStatus.REVOKED
        ]

    async def request_global_distribution(self) -> None:
        """Request global distribution for this post"""
        if not self.can_request_global_distribution():
            raise ValueError("Cannot request global distribution for this post")

        self.global_distribution.requested = True
        self.global_distribution.status = GlobalDistributionStatus.PENDING
        self.global_distribution.requested_at = utc_now()
        # Clear previous rejection/revoke info
        self.global_distribution.rejection_reason = None
        self.global_distribution.revoked_at = None
        self.global_distribution.revoked_by = None
        self.global_distribution.revoke_reason = None
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def approve_global_distribution(self, admin_id: PydanticObjectId) -> None:
        """Approve global distribution (admin only)"""
        if self.global_distribution.status != GlobalDistributionStatus.PENDING:
            raise ValueError("Post is not pending global distribution approval")

        self.global_distribution.status = GlobalDistributionStatus.APPROVED
        self.global_distribution.reviewed_at = utc_now()
        self.global_distribution.reviewed_by = admin_id
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def reject_global_distribution(self, admin_id: PydanticObjectId, reason: str) -> None:
        """Reject global distribution (admin only)"""
        if self.global_distribution.status != GlobalDistributionStatus.PENDING:
            raise ValueError("Post is not pending global distribution approval")

        self.global_distribution.status = GlobalDistributionStatus.REJECTED
        self.global_distribution.reviewed_at = utc_now()
        self.global_distribution.reviewed_by = admin_id
        self.global_distribution.rejection_reason = reason
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def revoke_global_distribution(self, admin_id: PydanticObjectId, reason: str) -> None:
        """Revoke previously approved global distribution (admin only)"""
        if self.global_distribution.status != GlobalDistributionStatus.APPROVED:
            raise ValueError("Post is not globally approved")

        self.global_distribution.status = GlobalDistributionStatus.REVOKED
        self.global_distribution.revoked_at = utc_now()
        self.global_distribution.revoked_by = admin_id
        self.global_distribution.revoke_reason = reason
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def set_approved_global_distribution(self, admin_id: PydanticObjectId) -> None:
        """Set global distribution to approved (for admin-created global posts)"""
        self.global_distribution.requested = True
        self.global_distribution.status = GlobalDistributionStatus.APPROVED
        self.global_distribution.requested_at = utc_now()
        self.global_distribution.reviewed_at = utc_now()
        self.global_distribution.reviewed_by = admin_id
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    async def increment_views(self) -> None:
        """Increment view counter"""
        self.stats.view_count += 1
        self.update_engagement_rate()
        await self.save()

    async def increment_likes(self) -> None:
        """Increment like counter"""
        self.stats.like_count += 1
        self.update_engagement_rate()
        await self.save()

    async def decrement_likes(self) -> None:
        """Decrement like counter (unlike)"""
        self.stats.like_count = max(0, self.stats.like_count - 1)
        self.update_engagement_rate()
        await self.save()

    async def increment_comments(self) -> None:
        """Increment comment counter"""
        self.stats.comment_count += 1
        self.stats.last_comment_at = utc_now()
        self.update_engagement_rate()
        await self.save()

    async def increment_shares(self) -> None:
        """Increment share counter"""
        self.stats.share_count += 1
        self.update_engagement_rate()
        await self.save()

    async def increment_saves(self) -> None:
        """Increment save counter"""
        self.stats.save_count += 1
        await self.save()

    def update_engagement_rate(self) -> None:
        """Calculate engagement rate"""
        if self.stats.view_count > 0:
            engagements = (
                self.stats.like_count +
                self.stats.comment_count +
                self.stats.share_count
            )
            self.stats.engagement_rate = (engagements / self.stats.view_count) * 100

    async def vote_poll(self, option_id: str) -> None:
        """Record a poll vote"""
        if not self.poll:
            raise ValueError("Post is not a poll")

        # Check if poll has ended
        if self.poll.ends_at and utc_now() > self.poll.ends_at:
            raise ValueError("Poll has ended")

        # Find and increment option
        option_found = False
        for option in self.poll.options:
            if option.option_id == option_id:
                option.vote_count += 1
                option_found = True
                break

        if not option_found:
            raise ValueError("Invalid poll option")

        # Update total votes
        self.poll.total_votes += 1
        self.updated_at = utc_now()
        self.version += 1
        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe post data"""
        result = {
            "id": str(self.id),
            "type": self.post_type.value,
            "author": {
                "id": str(self.author.user_id),
                "name": self.author.display_name,
                "avatar": self.author.avatar,
                "type": self.author.author_type.value,
                "is_verified": self.author.is_verified
            },
            "content": self.text_content,
            "media": [
                {
                    "type": media.media_type,
                    "url": str(media.media_url),
                    "thumbnail": str(media.thumbnail_url) if media.thumbnail_url else None,
                    "width": media.width,
                    "height": media.height
                }
                for media in self.media
            ],
            "tags": self.tags,
            "mentions": [
                {"id": str(m.user_id), "name": m.display_name}
                for m in self.mentions
            ],
            "stats": {
                "views": self.stats.view_count,
                "likes": self.stats.like_count,
                "comments": self.stats.comment_count,
                "shares": self.stats.share_count,
                "saves": self.stats.save_count,
                "engagement_rate": round(self.stats.engagement_rate, 2)
            },
            "is_pinned": self.is_pinned,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat()
        }

        # Add community info if posted in community
        if self.community_id:
            result["community"] = {
                "id": str(self.community_id),
                "name": self.community_name
            }

        # Add link preview if present
        if self.link_preview:
            result["link_preview"] = {
                "url": str(self.link_preview.url),
                "title": self.link_preview.title,
                "description": self.link_preview.description,
                "image": str(self.link_preview.image) if self.link_preview.image else None
            }

        # Add poll data if present
        if self.poll:
            result["poll"] = {
                "question": self.poll.question,
                "options": [
                    {
                        "id": opt.option_id,
                        "text": opt.option_text,
                        "votes": opt.vote_count,
                        "percentage": round((opt.vote_count / self.poll.total_votes * 100), 1) if self.poll.total_votes > 0 else 0
                    }
                    for opt in self.poll.options
                ],
                "total_votes": self.poll.total_votes,
                "ends_at": self.poll.ends_at.isoformat() if self.poll.ends_at else None,
                "allows_multiple": self.poll.allows_multiple_votes
            }

        return result

    def to_feed_preview(self) -> dict:
        """Return minimal data for feed_items preview"""
        return {
            "title": None,  # Posts don't have titles
            "content_snippet": self.get_preview_text(150),
            "image": self.get_primary_image(),
            "author": {
                "id": str(self.author.user_id),
                "name": self.author.display_name,
                "avatar": self.author.avatar,
                "type": self.author.author_type.value
            },
            "stats": {
                "likes": self.stats.like_count,
                "comments": self.stats.comment_count
            }
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
