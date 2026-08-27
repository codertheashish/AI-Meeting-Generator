"""
app.py
------
AI Meeting Generator - Flask application entrypoint.

Run locally with:
    python -m venv venv
    venv\\Scripts\\activate      (Windows)   or   source venv/bin/activate   (macOS/Linux)
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000
"""

import os
from flask import Flask, render_template, session
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env into os.environ

from models.database import init_db
from routes.meeting_routes import meeting_bp
from routes.transcription_routes import transcription_bp
from routes.export_routes import export_bp
from routes.auth_routes import auth_bp, init_oauth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
    app.config["EXPORT_FOLDER"] = os.path.join(BASE_DIR, "exports")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload cap

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

    CORS(app)

    # Google OAuth (Authlib) - reads GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from env
    init_oauth(app)

    # Initialize SQLite schema on boot
    init_db()

    # Register API blueprints
    app.register_blueprint(meeting_bp)
    app.register_blueprint(transcription_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(auth_bp)

    @app.route("/")
    def index():
        user = session.get("user")
        return render_template("index.html", user=user)

    @app.route("/api/health")
    def health():
        return {"success": True, "status": "AI Meeting Generator API is running."}

    @app.errorhandler(413)
    def file_too_large(_e):
        return {"success": False, "error": "File is too large. Maximum upload size is 500MB."}, 413

    @app.errorhandler(404)
    def not_found(_e):
        return {"success": False, "error": "Endpoint not found."}, 404

    @app.errorhandler(500)
    def server_error(_e):
        return {"success": False, "error": "Internal server error. Please try again."}, 500

    return app


app = create_app()

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    print("=" * 60)
    print(" AI Meeting Generator")
    print(" Running at: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
