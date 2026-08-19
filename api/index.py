"""
Vercel serverless entrypoint.

Vercel's Python runtime (@vercel/python) looks for a WSGI-compatible `app`
object in the file referenced by vercel.json's build config. This just
re-exports the real Flask app defined at the project root in app.py -
kept as a thin wrapper here (rather than moving app.py itself into /api)
so the same app.py still works for local development via `python app.py`.
"""
import os
import sys

# Make the project root (one level up from /api) importable, since Vercel
# runs this file as the entrypoint and Python's default path resolution
# doesn't automatically include the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
