"""User Data Access Layer - SQL operations for user analytics."""

import json
import logging
from datetime import datetime
from typing import Optional

from src.db.connection import get_database


logger = logging.getLogger(__name__)


class UserDAL:
    """Data Access Layer for user analytics tables."""

    def __init__(self):
        self._db = get_database()

    def insert_user(
        self,
        user_id: str,
        email: str,
        display_name: str,
        role: str,
        status: str,
        avatar: Optional[str],
        bio: Optional[str],
        phone: Optional[str],
        business_name: Optional[str],
        business_type: Optional[str],
        country: Optional[str],
        city: Optional[str],
        state: Optional[str],
        event_id: str,
        event_timestamp: datetime,
    ) -> int:
        """Insert a new user record."""
        sql = """
            INSERT INTO users (
                user_id, email, display_name, role, status,
                avatar, bio, phone,
                business_name, business_type, country, city, state,
                event_id, event_timestamp
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
        """
        return self._db.execute(sql, (
            user_id, email, display_name, role, status,
            avatar, bio, phone,
            business_name, business_type, country, city, state,
            event_id, event_timestamp,
        ))

    def insert_login(
        self,
        user_id: str,
        email: str,
        role: str,
        ip_address: str,
        event_id: str,
        event_timestamp: datetime,
    ) -> int:
        """Insert a login record."""
        sql = """
            INSERT INTO user_logins (
                user_id, email, role, ip_address, event_id, event_timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._db.execute(sql, (
            user_id, email, role, ip_address, event_id, event_timestamp,
        ))

    def insert_event(
        self,
        user_id: str,
        event_type: str,
        event_id: str,
        event_data: dict,
        event_timestamp: datetime,
    ) -> int:
        """Insert a generic user event."""
        sql = """
            INSERT INTO user_events (
                user_id, event_type, event_id, event_data, event_timestamp
            ) VALUES (%s, %s, %s, %s, %s)
        """
        return self._db.execute(sql, (
            user_id, event_type, event_id, json.dumps(event_data), event_timestamp,
        ))

    def update_status(self, user_id: str, status: str) -> None:
        """Update user status."""
        sql = "UPDATE users SET status = %s WHERE user_id = %s"
        self._db.execute(sql, (status, user_id))
