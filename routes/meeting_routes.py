"""Meeting CRUD endpoints, plus a read-only settings/status endpoint.

Login is OPTIONAL here, not required. Logged-in users only ever see their
own meetings; anonymous visitors share a single "guest" bucket (the same
behavior the app had before accounts existed) - see extensions.current_user_id().
"""
import os
from flask import Blueprint, jsonify, request

from extensions import current_user_id
from models import database as db
from services import audio_service

meeting_bp = Blueprint("meetings", __name__)


@meeting_bp.route("/api/settings", methods=["GET"])
def get_settings():
    """
    Read-only view of the app's current configuration, for the Settings
    panel in the UI. Never returns the actual API key - only whether one
    is configured - since secrets must stay backend-only.
    """
    return jsonify({
        "whisper_model": os.getenv("WHISPER_MODEL", "small"),
        "whisper_device": os.getenv("WHISPER_DEVICE", "cpu"),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "openrouter_key_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        "mail_configured": bool(os.getenv("MAIL_USERNAME") and os.getenv("MAIL_PASSWORD")),
        "ffmpeg_available": audio_service.is_ffmpeg_available(),
    })


@meeting_bp.route("/api/meetings", methods=["GET"])
def list_meetings():
    return jsonify({"meetings": db.list_meetings(user_id=current_user_id())})


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["GET"])
def get_meeting(meeting_id):
    meeting = db.get_meeting(meeting_id, user_id=current_user_id())
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    return jsonify({"meeting": meeting})


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["DELETE"])
def delete_meeting(meeting_id):
    meeting = db.get_meeting(meeting_id, user_id=current_user_id())
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    db.delete_meeting(meeting_id, user_id=current_user_id())
    return jsonify({"success": True})


@meeting_bp.route("/api/meetings/<int:meeting_id>", methods=["PATCH"])
def update_meeting(meeting_id):
    meeting = db.get_meeting(meeting_id, user_id=current_user_id())
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    data = request.get_json(force=True, silent=True) or {}
    allowed = {"title", "duration", "summary", "key_highlights", "decisions", "follow_up_points"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if "title" in updates:
        updates["title"] = (updates["title"] or "").strip() or "Untitled Meeting"
    if updates:
        db.update_meeting(meeting_id, **updates)
    return jsonify({"meeting": db.get_meeting(meeting_id, user_id=current_user_id())})


@meeting_bp.route("/api/action-items/<int:item_id>", methods=["PATCH"])
def update_action_item(item_id):
    """Edit an action item's task/assignee/deadline, or toggle completion."""
    if not db.action_item_belongs_to_user(item_id, current_user_id()):
        return jsonify({"error": "Action item not found."}), 404
    data = request.get_json(force=True, silent=True) or {}
    allowed = {"task", "assigned_to", "deadline", "priority", "completed"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update."}), 400
    db.update_action_item(item_id, **updates)
    return jsonify({"success": True})
