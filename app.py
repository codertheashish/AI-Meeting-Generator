"""
AI Meeting Notes Generator - Flask application entry point.

Run locally with:
    python -m venv venv
    venv\\Scripts\\activate      (Windows)  |  source venv/bin/activate  (macOS/Linux)
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000
"""
import os
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from flask_login import current_user
from dotenv import load_dotenv

from extensions import login_manager, oauth
from models.database import init_db
from routes.meeting_routes import meeting_bp
from routes.transcription_routes import transcription_bp
from routes.export_routes import export_bp
from routes.auth_routes import auth_bp
from services.audio_service import is_ffmpeg_available

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _register_oauth_clients():
    """
    Register an OAuth client per provider ONLY if its credentials are
    present in .env. Missing credentials simply disable that login button
    (see routes/auth_routes.py::_configured_providers) instead of crashing
    the app at startup.
    """
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    if os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET"):
        oauth.register(
            name="linkedin",
            client_id=os.getenv("LINKEDIN_CLIENT_ID"),
            client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
            access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
            authorize_url="https://www.linkedin.com/oauth/v2/authorization",
            api_base_url="https://api.linkedin.com/v2/",
            client_kwargs={"scope": "openid profile email"},
        )

    if os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"):
        oauth.register(
            name="github",
            client_id=os.getenv("GITHUB_CLIENT_ID"),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "read:user user:email"},
        )


def _request_wants_json():
    """
    Treat requests as API calls (fetch/XHR) if the path starts with /api/
    - simpler and more reliable than sniffing Accept headers, since our
    frontend's fetch() calls don't always set a strict Accept header.
    """
    return request.path.startswith("/api/")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    app.config["UPLOAD_DIR"] = os.path.join(BASE_DIR, "uploads")
    app.config["EXPORT_DIR"] = os.path.join(BASE_DIR, "exports")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB upload cap

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)

    CORS(app)
    init_db()

    login_manager.init_app(app)
    oauth.init_app(app)
    _register_oauth_clients()

    # Startup checks - warn loudly in the terminal instead of only failing
    # silently later when the user tries to transcribe something.
    if not is_ffmpeg_available():
        print("=" * 70)
        print("WARNING: FFmpeg was not found on your system PATH.")
        print("Recording/upload will fail at the transcription step until")
        print("FFmpeg is installed. Download it from https://ffmpeg.org/download.html")
        print("and make sure 'ffmpeg' and 'ffprobe' work from a terminal.")
        print("=" * 70)
    if not os.getenv("OPENROUTER_API_KEY"):
        print("=" * 70)
        print("WARNING: OPENROUTER_API_KEY is not set in your .env file.")
        print("AI note generation will fail until you add a free key from")
        print("https://openrouter.ai/keys")
        print("=" * 70)

    app.register_blueprint(auth_bp)
    app.register_blueprint(meeting_bp)
    app.register_blueprint(transcription_bp)
    app.register_blueprint(export_bp)

    @app.route("/")
    def index():
        # Login is optional - render the dashboard for anyone, logged in or
        # not. `current_user` is Flask-Login's AnonymousUserMixin when
        # nobody's logged in, so the template checks .is_authenticated
        # before touching .name/.email/.avatar_url.
        return render_template("index.html", user=current_user)

    @login_manager.unauthorized_handler
    def unauthorized():
        # Nothing in this app requires login, but keep a safe fallback in
        # case a future @login_required route is added.
        if _request_wants_json():
            return jsonify({"error": "Please log in to continue.", "login_required": True}), 401
        return redirect(url_for("auth.login_page"))

    @app.errorhandler(413)
    def too_large(e):
        return {"error": "File is too large. Max upload size is 500MB."}, 413

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Resource not found."}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {"error": "Internal server error."}, 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
