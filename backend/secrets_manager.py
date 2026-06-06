"""
GymVault - AWS Secrets Manager Client
Handles all secret retrieval with 5-minute TTL in-memory cache.
On EC2: uses IAM role automatically (no explicit credentials).
Locally: uses .env / aws configure.
"""

import time
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SecretsManagerClient:
    """AWS Secrets Manager client with in-memory TTL cache."""

    def __init__(self, region="us-east-1"):
        self.region = region
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes in seconds
        self._cache_timestamps = {}
        self._client = None

    def _get_client(self):
        """Lazy-initialize boto3 Secrets Manager client."""
        if self._client is None:
            try:
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self.region
                )
            except Exception as e:
                logger.error(f"Failed to create Secrets Manager client: {e}")
                raise
        return self._client

    def get_secret(self, secret_name):
        """
        Retrieve a secret from AWS Secrets Manager.
        Returns cached value if within TTL, otherwise fetches fresh.

        Args:
            secret_name: Name of the secret in Secrets Manager

        Returns:
            dict: Parsed secret key-value pairs
        """
        # Check cache first
        now = time.time()
        if secret_name in self._cache:
            cached_time = self._cache_timestamps.get(secret_name, 0)
            if (now - cached_time) < self._cache_ttl:
                logger.debug(f"Cache hit for secret: {secret_name}")
                return self._cache[secret_name]
            else:
                logger.debug(f"Cache expired for secret: {secret_name}")

        # Fetch from AWS
        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_name)

            if "SecretString" in response:
                secret_data = json.loads(response["SecretString"])
            else:
                logger.error(f"Secret {secret_name} is binary, expected string")
                return {}

            # Update cache
            self._cache[secret_name] = secret_data
            self._cache_timestamps[secret_name] = now
            logger.info(f"Fetched and cached secret: {secret_name}")
            return secret_data

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "ResourceNotFoundException":
                logger.error(f"Secret not found: {secret_name}")
            elif error_code == "AccessDeniedException":
                logger.error(f"Access denied to secret: {secret_name}. Check IAM permissions.")
            elif error_code == "InvalidRequestException":
                logger.error(f"Invalid request for secret: {secret_name}")
            elif error_code == "InvalidParameterException":
                logger.error(f"Invalid parameter for secret: {secret_name}")
            elif error_code == "DecryptionFailure":
                logger.error(f"Cannot decrypt secret: {secret_name}. Check KMS permissions.")
            elif error_code == "InternalServiceError":
                logger.error(f"AWS internal error fetching secret: {secret_name}")
            else:
                logger.error(f"Unexpected error fetching secret {secret_name}: {error_code} - {e}")

            return {}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret {secret_name} as JSON: {e}")
            return {}

        except Exception as e:
            logger.error(f"Unexpected error fetching secret {secret_name}: {e}")
            return {}

    def get_key(self, secret_name, key):
        """
        Get a specific key from a secret.

        Args:
            secret_name: Name of the secret
            key: Key within the secret JSON

        Returns:
            str: Value of the key, or empty string if not found
        """
        secret_data = self.get_secret(secret_name)
        value = secret_data.get(key, "")
        if not value:
            logger.warning(f"Key '{key}' not found in secret '{secret_name}'")
        return value

    def clear_cache(self):
        """Clear all cached secrets."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Secrets Manager cache cleared")

    def get_cache_info(self):
        """
        Get information about current cache state.

        Returns:
            dict: Cache statistics including entries and TTL info
        """
        now = time.time()
        cache_entries = []

        for secret_name, timestamp in self._cache_timestamps.items():
            age_seconds = int(now - timestamp)
            remaining_seconds = max(0, self._cache_ttl - age_seconds)
            cache_entries.append({
                "secret_name": secret_name,
                "cached_at": timestamp,
                "age_seconds": age_seconds,
                "ttl_remaining_seconds": remaining_seconds,
                "is_expired": remaining_seconds == 0
            })

        return {
            "total_cached_secrets": len(self._cache),
            "ttl_seconds": self._cache_ttl,
            "entries": cache_entries
        }

    def is_available(self):
        """Check if Secrets Manager is accessible."""
        try:
            client = self._get_client()
            client.list_secrets(MaxResults=1)
            return True
        except Exception as e:
            logger.warning(f"Secrets Manager not available: {e}")
            return False


# ─── Singleton Instance ──────────────────────────────────────
secrets_client = SecretsManagerClient()
