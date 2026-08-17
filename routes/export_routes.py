"""Export (PDF/DOCX/TXT) and email-sending endpoints.

Downloaded/emailed filenames use the meeting's own title (e.g.
"Project_Sync_Notes.pdf") instead of a generic "meeting_<id>_notes.pdf" -
renaming a meeting (PATCH /api/meetings/<id> with {"title": "..."}) changes
what the exported file is called too.
"""
import os
import re
import smtplib
import traceback
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, request, send_file

from extensions import current_user_id
from models import database as db
from services import export_service

export_bp = Blueprint("export", __name__)


def _export_dir():
    return current_app.config["EXPORT_DIR"]


def _get_meeting_or_404(meeting_id):
    return db.get_meeting(meeting_id, user_id=current_user_id())


def _download_filename(meeting, extension):
    """Turn a meeting title into a safe, human-readable filename."""
    title = (meeting.get("title") or "Untitled Meeting").strip()
    slug = re.sub(r"[^\w\s-]", "", title)          # strip punctuation
    slug = re.sub(r"[\s]+", "_", slug).strip("_")  # spaces -> underscores
    slug = slug or "Untitled_Meeting"
    return f"{slug}_Notes.{extension}"


@export_bp.route("/api/export/pdf/<int:meeting_id>", methods=["GET"])
def export_pdf(meeting_id):
    meeting = _get_meeting_or_404(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    try:
        path = export_service.export_pdf(meeting, _export_dir())
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to generate PDF."}), 500
    return send_file(path, as_attachment=True, download_name=_download_filename(meeting, "pdf"))


@export_bp.route("/api/export/docx/<int:meeting_id>", methods=["GET"])
def export_docx(meeting_id):
    meeting = _get_meeting_or_404(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    try:
        path = export_service.export_docx(meeting, _export_dir())
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to generate DOCX."}), 500
    return send_file(path, as_attachment=True, download_name=_download_filename(meeting, "docx"))


@export_bp.route("/api/export/txt/<int:meeting_id>", methods=["GET"])
def export_txt(meeting_id):
    meeting = _get_meeting_or_404(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404
    try:
        path = export_service.export_txt(meeting, _export_dir())
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to generate TXT."}), 500
    return send_file(path, as_attachment=True, download_name=_download_filename(meeting, "txt"))


@export_bp.route("/api/email", methods=["POST"])
def send_email():
    """
    Body: { "meeting_id": <int>, "to": "someone@example.com", "format": "pdf"|"docx"|"txt" }
    Sends the meeting notes as an email attachment via SMTP.
    Credentials are read from environment variables - never hardcoded.
    """
    data = request.get_json(force=True, silent=True) or {}
    meeting_id = data.get("meeting_id")
    to_email = data.get("to")
    fmt = data.get("format", "pdf")

    if not meeting_id or not to_email:
        return jsonify({"error": "meeting_id and 'to' email address are required."}), 400

    meeting = _get_meeting_or_404(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found."}), 404

    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)

    if not mail_username or not mail_password:
        return jsonify({"error": "Email is not configured. Set MAIL_USERNAME and MAIL_PASSWORD in .env."}), 500

    try:
        exporters = {"pdf": export_service.export_pdf, "docx": export_service.export_docx, "txt": export_service.export_txt}
        if fmt not in exporters:
            return jsonify({"error": "format must be one of: pdf, docx, txt"}), 400
        attachment_path = exporters[fmt](meeting, _export_dir())
        attachment_filename = _download_filename(meeting, fmt)

        msg = EmailMessage()
        msg["Subject"] = f"Meeting Notes - {meeting.get('title', 'Meeting')}"
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(
            f"Hello,\n\nPlease find attached the meeting notes for "
            f"\"{meeting.get('title','')}\" held on {meeting.get('date','')}.\n\n"
            f"Summary:\n{meeting.get('summary','')}\n\n"
            f"Thanks,\nAI Meeting Notes Generator"
        )

        with open(attachment_path, "rb") as f:
            file_data = f.read()
        mime_map = {"pdf": ("application", "pdf"), "docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"), "txt": ("text", "plain")}
        maintype, subtype = mime_map[fmt]
        msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=attachment_filename)

        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)

    except smtplib.SMTPAuthenticationError as exc:
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Gmail rejected the login credentials. If you're using Gmail, you need an "
                     "App Password (not your normal password) - see "
                     "https://support.google.com/accounts/answer/185833"
        }), 502
    except smtplib.SMTPException as exc:
        return jsonify({"error": f"Email failed to send: {exc}"}), 502
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Unexpected error while sending email."}), 500

    return jsonify({"success": True, "sent_to": to_email})
