"""
meeting_routes.py
------------------
CRUD endpoints for meetings, plus action-item editing/completion toggling.
"""

from flask import Blueprint, request, jsonify
from models import database as db

meeting_bp = Blueprint("meeting_bp", __name__)


@meeting_bp.route("/api/meetings", methods=["GET"])
def list_meetings():
    try:
        meetings = db.list_meetings()
        return jsonify({"success": True, "meetings": meetings})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": str(exc)}), 500


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["GET"])
def get_meeting(meeting_id):
    meeting = db.get_full_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404
    return jsonify({"success": True, "meeting": meeting})


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["DELETE"])
def delete_meeting(meeting_id):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404
    db.delete_meeting(meeting_id)
    return jsonify({"success": True})


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["PATCH"])
def update_meeting_title(meeting_id):
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in data.items() if k in ("title", "date")}
    if not fields:
        return jsonify({"success": False, "error": "Nothing to update."}), 400
    db.update_meeting(meeting_id, **fields)
    return jsonify({"success": True, "meeting": db.get_meeting(meeting_id)})


@meeting_bp.route("/api/action-items/<int:item_id>", methods=["PATCH"])
def update_action_item(item_id):
    """Allows editing task/assignee/deadline and toggling completion."""
    data = request.get_json(silent=True) or {}
    allowed = {"task", "assigned_to", "deadline", "completed"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({"success": False, "error": "Nothing to update."}), 400
    if "completed" in fields:
        fields["completed"] = int(bool(fields["completed"]))
    db.update_action_item(item_id, **fields)
    return jsonify({"success": True})
