"""
GymVault - MongoDB Database Manager
Handles MongoDB connection, health checks, and default plan seeding.
Connection URI fetched from AWS Secrets Manager at runtime.
"""

import logging
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure,
    ServerSelectionTimeoutError,
    OperationFailure
)
from config import SECRET_NAME, LOCAL_MONGODB_URI, LOCAL_MONGODB_DB_NAME

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database manager for GymVault."""

    def __init__(self):
        self._client = None
        self._db = None
        self._connected = False

    def _get_connection_uri(self):
        """Get MongoDB URI - try Secrets Manager first, fall back to local config."""
        try:
            from secrets_manager import secrets_client
            uri = secrets_client.get_key(SECRET_NAME, "mongodb_uri")
            if uri:
                return uri
        except Exception as e:
            logger.warning(f"Could not fetch MongoDB URI from Secrets Manager: {e}")

        logger.info("Using local MongoDB URI from .env / config")
        return LOCAL_MONGODB_URI

    def _get_db_name(self):
        """Get database name - try Secrets Manager first, fall back to local config."""
        try:
            from secrets_manager import secrets_client
            db_name = secrets_client.get_key(SECRET_NAME, "mongodb_db_name")
            if db_name:
                return db_name
        except Exception as e:
            logger.warning(f"Could not fetch DB name from Secrets Manager: {e}")

        return LOCAL_MONGODB_DB_NAME

    def connect(self):
        """
        Establish MongoDB connection.

        Returns:
            MongoClient: Connected pymongo client
        """
        if self._client is not None and self._connected:
            return self._client

        try:
            uri = self._get_connection_uri()
            logger.info("Connecting to MongoDB...")

            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000
            )

            # Test connection
            self._client.admin.command("ping")
            self._connected = True

            db_name = self._get_db_name()
            self._db = self._client[db_name]

            logger.info(f"Connected to MongoDB database: {db_name}")

            # Create indexes
            self._create_indexes()

            return self._client

        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            self._connected = False
            raise

        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB server selection timeout: {e}")
            self._connected = False
            raise

        except OperationFailure as e:
            logger.error(f"MongoDB operation failed: {e}")
            self._connected = False
            raise

        except Exception as e:
            logger.error(f"Unexpected MongoDB error: {e}")
            self._connected = False
            raise

    def _create_indexes(self):
        """Create necessary database indexes."""
        try:
            if self._db is not None:
                # Members indexes
                self._db.members.create_index("email", unique=True)
                self._db.members.create_index("member_id", unique=True)
                self._db.members.create_index("status")
                self._db.members.create_index("membership_end")

                # Payments indexes
                self._db.payments.create_index("member_id")
                self._db.payments.create_index("payment_date")
                self._db.payments.create_index("receipt_number", unique=True)

                # Check-ins indexes
                self._db.checkins.create_index("member_id")
                self._db.checkins.create_index("date")

                logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")

    def get_db(self):
        """
        Get database instance. Connects if not already connected.

        Returns:
            Database: pymongo database instance
        """
        if self._db is None:
            self.connect()
        return self._db

    def ping(self):
        """
        Health check for MongoDB connection.

        Returns:
            bool: True if connected and responsive
        """
        try:
            if self._client is None:
                self.connect()
            self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            self._connected = False
            return False

    def seed_default_plans(self):
        """
        Seed default plans if no plans exist in the database.
        Runs on application startup.
        """
        try:
            database = self.get_db()
            existing_plans = database.plans.count_documents({})

            if existing_plans > 0:
                logger.info(f"Plans already exist ({existing_plans} found). Skipping seed.")
                return

            default_plans = [
                {
                    "plan_name": "Basic",
                    "duration_months": 1,
                    "price": 29.00,
                    "features": ["Gym Access", "Locker"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "plan_name": "Standard",
                    "duration_months": 3,
                    "price": 79.00,
                    "features": ["Gym Access", "Locker", "1 PT Session"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "plan_name": "Premium",
                    "duration_months": 12,
                    "price": 249.00,
                    "features": [
                        "Gym Access",
                        "Locker",
                        "Unlimited PT",
                        "Diet Plan",
                        "Sauna"
                    ],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            ]

            result = database.plans.insert_many(default_plans)
            logger.info(f"Seeded {len(result.inserted_ids)} default plans")

        except Exception as e:
            logger.error(f"Error seeding default plans: {e}")

    def get_member_count(self):
        """Get total number of members."""
        try:
            database = self.get_db()
            return database.members.count_documents({})
        except Exception:
            return 0

    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False
            logger.info("MongoDB connection closed")


# ─── Singleton Instance ──────────────────────────────────────
db = Database()
