"""
GymVault Configuration Module
Loads .env for local development only.
All actual values come from AWS Secrets Manager at runtime.
"""

import os
from dotenv import load_dotenv

# Load .env file for local development only
# On EC2 with IAM roles, this file won't exist and that's fine
load_dotenv()

# ─── Application Constants ───────────────────────────────────
APP_NAME = "GymVault"
APP_VERSION = "1.0.0"
SECRET_NAME = "gymvault/config"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ─── Local Development Fallbacks ─────────────────────────────
# These are ONLY used when Secrets Manager is unavailable (local dev)
LOCAL_MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/gymvault")
LOCAL_MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "gymvault")
LOCAL_S3_BUCKET = os.getenv("S3_BUCKET_NAME", "")
LOCAL_S3_REGION = os.getenv("S3_REGION", "us-east-1")
LOCAL_KMS_KEY_ARN = os.getenv("KMS_KEY_ARN", "")
LOCAL_SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
LOCAL_GYM_NAME = os.getenv("GYM_NAME", "GymVault Fitness Center")
LOCAL_GYM_EMAIL = os.getenv("GYM_EMAIL", "admin@gymvault.com")
LOCAL_ALERT_DAYS_BEFORE = int(os.getenv("ALERT_DAYS_BEFORE", "7"))

# ─── Flask Config ────────────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# ─── Upload Config ───────────────────────────────────────────
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    """Check if file extension is allowed for photo upload."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
