"""Authentication events consumer."""

import logging

from shared.kafka.topics import EventType


logger = logging.getLogger(__name__)


class AuthConsumer:
    """Consumer for authentication events from user topic."""

    def handle_user_registered(self, event: dict) -> None:
        """Handle user.registered event."""
        data = event.get("data", {})
        contact = data.get("contact_info", {})
        profile = data.get("profile", {})
        logger.info(
            f"[USER_REGISTERED] "
            f"id={event['entity_id']} "
            f"email={contact.get('primary_email')} "
            f"display_name={profile.get('display_name')} "
            f"role={data.get('role')}"
        )

    def handle_user_login(self, event: dict) -> None:
        """Handle user.login event."""
        data = event.get("data", {})
        logger.info(
            f"[USER_LOGIN] "
            f"id={event['entity_id']} "
            f"email={data.get('email')} "
            f"role={data.get('role')} "
            f"ip={data.get('ip_address')}"
        )

    def handle_email_verified(self, event: dict) -> None:
        """Handle user.email_verified event."""
        data = event.get("data", {})
        logger.info(
            f"[EMAIL_VERIFIED] "
            f"id={event['entity_id']} "
            f"email={data.get('email')} "
            f"status={data.get('status')}"
        )

    def handle_account_locked(self, event: dict) -> None:
        """Handle user.account_locked event."""
        data = event.get("data", {})
        logger.info(
            f"[ACCOUNT_LOCKED] "
            f"id={event['entity_id']} "
            f"email={data.get('email')} "
            f"failed_attempts={data.get('failed_attempts')} "
            f"lock_duration={data.get('lock_duration_minutes')}min"
        )

    def handle_password_reset_requested(self, event: dict) -> None:
        """Handle user.password_reset_requested event."""
        data = event.get("data", {})
        logger.info(
            f"[PASSWORD_RESET_REQUESTED] "
            f"id={event['entity_id']} "
            f"email={data.get('email')}"
        )

    def handle_password_reset(self, event: dict) -> None:
        """Handle user.password_reset event."""
        logger.info(f"[PASSWORD_RESET] id={event['entity_id']}")

    def get_handlers(self) -> dict:
        """Return event type to handler mapping."""
        return {
            EventType.USER_REGISTERED: self.handle_user_registered,
            EventType.USER_LOGIN: self.handle_user_login,
            EventType.USER_EMAIL_VERIFIED: self.handle_email_verified,
            EventType.USER_ACCOUNT_LOCKED: self.handle_account_locked,
            EventType.USER_PASSWORD_RESET_REQUESTED: self.handle_password_reset_requested,
            EventType.USER_PASSWORD_RESET: self.handle_password_reset,
        }
