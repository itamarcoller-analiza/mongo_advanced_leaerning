"""
Community Moderation Log Model - Audit trail for admin actions on communities

Tracks all administrative actions for compliance and accountability.
"""

from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Optional, Dict, Any, Annotated
from datetime import datetime
from enum import Enum

from src.utils.datetime_utils import utc_now


class ModerationAction(str, Enum):
    """Types of moderation actions"""
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"
    DELETE = "delete"
    VERIFY = "verify"
    UNVERIFY = "unverify"
    FEATURE = "feature"
    UNFEATURE = "unfeature"
    UPDATE_OVERRIDE = "update_override"  # Admin override of community settings


class ActorType(str, Enum):
    """Type of actor performing the action"""
    ADMIN = "admin"
    SYSTEM = "system"


class CommunityModerationLog(Document):
    """
    Audit log entry for community moderation actions.

    Every admin action on a community creates a log entry
    for compliance and potential reversal.
    """

    # Community reference
    community_id: Annotated[PydanticObjectId, Field(description="Affected community")]

    # Action details
    action: Annotated[ModerationAction, Field(description="Type of moderation action")]
    reason: Annotated[str, Field(min_length=5, max_length=1000, description="Reason for action")]

    # Actor information
    actor_id: Annotated[PydanticObjectId, Field(description="Admin who performed action")]
    actor_type: Annotated[ActorType, Field(default=ActorType.ADMIN, description="Type of actor")]

    # State change tracking
    previous_status: Annotated[Optional[str], Field(None, description="Status before action")]
    new_status: Annotated[Optional[str], Field(None, description="Status after action")]

    # Additional context
    metadata: Annotated[Optional[Dict[str, Any]], Field(None, description="Additional context")]

    # Timestamp
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="When action occurred")]

    class Settings:
        name = "community_moderation_logs"

        indexes = [
            # Community history
            [("community_id", 1), ("created_at", -1)],

            # Admin audit
            [("actor_id", 1), ("created_at", -1)],

            # Action type filtering
            [("action", 1), ("created_at", -1)],

            # Recent actions
            [("created_at", -1)],
        ]

    def to_public_dict(self) -> dict:
        """Return public-safe representation"""
        return {
            "id": str(self.id),
            "community_id": str(self.community_id),
            "action": self.action.value,
            "reason": self.reason,
            "actor_id": str(self.actor_id),
            "actor_type": self.actor_type.value,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


async def log_moderation_action(
    community_id: PydanticObjectId,
    action: ModerationAction,
    actor_id: PydanticObjectId,
    reason: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> CommunityModerationLog:
    """Helper function to create a moderation log entry"""
    log_entry = CommunityModerationLog(
        community_id=community_id,
        action=action,
        actor_id=actor_id,
        reason=reason,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata
    )
    await log_entry.insert()
    return log_entry
