"""
Post Change Request Model - Change requests for globally-tagged posts

When a post has global distribution pending or approved, direct edits are blocked.
Authors must submit change requests that admins review and approve/reject.
"""

from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Optional, Dict, Any, Annotated, List, ClassVar, Set
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


class ChangeRequestStatus(str, Enum):
    """Status of a change request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestedChanges(Dict[str, Any]):
    """Type alias for requested changes dict"""
    pass


class PostChangeRequest(Document):
    """
    Change request for a globally-tagged post.

    When a post has global_distribution.status in [pending, approved],
    edits must go through this change request workflow.

    Allowed fields for change:
    - text_content
    - media
    - link_preview
    - tags

    Not allowed (require new post):
    - post_type
    - poll
    """

    # Reference to the post
    post_id: Annotated[PydanticObjectId, Field(description="Reference to the post")]

    # Author who submitted the request
    author_id: Annotated[PydanticObjectId, Field(description="User who submitted the change request")]

    # The changes being requested
    requested_changes: Annotated[Dict[str, Any], Field(description="Dict of field -> new value")]

    # Reason for the change
    reason: Annotated[str, Field(min_length=5, max_length=500, description="Reason for requesting changes")]

    # Status
    status: Annotated[ChangeRequestStatus, Field(default=ChangeRequestStatus.PENDING, description="Request status")]

    # Original values (captured when approved, before applying changes)
    original_values: Annotated[Optional[Dict[str, Any]], Field(None, description="Original values before change was applied")]

    # Review information
    reviewed_at: Annotated[Optional[datetime], Field(None, description="When the request was reviewed")]
    reviewed_by: Annotated[Optional[PydanticObjectId], Field(None, description="Admin who reviewed")]
    review_notes: Annotated[Optional[str], Field(None, max_length=1000, description="Admin notes on the review")]

    # Applied information (when approved and changes are applied)
    applied_at: Annotated[Optional[datetime], Field(None, description="When changes were applied to the post")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "post_change_requests"

        indexes = [
            # Find change requests for a post
            [("post_id", 1), ("status", 1), ("created_at", -1)],

            # Admin queue - pending requests
            [("status", 1), ("created_at", 1)],

            # Author's change requests
            [("author_id", 1), ("status", 1), ("created_at", -1)],

            # Post + status for checking pending requests
            [("post_id", 1), ("status", 1)],
        ]

    # Allowed fields that can be changed
    ALLOWED_CHANGE_FIELDS: ClassVar[Set[str]] = {"text_content", "media", "link_preview", "tags"}

    @classmethod
    def validate_requested_changes(cls, changes: Dict[str, Any]) -> None:
        """Validate that only allowed fields are being changed"""
        invalid_fields = set(changes.keys()) - cls.ALLOWED_CHANGE_FIELDS
        if invalid_fields:
            raise ValueError(f"Cannot change fields: {', '.join(invalid_fields)}. Allowed: {', '.join(cls.ALLOWED_CHANGE_FIELDS)}")

        if not changes:
            raise ValueError("No changes specified")

    def is_pending(self) -> bool:
        """Check if request is still pending"""
        return self.status == ChangeRequestStatus.PENDING

    async def approve(self, admin_id: PydanticObjectId, notes: Optional[str] = None) -> None:
        """Approve the change request (does not apply changes - that's done by service)"""
        if not self.is_pending():
            raise ValueError("Change request is not pending")

        self.status = ChangeRequestStatus.APPROVED
        self.reviewed_at = utc_now()
        self.reviewed_by = admin_id
        self.review_notes = notes
        self.updated_at = utc_now()
        await self.save()

    async def reject(self, admin_id: PydanticObjectId, notes: str) -> None:
        """Reject the change request"""
        if not self.is_pending():
            raise ValueError("Change request is not pending")

        self.status = ChangeRequestStatus.REJECTED
        self.reviewed_at = utc_now()
        self.reviewed_by = admin_id
        self.review_notes = notes
        self.updated_at = utc_now()
        await self.save()

    async def mark_applied(self, original_values: Dict[str, Any]) -> None:
        """Mark the changes as applied to the post"""
        if self.status != ChangeRequestStatus.APPROVED:
            raise ValueError("Can only mark approved requests as applied")

        self.original_values = original_values
        self.applied_at = utc_now()
        self.updated_at = utc_now()
        await self.save()

    def to_public_dict(self) -> dict:
        """Return public-safe representation"""
        return {
            "id": str(self.id),
            "post_id": str(self.post_id),
            "author_id": str(self.author_id),
            "requested_changes": self.requested_changes,
            "reason": self.reason,
            "status": self.status.value,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
            "review_notes": self.review_notes,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
