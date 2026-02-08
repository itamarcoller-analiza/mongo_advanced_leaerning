"""
Community Join Request Model - Join requests for private/approval-required communities

When a community requires approval (private visibility or requires_approval=true),
users must submit join requests that owners/admins review.
"""

from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Optional, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


class JoinRequestStatus(str, Enum):
    """Status of a join request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CommunityJoinRequest(Document):
    """
    Join request for a community requiring approval.

    Created when:
    - Community visibility is private
    - Community has requires_approval=true
    """

    # References
    community_id: Annotated[PydanticObjectId, Field(description="Community being requested to join")]
    user_id: Annotated[PydanticObjectId, Field(description="User requesting to join")]

    # Request details
    message: Annotated[Optional[str], Field(None, max_length=500, description="User's join message")]
    status: Annotated[JoinRequestStatus, Field(default=JoinRequestStatus.PENDING, description="Request status")]

    # Review information
    reviewed_by: Annotated[Optional[PydanticObjectId], Field(None, description="Owner/admin who reviewed")]
    reviewed_at: Annotated[Optional[datetime], Field(None, description="When reviewed")]
    review_notes: Annotated[Optional[str], Field(None, max_length=500, description="Review notes")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Request creation time")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update time")]

    class Settings:
        name = "community_join_requests"

        indexes = [
            # Owner's pending queue for a community
            [("community_id", 1), ("status", 1), ("created_at", 1)],

            # User's requests
            [("user_id", 1), ("status", 1)],

            # Check for existing pending request
            [("community_id", 1), ("user_id", 1), ("status", 1)],

            # Admin global pending queue
            [("status", 1), ("created_at", 1)],
        ]

    def is_pending(self) -> bool:
        """Check if request is still pending"""
        return self.status == JoinRequestStatus.PENDING

    async def approve(self, reviewer_id: PydanticObjectId, notes: Optional[str] = None) -> None:
        """Approve the join request"""
        if not self.is_pending():
            raise ValueError("Join request is not pending")

        self.status = JoinRequestStatus.APPROVED
        self.reviewed_by = reviewer_id
        self.reviewed_at = utc_now()
        self.review_notes = notes
        self.updated_at = utc_now()
        await self.save()

    async def reject(self, reviewer_id: PydanticObjectId, notes: str) -> None:
        """Reject the join request"""
        if not self.is_pending():
            raise ValueError("Join request is not pending")

        self.status = JoinRequestStatus.REJECTED
        self.reviewed_by = reviewer_id
        self.reviewed_at = utc_now()
        self.review_notes = notes
        self.updated_at = utc_now()
        await self.save()

    async def cancel(self) -> None:
        """Cancel the join request (by user)"""
        if not self.is_pending():
            raise ValueError("Join request is not pending")

        self.status = JoinRequestStatus.CANCELLED
        self.updated_at = utc_now()
        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe representation"""
        return {
            "id": str(self.id),
            "community_id": str(self.community_id),
            "user_id": str(self.user_id),
            "message": self.message,
            "status": self.status.value,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
