"""
Authentication routes - email/password only (no OAuth/social login).

- Signup, login, logout (session-based via Flask-Login)
- Forgot / reset password (token emailed via the same SMTP config used
  for meeting-notes emails)
"""
import os
import re
import smtplib
import traceback
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import LoginUser
from models import database as db
from services import auth_service

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# Email / password
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET"])
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("signup.html")


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if db.get_user_by_email(email):
        return jsonify({"error": "An account with this email already exists. Try logging in instead."}), 409

    user_id = db.create_user(email=email, name=name, password_hash=auth_service.hash_password(password))
    user_row = db.get_user_by_id(user_id)
    login_user(LoginUser(user_row))
    return jsonify({"success": True, "redirect": url_for("index")})


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    user_row = db.get_user_by_email(email)
    if not user_row or not auth_service.verify_password(password, user_row.get("password_hash")):
        return jsonify({"error": "Incorrect email or password."}), 401

    login_user(LoginUser(user_row), remember=bool(data.get("remember")))
    return jsonify({"success": True, "redirect": url_for("index")})


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------

@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")


@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    user_row = db.get_user_by_email(email)

    # Always return success even if the email isn't registered - this is
    # standard practice so the form can't be used to enumerate accounts.
    if not user_row or not user_row.get("password_hash"):
        return jsonify({"success": True})

    token = auth_service.generate_reset_token(user_row["id"])
    reset_url = url_for("auth.reset_password_page", token=token, _external=True)

    try:
        _send_reset_email(user_row["email"], reset_url)
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Couldn't send the reset email. Check your SMTP settings in .env."}), 502

    return jsonify({"success": True})


def _send_reset_email(to_email, reset_url):
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)

    if not mail_username or not mail_password:
        raise RuntimeError("Email is not configured (MAIL_USERNAME / MAIL_PASSWORD missing in .env).")

    msg = EmailMessage()
    msg["Subject"] = "Reset your AI Meeting Notes password"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(
        "Hello,\n\nWe received a request to reset your password. This link expires in 1 hour:\n\n"
        f"{reset_url}\n\nIf you didn't request this, you can safely ignore this email.\n\n"
        "Thanks,\nAI Meeting Notes Generator"
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)


@auth_bp.route("/reset-password/<token>", methods=["GET"])
def reset_password_page(token):
    user_id = auth_service.verify_reset_token(token)
    if not user_id:
        return render_template("reset_password.html", token=None)
    return render_template("reset_password.html", token=token)


@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") or ""
    password = data.get("password") or ""

    user_id = auth_service.verify_reset_token(token)
    if not user_id:
        return jsonify({"error": "This reset link is invalid or has expired. Request a new one."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    db.update_user_password(user_id, auth_service.hash_password(password))
    return jsonify({"success": True, "redirect": url_for("auth.login_page")})
