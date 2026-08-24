"""
AI Meeting Notes Generator - Flask application entry point (Vercel edition).

This version is built to run as a Vercel serverless deployment: audio goes
to Vercel Blob storage, the database is Postgres (not local SQLite), and
transcription uses a hosted Whisper API instead of a local model - all
because Vercel's serverless functions have a read-only, ephemeral
filesystem and strict execution-time/memory limits. See README.md's
"Deploying to Vercel" section for the required environment variables.

For local development, run:
    python -m venv venv
    venv\\Scripts\\activate      (Windows)  |  source venv/bin/activate  (macOS/Linux)
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000 (you'll still need DATABASE_URL, a Blob
token, and API keys set in a local .env - see .env.example).
"""
import os
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from flask_login import current_user
from dotenv import load_dotenv

from extensions import login_manager
from models.database import init_db
from routes.meeting_routes import meeting_bp
from routes.transcription_routes import transcription_bp
from routes.export_routes import export_bp
from routes.auth_routes import auth_bp
from services import whisper_service

load_dotenv()


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
    # Keep this in step with audio_service.MAX_FILE_SIZE_MB. Vercel's own
    # serverless functions additionally cap request body size (commonly
    # ~4.5MB on the Hobby plan) - large uploads may hit that ceiling before
    # ever reaching this check. See README's "Deploying to Vercel" section.
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    CORS(app)
    init_db()

    login_manager.init_app(app)

    # Startup checks - warn loudly in the logs instead of only failing
    # silently later when someone tries to record/upload/transcribe.
    if not os.getenv("DATABASE_URL"):
        print("=" * 70)
        print("WARNING: DATABASE_URL is not set.")
        print("Connect a Postgres database (Vercel Postgres/Neon/Supabase all")
        print("work) and set DATABASE_URL in your environment variables.")
        print("=" * 70)
    if not os.getenv("BLOB_READ_WRITE_TOKEN"):
        print("=" * 70)
        print("WARNING: BLOB_READ_WRITE_TOKEN is not set.")
        print("Recording/upload will fail until you connect a Vercel Blob")
        print("store to this project (Storage tab in the Vercel dashboard).")
        print("=" * 70)
    if not whisper_service.is_configured():
        print("=" * 70)
        print("WARNING: HOSTED_WHISPER_API_KEY (or GROQ_API_KEY) is not set.")
        print("Transcription will fail until you add a free key from")
        print("https://console.groq.com/keys")
        print("=" * 70)
    if not os.getenv("OPENROUTER_API_KEY"):
        print("=" * 70)
        print("WARNING: OPENROUTER_API_KEY is not set.")
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
        return {"error": "File is too large for this deployment (see MAX_CONTENT_LENGTH / audio_service.MAX_FILE_SIZE_MB)."}, 413

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
