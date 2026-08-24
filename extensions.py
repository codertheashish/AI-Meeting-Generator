"""
Shared Flask extension instances (Flask-Login).

Kept in their own module - separate from app.py and routes/auth_routes.py -
so both can import the same `login_manager` object without a circular
import.

NOTE: Login is OPTIONAL in this app, not required. Routes do not use
Flask-Login's @login_required, so anonymous visitors can use the dashboard
directly. If someone does log in, their meetings are private to their
account; if they don't, meetings are stored under a shared "guest" bucket
(user_id = NULL) - the same behavior the app had before accounts existed.

Auth is email/password only - no OAuth/social login.
"""
from flask_login import LoginManager, UserMixin, current_user

login_manager = LoginManager()
login_manager.login_view = "auth.login_page"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"


class LoginUser(UserMixin):
    """Thin Flask-Login wrapper around a `users` table row (a plain dict)."""

    def __init__(self, user_row):
        self.id = str(user_row["id"])
        self.email = user_row["email"]
        self.name = user_row["name"] or user_row["email"].split("@")[0]
        self.avatar_url = user_row.get("avatar_url")


@login_manager.user_loader
def load_user(user_id):
    from models import database as db  # local import avoids a circular import at module load time
    row = db.get_user_by_id(int(user_id))
    return LoginUser(row) if row else None


def current_user_id():
    """
    Returns the logged-in user's id (int), or None if nobody is logged in.
    Used everywhere meetings are read/written so logged-in users get
    private data and anonymous visitors share the "guest" bucket.
    """
    return int(current_user.id) if current_user.is_authenticated else None
