"""
GymVault - Plans API Routes
Handles plan CRUD operations.
"""

import logging
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify
from database import db

logger = logging.getLogger(__name__)
plans_bp = Blueprint("plans", __name__)


def serialize_plan(plan):
    """Convert MongoDB plan document to JSON-serializable dict."""
    if not plan:
        return None
    return {
        "_id": str(plan.get("_id", "")),
        "plan_name": plan.get("plan_name", ""),
        "duration_months": plan.get("duration_months", 0),
        "price": plan.get("price", 0),
        "features": plan.get("features", []),
        "is_active": plan.get("is_active", True),
        "created_at": plan.get("created_at", "").isoformat() if isinstance(plan.get("created_at"), datetime) else str(plan.get("created_at", ""))
    }


# ─── GET /api/plans ──────────────────────────────────────────
@plans_bp.route("/api/plans", methods=["GET"])
def get_plans():
    """Get all active plans."""
    try:
        database = db.get_db()
        plans = list(database.plans.find({"is_active": True}).sort("price", 1))

        return jsonify({
            "success": True,
            "data": [serialize_plan(p) for p in plans],
            "count": len(plans)
        })

    except Exception as e:
        logger.error(f"Error fetching plans: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /api/plans ─────────────────────────────────────────
@plans_bp.route("/api/plans", methods=["POST"])
def create_plan():
    """Create a new membership plan."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        plan_name = data.get("plan_name", "").strip()
        duration_months = data.get("duration_months", 0)
        price = data.get("price", 0)
        features = data.get("features", [])

        # Validate required fields
        if not plan_name:
            return jsonify({"success": False, "error": "Plan name is required"}), 400
        if not duration_months or int(duration_months) <= 0:
            return jsonify({"success": False, "error": "Duration must be greater than 0"}), 400
        if price is None or float(price) < 0:
            return jsonify({"success": False, "error": "Price must be 0 or greater"}), 400

        # Handle features as string (comma-separated) or list
        if isinstance(features, str):
            features = [f.strip() for f in features.split(",") if f.strip()]

        database = db.get_db()

        # Check for duplicate plan name
        existing = database.plans.find_one({"plan_name": plan_name, "is_active": True})
        if existing:
            return jsonify({"success": False, "error": f"Plan '{plan_name}' already exists"}), 409

        plan_doc = {
            "plan_name": plan_name,
            "duration_months": int(duration_months),
            "price": float(price),
            "features": features,
            "is_active": True,
            "created_at": datetime.utcnow()
        }

        result = database.plans.insert_one(plan_doc)
        plan_doc["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "data": serialize_plan(plan_doc),
            "message": f"Plan '{plan_name}' created successfully"
        }), 201

    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── PUT /api/plans/<plan_id> ────────────────────────────────
@plans_bp.route("/api/plans/<plan_id>", methods=["PUT"])
def update_plan(plan_id):
    """Update an existing plan."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        database = db.get_db()

        try:
            plan = database.plans.find_one({"_id": ObjectId(plan_id)})
        except Exception:
            return jsonify({"success": False, "error": "Invalid plan ID"}), 400

        if not plan:
            return jsonify({"success": False, "error": "Plan not found"}), 404

        update_fields = {}

        if "plan_name" in data:
            update_fields["plan_name"] = data["plan_name"].strip()
        if "duration_months" in data:
            update_fields["duration_months"] = int(data["duration_months"])
        if "price" in data:
            update_fields["price"] = float(data["price"])
        if "features" in data:
            features = data["features"]
            if isinstance(features, str):
                features = [f.strip() for f in features.split(",") if f.strip()]
            update_fields["features"] = features
        if "is_active" in data:
            update_fields["is_active"] = bool(data["is_active"])

        if not update_fields:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        database.plans.update_one(
            {"_id": ObjectId(plan_id)},
            {"$set": update_fields}
        )

        updated_plan = database.plans.find_one({"_id": ObjectId(plan_id)})

        return jsonify({
            "success": True,
            "data": serialize_plan(updated_plan),
            "message": "Plan updated successfully"
        })

    except Exception as e:
        logger.error(f"Error updating plan {plan_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
