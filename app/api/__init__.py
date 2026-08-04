"""Shared helpers for the API blueprints.

Authentication and role checks use Flask-Security's own decorators:

    @auth_required("token")     -- must send a valid Authentication-Token
    @roles_required("admin")    -- must additionally hold that role

`blocked_check` is ours, because "blacklisted" is our own concept.
"""

from functools import wraps

from flask import jsonify
from flask_security import current_user


def error(message, status=400):
    """Every failure in the API returns this shape, so the UI has one path."""
    return jsonify({"error": message}), status


def blocked_check(fn):
    """Reject a logged-in user who has been blacklisted by the admin."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user.is_blacklisted:
            return error("Your account has been blacklisted.", 403)
        return fn(*args, **kwargs)

    return wrapper


def require_fields(data, *names):
    """Return the name of the first missing/empty field, or None if all present."""
    if not isinstance(data, dict):
        return "body"
    for name in names:
        value = data.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            return name
    return None
