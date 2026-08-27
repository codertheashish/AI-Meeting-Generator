"""
export_routes.py
-----------------
Endpoints for downloading meeting notes as PDF / DOCX / TXT, and for
emailing the notes via SMTP (credentials read from environment variables).
"""

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from flask import Blueprint, jsonify, send_file, request, current_app

from models import database as db
from services import export_service

export_bp = Blueprint("export_bp", __name__)


def _safe_filename(title):
    slug = re.sub(r"[^a-zA-Z0-9-_]+", "_", title.strip()) or "meeting"
    return slug[:60]


def _exports_dir():
    return current_app.config["EXPORT_FOLDER"]


@export_bp.route("/api/export/pdf/<int:meeting_id>", methods=["GET"])
def export_pdf(meeting_id):
    meeting = db.get_full_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404

    out_path = os.path.join(_exports_dir(), f"{_safe_filename(meeting['title'])}_{meeting_id}.pdf")
    try:
        export_service.export_pdf(meeting, out_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"PDF export failed: {exc}"}), 500

    return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))


@export_bp.route("/api/export/docx/<int:meeting_id>", methods=["GET"])
def export_docx(meeting_id):
    meeting = db.get_full_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404

    out_path = os.path.join(_exports_dir(), f"{_safe_filename(meeting['title'])}_{meeting_id}.docx")
    try:
        export_service.export_docx(meeting, out_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"DOCX export failed: {exc}"}), 500

    return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))


@export_bp.route("/api/export/txt/<int:meeting_id>", methods=["GET"])
def export_txt(meeting_id):
    meeting = db.get_full_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404

    out_path = os.path.join(_exports_dir(), f"{_safe_filename(meeting['title'])}_{meeting_id}.txt")
    try:
        export_service.export_txt(meeting, out_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"TXT export failed: {exc}"}), 500

    return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))


@export_bp.route("/api/email", methods=["POST"])
def email_notes():
    """
    Body JSON: {"meeting_id": int, "to": "someone@example.com", "message": "optional custom body"}
    Sends the meeting notes as a PDF attachment via SMTP.
    Credentials are read only from environment variables - never hardcoded.
    """
    data = request.get_json(silent=True) or {}
    meeting_id = data.get("meeting_id")
    to_email = data.get("to")

    if not meeting_id or not to_email:
        return jsonify({"success": False, "error": "'meeting_id' and 'to' are required."}), 400

    meeting = db.get_full_meeting(meeting_id)
    if not meeting:
        return jsonify({"success": False, "error": "Meeting not found."}), 404

    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"

    if not all([mail_server, mail_username, mail_password]):
        return jsonify({
            "success": False,
            "error": "Email is not configured. Set MAIL_SERVER, MAIL_USERNAME and MAIL_PASSWORD in your .env file.",
        }), 400

    # Build the PDF attachment
    pdf_path = os.path.join(_exports_dir(), f"{_safe_filename(meeting['title'])}_{meeting_id}.pdf")
    try:
        export_service.export_pdf(meeting, pdf_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"Could not prepare PDF attachment: {exc}"}), 500

    subject = data.get("subject") or f"Meeting Notes - {meeting['title']}"
    body = data.get("message") or (
        f"Hello Team,\n\nPlease find the meeting notes for \"{meeting['title']}\" attached.\n\n"
        f"Thanks,\nAI Meeting Generator"
    )

    msg = MIMEMultipart()
    msg["From"] = mail_sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_path))
        msg.attach(part)

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_sender, [to_email], msg.as_string())
    except smtplib.SMTPException as exc:
        return jsonify({"success": False, "error": f"Failed to send email: {exc}"}), 502
    except OSError as exc:
        return jsonify({"success": False, "error": f"Could not connect to mail server: {exc}"}), 502

    return jsonify({"success": True, "message": f"Notes emailed to {to_email}."})
