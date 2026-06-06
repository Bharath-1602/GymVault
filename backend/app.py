"""
GymVault - Main Flask Application
Gym Membership Management System

Runs on host=0.0.0.0, port=5000
All routes return JSON: {"success": bool, "data": ..., "error": "..."}
CORS enabled for all routes.
"""

import logging
import sys
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

# ─── Configure Logging ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ─── Create Flask App ────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ─── Import Managers ─────────────────────────────────────────
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, APP_VERSION, SECRET_NAME
from database import db
from secrets_manager import secrets_client
from s3_manager import s3_manager
from kms_manager import kms_manager
from sns_manager import sns_manager
from routes import register_routes

# ─── Register Route Blueprints ───────────────────────────────
register_routes(app)


# ═══════════════════════════════════════════════════════════════
# GENERAL ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    Returns status of all services: MongoDB, S3, KMS, SNS, Secrets Manager.
    """
    try:
        # Check MongoDB
        mongo_status = False
        total_members = 0
        try:
            mongo_status = db.ping()
            if mongo_status:
                total_members = db.get_member_count()
        except Exception as e:
            logger.warning(f"MongoDB health check failed: {e}")

        # Check Secrets Manager
        secrets_status = False
        try:
            secrets_status = secrets_client.is_available()
        except Exception:
            pass

        # Check S3
        s3_status = False
        s3_bucket = ""
        try:
            s3_status = s3_manager.is_available()
            s3_bucket = secrets_client.get_key(SECRET_NAME, "s3_bucket_name")
        except Exception:
            pass

        # Check KMS
        kms_status = False
        try:
            kms_status = kms_manager.is_available()
        except Exception:
            pass

        # Check SNS
        sns_status = False
        sns_topic_preview = ""
        try:
            sns_status = sns_manager.is_available()
            sns_arn = secrets_client.get_key(SECRET_NAME, "sns_topic_arn")
            if sns_arn:
                sns_topic_preview = sns_arn[:30] + "..." if len(sns_arn) > 30 else sns_arn
        except Exception:
            pass

        # Total revenue
        total_revenue = 0
        try:
            database = db.get_db()
            pipeline = [
                {"$match": {"status": "Paid"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            result = list(database.payments.aggregate(pipeline))
            total_revenue = result[0]["total"] if result else 0
        except Exception:
            pass

        return jsonify({
            "success": True,
            "data": {
                "app": "GymVault",
                "version": APP_VERSION,
                "status": "running",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "mongodb": {"status": "connected" if mongo_status else "disconnected", "healthy": mongo_status},
                    "s3": {"status": "connected" if s3_status else "disconnected", "healthy": s3_status, "bucket": s3_bucket},
                    "kms": {"status": "active" if kms_status else "inactive", "healthy": kms_status},
                    "sns": {"status": "active" if sns_status else "inactive", "healthy": sns_status, "topic_preview": sns_topic_preview},
                    "secrets_manager": {"status": "connected" if secrets_status else "disconnected", "healthy": secrets_status}
                },
                "total_members": total_members,
                "total_revenue": total_revenue
            }
        })

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": {
                "app": "GymVault",
                "version": APP_VERSION,
                "status": "error"
            }
        }), 500


@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    """Get dashboard statistics."""
    try:
        database = db.get_db()
        now = datetime.utcnow()
        from datetime import timedelta

        # Total members
        total_members = database.members.count_documents({})

        # Active members (recalculate based on dates)
        active_members = database.members.count_documents({
            "membership_end": {"$gt": now + timedelta(days=7)}
        })

        # Expiring soon (within 7 days)
        expiring_soon = database.members.count_documents({
            "membership_end": {
                "$gt": now,
                "$lte": now + timedelta(days=7)
            }
        })

        # Expired members
        expired_members = database.members.count_documents({
            "membership_end": {"$lt": now}
        })

        # Total revenue
        pipeline_total = [
            {"$match": {"status": "Paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        total_result = list(database.payments.aggregate(pipeline_total))
        total_revenue = total_result[0]["total"] if total_result else 0

        # Today's check-ins
        today = now.strftime("%Y-%m-%d")
        todays_checkins = database.checkins.count_documents({"date": today})

        # New members this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_members_month = database.members.count_documents({
            "created_at": {"$gte": month_start}
        })

        # Revenue this month
        pipeline_month = [
            {"$match": {"status": "Paid", "payment_date": {"$gte": month_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        month_result = list(database.payments.aggregate(pipeline_month))
        revenue_this_month = month_result[0]["total"] if month_result else 0

        return jsonify({
            "success": True,
            "data": {
                "total_members": total_members,
                "active_members": active_members,
                "expiring_soon": expiring_soon,
                "expired_members": expired_members,
                "total_revenue": total_revenue,
                "todays_checkins": todays_checkins,
                "new_members_this_month": new_members_month,
                "revenue_this_month": revenue_this_month
            }
        })

    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# AWS INFO ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/aws/secrets-info", methods=["GET"])
def aws_secrets_info():
    """Get secrets metadata (no actual secret values)."""
    try:
        secret_data = secrets_client.get_secret(SECRET_NAME)

        mongodb_uri = secret_data.get("mongodb_uri", "")
        mongodb_preview = mongodb_uri[:20] + "..." if len(mongodb_uri) > 20 else mongodb_uri

        sns_arn = secret_data.get("sns_topic_arn", "")
        sns_preview = sns_arn[:30] + "..." if len(sns_arn) > 30 else sns_arn

        kms_arn = secret_data.get("kms_key_arn", "")
        kms_preview = kms_arn[:30] + "..." if len(kms_arn) > 30 else kms_arn

        return jsonify({
            "success": True,
            "data": {
                "secret_name": SECRET_NAME,
                "available_keys": list(secret_data.keys()) if secret_data else [],
                "mongodb_uri_preview": mongodb_preview,
                "s3_bucket_name": secret_data.get("s3_bucket_name", ""),
                "sns_topic_preview": sns_preview,
                "kms_key_preview": kms_preview,
                "gym_name": secret_data.get("gym_name", ""),
                "cache_info": secrets_client.get_cache_info()
            }
        })

    except Exception as e:
        logger.error(f"Secrets info error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/aws/s3-info", methods=["GET"])
def aws_s3_info():
    """Get S3 bucket statistics."""
    try:
        stats = s3_manager.get_bucket_stats()
        return jsonify({
            "success": True,
            "data": stats
        })

    except Exception as e:
        logger.error(f"S3 info error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/aws/kms-info", methods=["GET"])
def aws_kms_info():
    """Get KMS key metadata."""
    try:
        key_info = kms_manager.get_key_info()
        return jsonify({
            "success": True,
            "data": key_info
        })

    except Exception as e:
        logger.error(f"KMS info error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/aws/send-expiry-alerts", methods=["POST"])
def send_expiry_alerts():
    """Trigger bulk expiry alert notifications."""
    try:
        alerts_sent = sns_manager.send_bulk_expiry_alerts()
        return jsonify({
            "success": True,
            "data": {
                "alerts_sent": alerts_sent,
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": f"{alerts_sent} expiry alert(s) sent successfully"
        })

    except Exception as e:
        logger.error(f"Expiry alerts error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/aws/cache/clear", methods=["POST"])
def clear_cache():
    """Clear all in-memory caches."""
    try:
        secrets_client.clear_cache()
        s3_manager.refresh()
        kms_manager.refresh()
        sns_manager.refresh()

        return jsonify({
            "success": True,
            "message": "All caches cleared successfully",
            "data": {
                "timestamp": datetime.utcnow().isoformat(),
                "cache_info": secrets_client.get_cache_info()
            }
        })

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════

def startup():
    """Application startup tasks."""
    logger.info("=" * 60)
    logger.info(f"  GymVault v{APP_VERSION} Starting Up")
    logger.info("=" * 60)

    # Connect to MongoDB
    try:
        db.connect()
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        logger.info("   App will retry on first request")

    # Seed default plans
    try:
        db.seed_default_plans()
        logger.info("✅ Default plans seeded")
    except Exception as e:
        logger.warning(f"⚠️  Could not seed plans: {e}")

    # Check AWS services (non-blocking)
    try:
        if secrets_client.is_available():
            logger.info("✅ AWS Secrets Manager connected")
        else:
            logger.warning("⚠️  AWS Secrets Manager not available (using local config)")
    except Exception:
        logger.warning("⚠️  AWS Secrets Manager not available")

    try:
        if s3_manager.is_available():
            logger.info("✅ AWS S3 connected")
        else:
            logger.warning("⚠️  AWS S3 not available")
    except Exception:
        logger.warning("⚠️  AWS S3 not available")

    try:
        if kms_manager.is_available():
            logger.info("✅ AWS KMS connected")
        else:
            logger.warning("⚠️  AWS KMS not available")
    except Exception:
        logger.warning("⚠️  AWS KMS not available")

    try:
        if sns_manager.is_available():
            logger.info("✅ AWS SNS connected")
        else:
            logger.warning("⚠️  AWS SNS not available")
    except Exception:
        logger.warning("⚠️  AWS SNS not available")

    logger.info("=" * 60)
    logger.info(f"  GymVault running on http://0.0.0.0:{FLASK_PORT}")
    logger.info("=" * 60)


# ─── Main Entry Point ────────────────────────────────────────
if __name__ == "__main__":
    startup()
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG
    )
