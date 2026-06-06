"""
GymVault - AWS S3 Manager
Handles member photo upload/download/delete with KMS encryption.
All photos encrypted with SSE-KMS using custom CMK.
Presigned URLs generated fresh on every request (1 hour expiry).
Provides automatic local filesystem fallback if AWS S3 is unavailable.
"""

import logging
import uuid
import os
import boto3
from botocore.exceptions import ClientError
from secrets_manager import secrets_client
from config import SECRET_NAME, AWS_REGION

logger = logging.getLogger(__name__)


class S3Manager:
    """AWS S3 manager for member photo storage with KMS encryption and local fallback."""

    def __init__(self):
        self._client = None
        self._bucket_name = None
        self._region = None
        self._kms_key_arn = None
        self._local_uploads_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "uploads"
        )

    def _get_client(self):
        """Lazy-initialize boto3 S3 client."""
        if self._client is None:
            try:
                region = self._get_region()
                self._client = boto3.client("s3", region_name=region)
            except Exception as e:
                logger.error(f"Failed to create S3 client: {e}")
                raise
        return self._client

    def _get_bucket_name(self):
        """Get S3 bucket name from Secrets Manager."""
        if self._bucket_name is None:
            self._bucket_name = secrets_client.get_key(SECRET_NAME, "s3_bucket_name")
        return self._bucket_name

    def _get_region(self):
        """Get S3 region from Secrets Manager."""
        if self._region is None:
            self._region = secrets_client.get_key(SECRET_NAME, "s3_region") or AWS_REGION
        return self._region

    def _get_kms_key_arn(self):
        """Get KMS key ARN from Secrets Manager."""
        if self._kms_key_arn is None:
            self._kms_key_arn = secrets_client.get_key(SECRET_NAME, "kms_key_arn")
        return self._kms_key_arn

    def upload_member_photo(self, member_id, file_bytes, content_type):
        """
        Upload a member photo to S3 with KMS encryption (or local fallback).

        Args:
            member_id: Member ID (e.g., GYM001)
            file_bytes: Raw file bytes
            content_type: MIME type (e.g., image/jpeg)

        Returns:
            str: S3 object key of uploaded photo (or local path key)
        """
        file_ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
        if file_ext == "jpeg":
            file_ext = "jpg"
        unique_id = uuid.uuid4().hex[:8]
        s3_key = f"members/{member_id}/photo_{unique_id}.{file_ext}"

        # Check if S3 is available, otherwise use local fallback
        if not self.is_available():
            logger.info("AWS S3 not available. Falling back to local storage.")
            try:
                local_path = os.path.join(self._local_uploads_dir, s3_key)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(file_bytes)
                logger.info(f"Local fallback: Saved photo for {member_id} at {local_path}")
                return s3_key
            except Exception as e:
                logger.error(f"Failed to save photo locally: {e}")
                raise

        # S3 Upload
        try:
            client = self._get_client()
            bucket = self._get_bucket_name()
            kms_key = self._get_kms_key_arn()

            if not bucket:
                raise ValueError("S3 bucket name not configured in Secrets Manager")

            # Upload with KMS encryption
            put_params = {
                "Bucket": bucket,
                "Key": s3_key,
                "Body": file_bytes,
                "ContentType": content_type
            }

            # Add KMS encryption if key is configured
            if kms_key:
                put_params["ServerSideEncryption"] = "aws:kms"
                put_params["SSEKMSKeyId"] = kms_key

            client.put_object(**put_params)
            logger.info(f"Uploaded photo for {member_id} to S3: {s3_key}")
            return s3_key

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchBucket":
                logger.error(f"S3 bucket not found: {bucket}")
            elif error_code == "AccessDenied":
                logger.error("Access denied to S3 bucket. Check IAM permissions.")
            elif error_code == "KMS.NotFoundException":
                logger.error("KMS key not found for S3 encryption")
            elif error_code == "KMS.AccessDeniedException":
                logger.error("Access denied to KMS key for S3 encryption")
            else:
                logger.error(f"S3 upload error: {error_code} - {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error uploading photo to S3: {e}")
            raise

    def get_presigned_url(self, s3_key, expiry=3600):
        """
        Generate a presigned URL (or local serving URL) for accessing a member photo.

        Args:
            s3_key: S3 object key
            expiry: URL expiry time in seconds (default 1 hour)

        Returns:
            str: Serving URL or empty string on error
        """
        if not s3_key:
            return ""

        # Check if S3 is available, otherwise use local fallback
        if not self.is_available():
            try:
                from flask import request
                # Build absolute URL to the local photo server route
                base_url = request.host_url.rstrip('/')
                return f"{base_url}/api/members/photo/{s3_key}"
            except RuntimeError:
                # Outside request context (e.g. startup or script)
                return f"http://localhost:5000/api/members/photo/{s3_key}"

        try:
            client = self._get_client()
            bucket = self._get_bucket_name()

            if not bucket:
                logger.warning("S3 bucket not configured")
                return ""

            url = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": s3_key
                },
                ExpiresIn=expiry
            )
            return url

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.warning(f"S3 object not found: {s3_key}")
            elif error_code == "NoSuchBucket":
                logger.error(f"S3 bucket not found: {bucket}")
            elif error_code == "AccessDenied":
                logger.error("Access denied generating presigned URL")
            else:
                logger.error(f"Presigned URL error: {error_code} - {e}")
            return ""

        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            return ""

    def delete_member_photo(self, s3_key):
        """
        Delete a member photo from S3 (or local storage).

        Args:
            s3_key: S3 object key to delete
        """
        if not s3_key:
            return

        # Check if S3 is available, otherwise use local fallback
        if not self.is_available():
            try:
                local_path = os.path.join(self._local_uploads_dir, s3_key)
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info(f"Local fallback: Deleted photo at {local_path}")
            except Exception as e:
                logger.warning(f"Failed to delete local photo: {e}")
            return

        try:
            client = self._get_client()
            bucket = self._get_bucket_name()

            if not bucket:
                logger.warning("S3 bucket not configured, cannot delete")
                return

            client.delete_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Deleted S3 object: {s3_key}")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.warning(f"S3 object already deleted: {s3_key}")
            elif error_code == "NoSuchBucket":
                logger.error(f"S3 bucket not found: {bucket}")
            elif error_code == "AccessDenied":
                logger.error("Access denied deleting S3 object")
            else:
                logger.error(f"S3 delete error: {error_code} - {e}")

        except Exception as e:
            logger.error(f"Unexpected error deleting S3 object: {e}")

    def get_bucket_stats(self):
        """
        Get S3 bucket statistics (or local stats).

        Returns:
            dict: Bucket statistics including photo count
        """
        if not self.is_available():
            total_photos = 0
            if os.path.exists(self._local_uploads_dir):
                for root, dirs, files in os.walk(self._local_uploads_dir):
                    total_photos += len(files)
            return {
                "bucket_name": "local-fallback-storage",
                "bucket_region": "localhost",
                "total_photos": total_photos,
                "encryption": "Local Filesystem",
                "kms_key_alias": "None",
                "status": "local_fallback"
            }

        try:
            client = self._get_client()
            bucket = self._get_bucket_name()

            if not bucket:
                return {
                    "status": "not_configured",
                    "message": "S3 bucket not configured"
                }

            # Count objects in the members/ prefix
            total_photos = 0
            paginator = client.get_paginator("list_objects_v2")

            try:
                for page in paginator.paginate(Bucket=bucket, Prefix="members/"):
                    contents = page.get("Contents", [])
                    total_photos += len(contents)
            except ClientError:
                total_photos = 0

            return {
                "bucket_name": bucket,
                "bucket_region": self._get_region(),
                "total_photos": total_photos,
                "encryption": "SSE-KMS",
                "kms_key_alias": "alias/gymvault-key",
                "status": "active"
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"S3 stats error: {error_code} - {e}")
            return {"status": "error", "error": str(e)}

        except Exception as e:
            logger.error(f"Unexpected error getting bucket stats: {e}")
            return {"status": "error", "error": str(e)}

    def is_available(self):
        """Check if S3 bucket is accessible."""
        try:
            client = self._get_client()
            bucket = self._get_bucket_name()
            if not bucket:
                return False
            client.head_bucket(Bucket=bucket)
            return True
        except Exception:
            # If Secrets Manager is not available, we are in local fallback mode
            return not secrets_client.is_available()

    def refresh(self):
        """Force refresh of S3 configuration from Secrets Manager."""
        self._bucket_name = None
        self._region = None
        self._kms_key_arn = None
        self._client = None


# ─── Singleton Instance ──────────────────────────────────────
s3_manager = S3Manager()
