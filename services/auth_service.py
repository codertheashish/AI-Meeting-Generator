"""
Authentication helpers: password hashing and signed, time-limited tokens
for the "Forgot Password" flow.

Kept separate from routes/auth_routes.py so the hashing/token logic can be
unit-tested or reused (e.g. by a future CLI "create admin user" script)
without pulling in Flask request handling.
"""
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

RESET_TOKEN_MAX_AGE_SECONDS = 3600  # 1 hour


def hash_password(plain_password):
    return generate_password_hash(plain_password)


def verify_password(plain_password, password_hash):
    if not password_hash:
        return False
    return check_password_hash(password_hash, plain_password)


def _serializer():
    secret = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    return URLSafeTimedSerializer(secret, salt="password-reset")


def generate_reset_token(user_id):
    return _serializer().dumps({"user_id": user_id})


def verify_reset_token(token):
    """Returns the user_id if the token is valid and unexpired, else None."""
    try:
        data = _serializer().loads(token, max_age=RESET_TOKEN_MAX_AGE_SECONDS)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None
