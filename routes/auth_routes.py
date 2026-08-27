"""
auth_routes.py
---------------
Real Google Sign-In (OAuth 2.0) using Authlib.

Flow:
  GET  /login            -> redirects the browser to Google's consent screen
  GET  /login/callback   -> Google redirects back here with a code; we
                             exchange it for the user's profile and store
                             {email, name, picture} in the Flask session
  GET  /logout            -> clears the session

Credentials come ONLY from environment variables (.env):
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_REDIRECT_URI   (defaults to http://127.0.0.1:5000/login/callback)
"""

import os
from flask import Blueprint, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth

auth_bp = Blueprint("auth_bp", __name__)

oauth = OAuth()

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


def init_oauth(app):
    """Call once from app.py after the Flask app is created."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={"scope": "openid email profile"},
    )


@auth_bp.route("/login")
def login():
    if not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        return jsonify({
            "success": False,
            "error": "Google login is not configured. Set GOOGLE_CLIENT_ID and "
                     "GOOGLE_CLIENT_SECRET in your .env file.",
        }), 400

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", url_for("auth_bp.callback", _external=True))
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/login/callback")
def callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo") or oauth.google.userinfo()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"Google sign-in failed: {exc}"}), 400

    session["user"] = {
        "email": user_info.get("email"),
        "name": user_info.get("name") or user_info.get("email", "User"),
        "picture": user_info.get("picture"),
    }
    return redirect(url_for("index"))


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@auth_bp.route("/api/me")
def me():
    user = session.get("user")
    if not user:
        return jsonify({"success": True, "authenticated": False, "user": None})
    return jsonify({"success": True, "authenticated": True, "user": user})
