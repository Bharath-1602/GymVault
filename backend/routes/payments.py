"""
GymVault - Payments API Routes
Handles payment creation, listing, and summary statistics.
"""

import logging
import random
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify
from database import db
from sns_manager import sns_manager

logger = logging.getLogger(__name__)
payments_bp = Blueprint("payments", __name__)


def serialize_payment(payment):
    """Convert MongoDB payment document to JSON-serializable dict."""
    if not payment:
        return None
    return {
        "_id": str(payment.get("_id", "")),
        "member_id": str(payment.get("member_id", "")),
        "member_name": payment.get("member_name", ""),
        "plan_id": str(payment.get("plan_id", "")),
        "plan_name": payment.get("plan_name", ""),
        "amount": payment.get("amount", 0),
        "payment_date": payment.get("payment_date", "").isoformat() if isinstance(payment.get("payment_date"), datetime) else str(payment.get("payment_date", "")),
        "payment_method": payment.get("payment_method", ""),
        "status": payment.get("status", ""),
        "receipt_number": payment.get("receipt_number", ""),
        "notes": payment.get("notes", ""),
        "created_at": payment.get("created_at", "").isoformat() if isinstance(payment.get("created_at"), datetime) else str(payment.get("created_at", ""))
    }


def generate_receipt_number():
    """Generate receipt number: RCP-YYYYMMDD-XXXX"""
    now = datetime.utcnow()
    random_digits = random.randint(1000, 9999)
    return f"RCP-{now.strftime('%Y%m%d')}-{random_digits}"


# ─── GET /api/payments ───────────────────────────────────────
@payments_bp.route("/api/payments", methods=["GET"])
def get_payments():
    """Get all payments, optionally filtered by member_id."""
    try:
        database = db.get_db()

        query = {}
        member_id = request.args.get("member_id", "").strip()

        if member_id:
            # Look up member by member_id string (e.g., GYM001)
            member = database.members.find_one({"member_id": member_id})
            if member:
                query["member_id"] = member["_id"]
            else:
                # Try as ObjectId
                try:
                    query["member_id"] = ObjectId(member_id)
                except Exception:
                    return jsonify({"success": True, "data": [], "count": 0})

        payments = list(database.payments.find(query).sort("payment_date", -1))

        return jsonify({
            "success": True,
            "data": [serialize_payment(p) for p in payments],
            "count": len(payments)
        })

    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /api/payments ──────────────────────────────────────
@payments_bp.route("/api/payments", methods=["POST"])
def create_payment():
    """Create a new payment record."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        member_id_str = data.get("member_id", "").strip()
        plan_id_str = data.get("plan_id", "").strip()
        amount = data.get("amount", 0)
        payment_method = data.get("payment_method", "Cash")
        notes = data.get("notes", "")

        if not member_id_str:
            return jsonify({"success": False, "error": "Member ID is required"}), 400

        database = db.get_db()

        # Look up member
        member = database.members.find_one({"member_id": member_id_str})
        if not member:
            try:
                member = database.members.find_one({"_id": ObjectId(member_id_str)})
            except Exception:
                return jsonify({"success": False, "error": "Member not found"}), 404

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Get plan details
        plan_name = ""
        if plan_id_str:
            try:
                plan = database.plans.find_one({"_id": ObjectId(plan_id_str)})
                if plan:
                    plan_name = plan.get("plan_name", "")
            except Exception:
                pass

        if not plan_name:
            plan_name = member.get("plan_name", "Unknown")

        # Generate receipt number
        receipt_number = generate_receipt_number()

        now = datetime.utcnow()
        payment_doc = {
            "member_id": member["_id"],
            "member_name": member.get("full_name", ""),
            "plan_id": ObjectId(plan_id_str) if plan_id_str else None,
            "plan_name": plan_name,
            "amount": float(amount),
            "payment_date": now,
            "payment_method": payment_method,
            "status": "Paid",
            "receipt_number": receipt_number,
            "notes": notes,
            "created_at": now
        }

        result = database.payments.insert_one(payment_doc)
        payment_doc["_id"] = result.inserted_id

        # Send payment confirmation via SNS
        try:
            sns_manager.send_payment_confirmation(
                member_name=member.get("full_name", ""),
                email=member.get("email", ""),
                amount=float(amount),
                receipt_number=receipt_number,
                plan_name=plan_name
            )
        except Exception as e:
            logger.warning(f"Failed to send payment confirmation: {e}")

        return jsonify({
            "success": True,
            "data": serialize_payment(payment_doc),
            "message": f"Payment recorded. Receipt: {receipt_number}"
        }), 201

    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── GET /api/payments/summary ───────────────────────────────
@payments_bp.route("/api/payments/summary", methods=["GET"])
def get_payment_summary():
    """Get payment summary with revenue stats and breakdowns."""
    try:
        database = db.get_db()

        # Total revenue (sum of all paid payments)
        pipeline_total = [
            {"$match": {"status": "Paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        total_result = list(database.payments.aggregate(pipeline_total))
        total_revenue = total_result[0]["total"] if total_result else 0

        # This month's revenue
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pipeline_month = [
            {"$match": {"status": "Paid", "payment_date": {"$gte": month_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        month_result = list(database.payments.aggregate(pipeline_month))
        month_revenue = month_result[0]["total"] if month_result else 0

        # Payments by method breakdown
        pipeline_methods = [
            {"$match": {"status": "Paid"}},
            {"$group": {
                "_id": "$payment_method",
                "count": {"$sum": 1},
                "total": {"$sum": "$amount"}
            }}
        ]
        methods_result = list(database.payments.aggregate(pipeline_methods))
        payments_by_method = {}
        for method in methods_result:
            payments_by_method[method["_id"] or "Other"] = {
                "count": method["count"],
                "total": method["total"]
            }

        # Recent 5 payments
        recent_payments = list(
            database.payments.find().sort("payment_date", -1).limit(5)
        )

        # Total payment count
        total_count = database.payments.count_documents({"status": "Paid"})

        # Average payment
        avg_payment = total_revenue / total_count if total_count > 0 else 0

        return jsonify({
            "success": True,
            "data": {
                "total_revenue": total_revenue,
                "this_month_revenue": month_revenue,
                "total_payments": total_count,
                "average_payment": round(avg_payment, 2),
                "payments_by_method": payments_by_method,
                "recent_payments": [serialize_payment(p) for p in recent_payments]
            }
        })

    except Exception as e:
        logger.error(f"Error fetching payment summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
