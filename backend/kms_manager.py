"""
GymVault - AWS KMS Manager
Manages KMS key information and verification.
Actual encryption is done by S3 SSE-KMS.
This module provides key metadata and status checks.
Provides automatic simulation if AWS KMS is unavailable.
"""

import logging
import boto3
from botocore.exceptions import ClientError
from secrets_manager import secrets_client
from config import SECRET_NAME, AWS_REGION

logger = logging.getLogger(__name__)


class KMSManager:
    """AWS KMS key manager for GymVault."""

    def __init__(self):
        self._client = None
        self._kms_key_arn = None

    def _get_client(self):
        """Lazy-initialize boto3 KMS client."""
        if self._client is None:
            try:
                self._client = boto3.client("kms", region_name=AWS_REGION)
            except Exception as e:
                logger.error(f"Failed to create KMS client: {e}")
                raise
        return self._client

    def _get_key_arn(self):
        """Get KMS key ARN from Secrets Manager."""
        if self._kms_key_arn is None:
            self._kms_key_arn = secrets_client.get_key(SECRET_NAME, "kms_key_arn")
        return self._kms_key_arn

    def get_key_info(self):
        """
        Get KMS key metadata.

        Returns:
            dict: Key metadata including alias, state, and usage info
        """
        try:
            client = self._get_client()
            key_arn = self._get_key_arn()

            if not key_arn:
                raise ValueError("KMS key ARN not configured")

            response = client.describe_key(KeyId=key_arn)
            key_metadata = response["KeyMetadata"]

            # Try to get alias
            alias = "alias/gymvault-key"
            try:
                aliases_response = client.list_aliases(KeyId=key_arn)
                aliases = aliases_response.get("Aliases", [])
                if aliases:
                    alias = aliases[0].get("AliasName", alias)
            except ClientError:
                pass

            return {
                "key_id": key_metadata.get("KeyId", ""),
                "key_arn": key_metadata.get("Arn", ""),
                "key_alias": alias,
                "key_state": key_metadata.get("KeyState", "Unknown"),
                "key_usage": key_metadata.get("KeyUsage", "Unknown"),
                "key_spec": key_metadata.get("KeySpec", "Unknown"),
                "creation_date": str(key_metadata.get("CreationDate", "")),
                "description": key_metadata.get("Description", ""),
                "enabled": key_metadata.get("Enabled", False),
                "key_manager": key_metadata.get("KeyManager", "Unknown"),
                "status": "active"
            }

        except Exception as e:
            # Check if we are running locally without AWS
            if not secrets_client.is_available():
                return {
                    "key_id": "simulated-kms-key-id",
                    "key_arn": "arn:aws:kms:us-east-1:123456789012:key/simulated-key",
                    "key_alias": "alias/gymvault-key (Simulated)",
                    "key_state": "Enabled",
                    "key_usage": "ENCRYPT_DECRYPT",
                    "key_spec": "SYMMETRIC_DEFAULT",
                    "creation_date": "2026-06-05 00:00:00",
                    "description": "Local development simulated KMS key",
                    "enabled": True,
                    "key_manager": "CUSTOMER",
                    "status": "active"
                }

            if isinstance(e, ClientError):
                error_code = e.response["Error"]["Code"]
                if error_code == "NotFoundException":
                    logger.error(f"KMS key not found: {key_arn}")
                    return {"status": "not_found", "error": "KMS key not found"}
                elif error_code == "AccessDeniedException":
                    logger.error("Access denied to KMS key. Check IAM permissions.")
                    return {"status": "access_denied", "error": "Access denied to KMS key"}
                elif error_code == "InvalidArnException":
                    logger.error(f"Invalid KMS key ARN: {key_arn}")
                    return {"status": "invalid_arn", "error": "Invalid KMS key ARN"}
                else:
                    logger.error(f"KMS error: {error_code} - {e}")
                    return {"status": "error", "error": str(e)}

            logger.error(f"Unexpected KMS error: {e}")
            return {"status": "error", "error": str(e)}

    def describe_key(self):
        """
        Get detailed key description.

        Returns:
            dict: Full key description from AWS
        """
        try:
            client = self._get_client()
            key_arn = self._get_key_arn()

            if not key_arn:
                raise ValueError("KMS key ARN not configured")

            response = client.describe_key(KeyId=key_arn)
            metadata = response["KeyMetadata"]

            return {
                "key_id": metadata.get("KeyId", ""),
                "arn": metadata.get("Arn", ""),
                "state": metadata.get("KeyState", ""),
                "usage": metadata.get("KeyUsage", ""),
                "spec": metadata.get("KeySpec", ""),
                "enabled": metadata.get("Enabled", False),
                "description": metadata.get("Description", ""),
                "creation_date": str(metadata.get("CreationDate", "")),
                "key_manager": metadata.get("KeyManager", ""),
                "encryption_algorithms": metadata.get("EncryptionAlgorithms", [])
            }

        except Exception as e:
            if not secrets_client.is_available():
                return {
                    "key_id": "simulated-kms-key-id",
                    "arn": "arn:aws:kms:us-east-1:123456789012:key/simulated-key",
                    "state": "Enabled",
                    "usage": "ENCRYPT_DECRYPT",
                    "spec": "SYMMETRIC_DEFAULT",
                    "enabled": True,
                    "description": "Local development simulated KMS key",
                    "creation_date": "2026-06-05 00:00:00",
                    "key_manager": "CUSTOMER",
                    "encryption_algorithms": ["SYMMETRIC_DEFAULT"]
                }

            if isinstance(e, ClientError):
                error_code = e.response["Error"]["Code"]
                logger.error(f"KMS describe_key error: {error_code} - {e}")
                return {"error": f"KMS error: {error_code}"}

            logger.error(f"Unexpected error describing KMS key: {e}")
            return {"error": str(e)}

    def is_available(self):
        """Check if KMS key is accessible and enabled."""
        try:
            info = self.get_key_info()
            return info.get("status") == "active" and info.get("enabled", False)
        except Exception:
            return False

    def refresh(self):
        """Force refresh of KMS key ARN from Secrets Manager."""
        self._kms_key_arn = None
        return self.get_key_info()


# ─── Singleton Instance ──────────────────────────────────────
kms_manager = KMSManager()
