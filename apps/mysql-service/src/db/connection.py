"""MySQL database connection."""

import os
import logging
import mysql.connector
from mysql.connector import pooling

logger = logging.getLogger(__name__)


class Database:
    """MySQL database connection manager."""

    def __init__(self):
        self._pool = None

    def connect(self):
        """Create connection pool."""
        config = {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT", 3306)),
            "user": os.getenv("MYSQL_USER", "analytics"),
            "password": os.getenv("MYSQL_PASSWORD", "analytics123"),
            "database": os.getenv("MYSQL_DATABASE", "analytics"),
        }

        self._pool = pooling.MySQLConnectionPool(
            pool_name="analytics_pool",
            pool_size=5,
            **config
        )
        logger.info(f"Connected to MySQL: {config['host']}:{config['port']}/{config['database']}")

    def get_connection(self):
        """Get connection from pool."""
        return self._pool.get_connection()

    def execute(self, query: str, params: tuple = None):
        """Execute a query."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    def init_tables(self):
        """Create analytics tables with flattened user data."""
        tables = [
            # Users table - flattened from user.registered event
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL,
                display_name VARCHAR(100),
                role ENUM('consumer', 'leader') DEFAULT 'consumer',
                status ENUM('pending', 'active', 'suspended', 'deleted') DEFAULT 'pending',
                avatar VARCHAR(500),
                bio TEXT,
                phone VARCHAR(50),
                phone_verified BOOLEAN DEFAULT FALSE,
                email_verified BOOLEAN DEFAULT FALSE,
                business_name VARCHAR(200),
                business_type VARCHAR(50),
                country VARCHAR(2),
                city VARCHAR(100),
                state VARCHAR(100),
                event_id VARCHAR(50),
                event_timestamp DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_role (role),
                INDEX idx_status (status),
                INDEX idx_country (country),
                INDEX idx_created (created_at)
            )
            """,
            # User logins table - from user.login event
            """
            CREATE TABLE IF NOT EXISTS user_logins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                email VARCHAR(255),
                role VARCHAR(50),
                ip_address VARCHAR(50),
                event_id VARCHAR(50),
                event_timestamp DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_ip (ip_address),
                INDEX idx_timestamp (event_timestamp)
            )
            """,
            # User events table - generic event log
            """
            CREATE TABLE IF NOT EXISTS user_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                event_type VARCHAR(100) NOT NULL,
                event_id VARCHAR(50),
                event_data JSON,
                event_timestamp DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_event_type (event_type),
                INDEX idx_timestamp (event_timestamp)
            )
            """
        ]

        for sql in tables:
            self.execute(sql)

        logger.info("Analytics tables initialized")


_db = None


def get_database() -> Database:
    """Get database singleton."""
    global _db
    if _db is None:
        _db = Database()
    return _db
