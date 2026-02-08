"""Authentication events consumer - stores flattened data in MySQL via DAL."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.user_dal import UserDAL


logger = logging.getLogger(__name__)


class AuthConsumer:
    """Consumer for authentication events from user topic."""

    def __init__(self):
        self._dal = UserDAL()

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse ISO timestamp to datetime."""
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def handle_user_registered(self, event: dict) -> None:
        """Handle user.registered - flatten and store user data."""
        data = event.get("data", {})
        contact = data.get("contact_info", {})
        profile = data.get("profile", {})
        business = profile.get("celebrity_business_info") or {}
        address = business.get("address") or {}

        self._dal.insert_user(
            user_id=event.get("entity_id"),
            email=contact.get("primary_email"),
            display_name=profile.get("display_name"),
            role=data.get("role"),
            status=data.get("status"),
            avatar=profile.get("avatar"),
            bio=profile.get("bio"),
            phone=contact.get("phone"),
            phone_verified=contact.get("phone_verified", False),
            email_verified=contact.get("email_verified", False),
            business_name=business.get("business_name"),
            business_type=business.get("business_type"),
            country=address.get("country"),
            city=address.get("city"),
            state=address.get("state"),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[USER_REGISTERED] Stored: {event['entity_id']}")

    def handle_user_login(self, event: dict) -> None:
        """Handle user.login - store login record."""
        data = event.get("data", {})

        self._dal.insert_login(
            user_id=event.get("entity_id"),
            email=data.get("email"),
            role=data.get("role"),
            ip_address=data.get("ip_address"),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[USER_LOGIN] Stored: {event['entity_id']}")

    def handle_email_verified(self, event: dict) -> None:
        """Handle user.email_verified - update user and log event."""
        data = event.get("data", {})

        self._dal.update_email_verified(
            user_id=event.get("entity_id"),
            status=data.get("status"),
        )
        self._dal.insert_event(
            user_id=event.get("entity_id"),
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            event_data=data,
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[EMAIL_VERIFIED] Updated: {event['entity_id']}")

    def handle_account_locked(self, event: dict) -> None:
        """Handle user.account_locked - update user and log event."""
        data = event.get("data", {})

        self._dal.update_status(event.get("entity_id"), "suspended")
        self._dal.insert_event(
            user_id=event.get("entity_id"),
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            event_data=data,
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[ACCOUNT_LOCKED] Updated: {event['entity_id']}")

    def handle_password_reset_requested(self, event: dict) -> None:
        """Handle user.password_reset_requested - log event."""
        data = event.get("data", {})

        self._dal.insert_event(
            user_id=event.get("entity_id"),
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            event_data=data,
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[PASSWORD_RESET_REQUESTED] Logged: {event['entity_id']}")

    def handle_password_reset(self, event: dict) -> None:
        """Handle user.password_reset - log event."""
        data = event.get("data", {})

        self._dal.insert_event(
            user_id=event.get("entity_id"),
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            event_data=data,
            event_timestamp=self._parse_timestamp(event.get("timestamp")),
        )
        logger.info(f"[PASSWORD_RESET] Logged: {event['entity_id']}")

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
