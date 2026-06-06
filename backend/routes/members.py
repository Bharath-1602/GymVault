"""
GymVault - Members API Routes
Handles all member CRUD operations, photo upload/download, and membership renewal.
"""

import logging
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from bson import ObjectId
from flask import Blueprint, request, jsonify
from database import db
from s3_manager import s3_manager
from sns_manager import sns_manager
from config import allowed_file, MAX_PHOTO_SIZE

logger = logging.getLogger(__name__)
members_bp = Blueprint("members", __name__)


def calculate_status(membership_end):
    """Auto-calculate member status based on end date."""
    if not membership_end:
        return "Expired"
    now = datetime.utcnow()
    if membership_end < now:
        return "Expired"
    elif membership_end <= now + timedelta(days=7):
        return "Expiring Soon"
    else:
        return "Active"


def serialize_member(member):
    """Convert MongoDB member document to JSON-serializable dict with fresh presigned URL."""
    if not member:
        return None

    # Recalculate status
    status = calculate_status(member.get("membership_end"))

    # Generate fresh presigned URL for photo
    photo_url = ""
    s3_key = member.get("photo_s3_key", "")
    if s3_key:
        try:
            photo_url = s3_manager.get_presigned_url(s3_key)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL: {e}")

    return {
        "_id": str(member.get("_id", "")),
        "member_id": member.get("member_id", ""),
        "full_name": member.get("full_name", ""),
        "email": member.get("email", ""),
        "phone": member.get("phone", ""),
        "age": member.get("age", 0),
        "gender": member.get("gender", ""),
        "address": member.get("address", ""),
        "photo_s3_key": s3_key,
        "photo_url": photo_url,
        "plan_id": str(member.get("plan_id", "")),
        "plan_name": member.get("plan_name", ""),
        "membership_start": member.get("membership_start", "").isoformat() if isinstance(member.get("membership_start"), datetime) else str(member.get("membership_start", "")),
        "membership_end": member.get("membership_end", "").isoformat() if isinstance(member.get("membership_end"), datetime) else str(member.get("membership_end", "")),
        "status": status,
        "created_at": member.get("created_at", "").isoformat() if isinstance(member.get("created_at"), datetime) else str(member.get("created_at", "")),
        "updated_at": member.get("updated_at", "").isoformat() if isinstance(member.get("updated_at"), datetime) else str(member.get("updated_at", ""))
    }


def generate_member_id():
    """Generate sequential member ID: GYM001, GYM002, etc."""
    database = db.get_db()
    count = database.members.count_documents({})
    return "GYM" + str(count + 1).zfill(3)


# ─── GET /api/members ────────────────────────────────────────
@members_bp.route("/api/members", methods=["GET"])
def get_members():
    """Get all members with optional status filter and search."""
    try:
        database = db.get_db()

        # Build query filter
        query = {}
        status_filter = request.args.get("status", "").strip()
        search_query = request.args.get("search", "").strip()

        if search_query:
            query["$or"] = [
                {"full_name": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
                {"member_id": {"$regex": search_query, "$options": "i"}}
            ]

        members = list(database.members.find(query).sort("created_at", -1))

        # Serialize and recalculate status
        serialized = [serialize_member(m) for m in members]

        # Apply status filter AFTER recalculation
        if status_filter and status_filter.lower() != "all":
            status_map = {
                "active": "Active",
                "expiring soon": "Expiring Soon",
                "expiring_soon": "Expiring Soon",
                "expired": "Expired"
            }
            target_status = status_map.get(status_filter.lower(), status_filter)
            serialized = [m for m in serialized if m["status"] == target_status]

        return jsonify({
            "success": True,
            "data": serialized,
            "count": len(serialized)
        })

    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── GET /api/members/<member_id> ────────────────────────────
@members_bp.route("/api/members/<member_id>", methods=["GET"])
def get_member(member_id):
    """Get a single member by member_id (e.g., GYM001)."""
    try:
        database = db.get_db()
        member = database.members.find_one({"member_id": member_id})

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        return jsonify({
            "success": True,
            "data": serialize_member(member)
        })

    except Exception as e:
        logger.error(f"Error fetching member {member_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /api/members ───────────────────────────────────────
@members_bp.route("/api/members", methods=["POST"])
def create_member():
    """
    Create a new member with photo upload.
    Accepts multipart/form-data.
    """
    try:
        database = db.get_db()

        # Extract form fields
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        age = request.form.get("age", 0)
        gender = request.form.get("gender", "Other")
        address = request.form.get("address", "").strip()
        plan_id = request.form.get("plan_id", "").strip()

        # Validate required fields
        if not full_name:
            return jsonify({"success": False, "error": "Full name is required"}), 400
        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400
        if not phone:
            return jsonify({"success": False, "error": "Phone is required"}), 400
        if not plan_id:
            return jsonify({"success": False, "error": "Plan selection is required"}), 400

        # Check for duplicate email
        existing = database.members.find_one({"email": email})
        if existing:
            return jsonify({"success": False, "error": "A member with this email already exists"}), 409

        # Get plan details
        try:
            plan = database.plans.find_one({"_id": ObjectId(plan_id)})
        except Exception:
            return jsonify({"success": False, "error": "Invalid plan ID"}), 400

        if not plan:
            return jsonify({"success": False, "error": "Plan not found"}), 404

        # Generate member ID
        member_id = generate_member_id()

        # Handle photo upload
        photo_s3_key = ""
        if "photo" in request.files:
            photo = request.files["photo"]
            if photo and photo.filename:
                if not allowed_file(photo.filename):
                    return jsonify({"success": False, "error": "Invalid file type. Allowed: png, jpg, jpeg, gif, webp"}), 400

                file_bytes = photo.read()
                if len(file_bytes) > MAX_PHOTO_SIZE:
                    return jsonify({"success": False, "error": "Photo exceeds 5MB limit"}), 400

                try:
                    photo_s3_key = s3_manager.upload_member_photo(
                        member_id=member_id,
                        file_bytes=file_bytes,
                        content_type=photo.content_type or "image/jpeg"
                    )
                except Exception as e:
                    logger.error(f"Failed to upload photo: {e}")
                    # Continue without photo - don't fail member creation

        # Calculate membership dates
        now = datetime.utcnow()
        duration_months = plan.get("duration_months", 1)
        membership_end = now + timedelta(days=duration_months * 30)

        # Create member document
        member_doc = {
            "member_id": member_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "age": int(age) if age else 0,
            "gender": gender,
            "address": address,
            "photo_s3_key": photo_s3_key,
            "plan_id": ObjectId(plan_id),
            "plan_name": plan.get("plan_name", ""),
            "membership_start": now,
            "membership_end": membership_end,
            "status": "Active",
            "created_at": now,
            "updated_at": now
        }

        result = database.members.insert_one(member_doc)
        member_doc["_id"] = result.inserted_id

        # Send SNS welcome notification (non-blocking)
        try:
            sns_manager.send_welcome_notification(
                member_name=full_name,
                email=email,
                plan_name=plan.get("plan_name", ""),
                end_date=membership_end.strftime("%B %d, %Y")
            )
        except Exception as e:
            logger.warning(f"Failed to send welcome notification: {e}")

        return jsonify({
            "success": True,
            "data": serialize_member(member_doc),
            "message": f"Member {member_id} created successfully"
        }), 201

    except Exception as e:
        logger.error(f"Error creating member: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── PUT /api/members/<member_id> ────────────────────────────
@members_bp.route("/api/members/<member_id>", methods=["PUT"])
def update_member(member_id):
    """Update member details. Handles optional new photo upload."""
    try:
        database = db.get_db()
        member = database.members.find_one({"member_id": member_id})

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Build update document
        update_fields = {}

        # Handle form data (multipart) or JSON
        if request.content_type and "multipart/form-data" in request.content_type:
            form = request.form
        else:
            form = request.get_json() or {}

        # Update text fields if provided
        field_mappings = {
            "full_name": "full_name",
            "email": "email",
            "phone": "phone",
            "age": "age",
            "gender": "gender",
            "address": "address"
        }

        for form_key, db_key in field_mappings.items():
            value = form.get(form_key)
            if value is not None:
                if db_key == "age":
                    update_fields[db_key] = int(value) if value else 0
                else:
                    update_fields[db_key] = str(value).strip()

        # Handle plan change
        new_plan_id = form.get("plan_id")
        if new_plan_id:
            try:
                plan = database.plans.find_one({"_id": ObjectId(new_plan_id)})
                if plan:
                    update_fields["plan_id"] = ObjectId(new_plan_id)
                    update_fields["plan_name"] = plan.get("plan_name", "")
            except Exception:
                pass

        # Handle new photo upload
        if request.files and "photo" in request.files:
            photo = request.files["photo"]
            if photo and photo.filename:
                if allowed_file(photo.filename):
                    file_bytes = photo.read()
                    if len(file_bytes) <= MAX_PHOTO_SIZE:
                        # Delete old photo from S3
                        old_s3_key = member.get("photo_s3_key", "")
                        if old_s3_key:
                            try:
                                s3_manager.delete_member_photo(old_s3_key)
                            except Exception as e:
                                logger.warning(f"Failed to delete old photo: {e}")

                        # Upload new photo
                        try:
                            new_s3_key = s3_manager.upload_member_photo(
                                member_id=member_id,
                                file_bytes=file_bytes,
                                content_type=photo.content_type or "image/jpeg"
                            )
                            update_fields["photo_s3_key"] = new_s3_key
                        except Exception as e:
                            logger.error(f"Failed to upload new photo: {e}")

        if not update_fields:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        update_fields["updated_at"] = datetime.utcnow()

        database.members.update_one(
            {"member_id": member_id},
            {"$set": update_fields}
        )

        # Fetch updated member
        updated_member = database.members.find_one({"member_id": member_id})

        return jsonify({
            "success": True,
            "data": serialize_member(updated_member),
            "message": f"Member {member_id} updated successfully"
        })

    except Exception as e:
        logger.error(f"Error updating member {member_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── DELETE /api/members/<member_id> ─────────────────────────
@members_bp.route("/api/members/<member_id>", methods=["DELETE"])
def delete_member(member_id):
    """Delete a member and their S3 photo."""
    try:
        database = db.get_db()
        member = database.members.find_one({"member_id": member_id})

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Delete photo from S3
        s3_key = member.get("photo_s3_key", "")
        if s3_key:
            try:
                s3_manager.delete_member_photo(s3_key)
            except Exception as e:
                logger.warning(f"Failed to delete S3 photo for {member_id}: {e}")

        # Delete member from MongoDB
        database.members.delete_one({"member_id": member_id})

        # Also delete associated checkins
        database.checkins.delete_many({"member_id": member.get("_id")})

        return jsonify({
            "success": True,
            "message": f"Member {member_id} deleted successfully"
        })

    except Exception as e:
        logger.error(f"Error deleting member {member_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── PUT /api/members/<member_id>/renew ──────────────────────
@members_bp.route("/api/members/<member_id>/renew", methods=["PUT"])
def renew_member(member_id):
    """
    Renew a member's membership.
    Extends membership, creates payment record, sends SNS notification.
    """
    try:
        database = db.get_db()
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        plan_id = data.get("plan_id", "").strip()
        payment_method = data.get("payment_method", "Cash")

        if not plan_id:
            return jsonify({"success": False, "error": "Plan ID is required"}), 400

        # Get member
        member = database.members.find_one({"member_id": member_id})
        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Get plan
        try:
            plan = database.plans.find_one({"_id": ObjectId(plan_id)})
        except Exception:
            return jsonify({"success": False, "error": "Invalid plan ID"}), 400

        if not plan:
            return jsonify({"success": False, "error": "Plan not found"}), 404

        # Calculate new membership end date
        now = datetime.utcnow()
        current_end = member.get("membership_end", now)
        # If expired, start from now; if active, extend from current end
        start_from = max(current_end, now)
        duration_months = plan.get("duration_months", 1)
        new_end = start_from + timedelta(days=duration_months * 30)

        # Generate receipt number
        import random
        receipt_number = f"RCP-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        # Create payment record
        payment_doc = {
            "member_id": member.get("_id"),
            "member_name": member.get("full_name", ""),
            "plan_id": ObjectId(plan_id),
            "plan_name": plan.get("plan_name", ""),
            "amount": plan.get("price", 0),
            "payment_date": now,
            "payment_method": payment_method,
            "status": "Paid",
            "receipt_number": receipt_number,
            "notes": f"Membership renewal - {plan.get('plan_name', '')}",
            "created_at": now
        }
        database.payments.insert_one(payment_doc)

        # Update member
        database.members.update_one(
            {"member_id": member_id},
            {"$set": {
                "plan_id": ObjectId(plan_id),
                "plan_name": plan.get("plan_name", ""),
                "membership_end": new_end,
                "status": "Active",
                "updated_at": now
            }}
        )

        # Send payment confirmation
        try:
            sns_manager.send_payment_confirmation(
                member_name=member.get("full_name", ""),
                email=member.get("email", ""),
                amount=plan.get("price", 0),
                receipt_number=receipt_number,
                plan_name=plan.get("plan_name", "")
            )
        except Exception as e:
            logger.warning(f"Failed to send payment confirmation: {e}")

        # Fetch updated member
        updated_member = database.members.find_one({"member_id": member_id})

        return jsonify({
            "success": True,
            "data": {
                "member": serialize_member(updated_member),
                "payment": {
                    "_id": str(payment_doc.get("_id", "")),
                    "receipt_number": receipt_number,
                    "amount": plan.get("price", 0),
                    "payment_method": payment_method,
                    "status": "Paid"
                }
            },
            "message": f"Membership renewed for {member.get('full_name', '')} until {new_end.strftime('%B %d, %Y')}"
        })

    except Exception as e:
        logger.error(f"Error renewing member {member_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
