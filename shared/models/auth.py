"""
Authentication Token Models - Email verification and password reset tokens
"""

from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Annotated, Optional
from datetime import datetime

from src.utils.datetime_utils import utc_now


class EmailVerificationToken(Document):
    """
    Email verification token for confirming user email addresses

    Tokens are one-time use and expire after 6 hours.
    Used during registration and when adding additional emails.
    """

    # User reference
    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]

    # Token (stored as bcrypt hash)
    token_hash: Annotated[str, Field(description="Bcrypt hash of verification token")]

    # Email being verified
    email: Annotated[str, Field(description="Email address being verified")]

    # Expiration (6 hours from creation)
    expires_at: Annotated[datetime, Field(description="Token expiration timestamp")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Token creation timestamp")]

    class Settings:
        name = "email_verification_tokens"

        indexes = [
            # Query by user
            [("user_id", 1)],

            # TTL index (auto-delete expired tokens)
            [("expires_at", 1)],

            # Query by email (for resend)
            [("email", 1), ("expires_at", 1)]
        ]

    def is_expired(self) -> bool:
        """Check if token has expired"""
        return utc_now() >= self.expires_at

    def to_dict(self) -> dict:
        """Return token data as dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "email": self.email,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


class PasswordResetToken(Document):
    """
    Password reset token for secure password recovery

    Tokens are one-time use and expire after 1 hour.
    After use, the token is marked as used to prevent replay attacks.
    """

    # User reference
    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]

    # Token (stored as bcrypt hash)
    token_hash: Annotated[str, Field(description="Bcrypt hash of reset token")]

    # Expiration (1 hour from creation)
    expires_at: Annotated[datetime, Field(description="Token expiration timestamp")]

    # One-time use flag
    used: Annotated[bool, Field(default=False, description="Whether token has been used")]
    used_at: Annotated[Optional[datetime], Field(None, description="When token was used")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Token creation timestamp")]

    class Settings:
        name = "password_reset_tokens"

        indexes = [
            # Query by user
            [("user_id", 1)],

            # TTL index (auto-delete expired tokens)
            [("expires_at", 1)],

            # Query unused tokens
            [("used", 1), ("expires_at", 1)]
        ]

    def is_expired(self) -> bool:
        """Check if token has expired"""
        return utc_now() >= self.expires_at

    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)"""
        return not self.is_expired() and not self.used

    async def mark_as_used(self) -> None:
        """Mark token as used"""
        self.used = True
        self.used_at = utc_now()
        await self.save()

    def to_dict(self) -> dict:
        """Return token data as dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "expires_at": self.expires_at.isoformat(),
            "used": self.used,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat()
        }
