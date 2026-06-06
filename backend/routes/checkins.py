"""
GymVault - Check-ins API Routes
Handles member check-in recording and history.
"""

import logging
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, request, jsonify
from database import db

logger = logging.getLogger(__name__)
checkins_bp = Blueprint("checkins", __name__)


def serialize_checkin(checkin):
    """Convert MongoDB checkin document to JSON-serializable dict."""
    if not checkin:
        return None
    return {
        "_id": str(checkin.get("_id", "")),
        "member_id": str(checkin.get("member_id", "")),
        "member_name": checkin.get("member_name", ""),
        "checkin_time": checkin.get("checkin_time", "").isoformat() if isinstance(checkin.get("checkin_time"), datetime) else str(checkin.get("checkin_time", "")),
        "date": checkin.get("date", "")
    }


# ─── POST /api/checkins ──────────────────────────────────────
@checkins_bp.route("/api/checkins", methods=["POST"])
def create_checkin():
    """
    Record a member check-in.
    Validates that member is Active before allowing check-in.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        member_id_str = data.get("member_id", "").strip()

        if not member_id_str:
            return jsonify({"success": False, "error": "Member ID is required"}), 400

        database = db.get_db()

        # Look up member by member_id string (e.g., GYM001)
        member = database.members.find_one({"member_id": member_id_str})
        if not member:
            # Try looking up by ObjectId
            try:
                member = database.members.find_one({"_id": ObjectId(member_id_str)})
            except Exception:
                pass

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Check membership status
        membership_end = member.get("membership_end")
        now = datetime.utcnow()

        if not membership_end or membership_end < now:
            return jsonify({
                "success": False,
                "error": "Membership Expired",
                "member_name": member.get("full_name", ""),
                "membership_end": membership_end.isoformat() if membership_end else "",
                "expired": True
            }), 403

        # Calculate days remaining
        days_remaining = (membership_end - now).days

        # Record check-in
        checkin_doc = {
            "member_id": member["_id"],
            "member_name": member.get("full_name", ""),
            "checkin_time": now,
            "date": now.strftime("%Y-%m-%d")
        }

        result = database.checkins.insert_one(checkin_doc)
        checkin_doc["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "data": serialize_checkin(checkin_doc),
            "member_name": member.get("full_name", ""),
            "plan_name": member.get("plan_name", ""),
            "membership_end": membership_end.isoformat(),
            "days_remaining": days_remaining,
            "message": f"Welcome back, {member.get('full_name', '')}! 💪"
        }), 201

    except Exception as e:
        logger.error(f"Error recording check-in: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── GET /api/checkins/today ─────────────────────────────────
@checkins_bp.route("/api/checkins/today", methods=["GET"])
def get_today_checkins():
    """Get all check-ins for today."""
    try:
        database = db.get_db()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        checkins = list(
            database.checkins.find({"date": today}).sort("checkin_time", -1)
        )

        return jsonify({
            "success": True,
            "data": [serialize_checkin(c) for c in checkins],
            "count": len(checkins),
            "date": today
        })

    except Exception as e:
        logger.error(f"Error fetching today's check-ins: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── GET /api/checkins/<member_id> ───────────────────────────
@checkins_bp.route("/api/checkins/<member_id>", methods=["GET"])
def get_member_checkins(member_id):
    """Get check-in history for a specific member."""
    try:
        database = db.get_db()

        # Look up member by member_id string
        member = database.members.find_one({"member_id": member_id})
        if not member:
            try:
                member = database.members.find_one({"_id": ObjectId(member_id)})
            except Exception:
                return jsonify({"success": False, "error": "Member not found"}), 404

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Get recent checkins (last 50)
        checkins = list(
            database.checkins.find({"member_id": member["_id"]})
            .sort("checkin_time", -1)
            .limit(50)
        )

        return jsonify({
            "success": True,
            "data": [serialize_checkin(c) for c in checkins],
            "count": len(checkins),
            "member_name": member.get("full_name", ""),
            "member_id": member.get("member_id", "")
        })

    except Exception as e:
        logger.error(f"Error fetching check-ins for member {member_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
