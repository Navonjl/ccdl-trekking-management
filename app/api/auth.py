"""Registration, "who am I", and profile editing.

Login and logout are NOT in this file. Flask-Security already provides them at

    POST /api/accounts/login    -> returns the Authentication-Token
    POST /api/accounts/logout

(the /api/accounts prefix comes from SECURITY_URL_PREFIX in app/config.py).
Rewriting them here would only duplicate the token handling we get for free.

Registration IS ours, because Flask-Security's own /register would let the
caller pick fields we do not want them near, and the spec allows
self-registration for trekkers only. SECURITY_REGISTERABLE is therefore False.
"""

from flask import Blueprint, jsonify, request
from flask_security import auth_required, current_user, hash_password

from ..extensions import db, security
from ..models import ROLE_USER
from . import blocked_check, error, require_fields

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.post("/register")
def register():
    """Self-registration, trekker only.

    The role is hard-coded to "user" below. There is deliberately no "role"
    field read from the request body, so nobody can register as admin or
    staff -- staff accounts are created by the admin, and the single admin is
    created by the `flask init-db` command.
    """
    data = request.get_json(silent=True)

    missing = require_fields(data, "email", "password", "full_name", "phone")
    if missing:
        return error(f"{missing} is required.")

    email = data["email"].strip().lower()
    password = data["password"]
    full_name = data["full_name"].strip()
    phone = data["phone"].strip()

    # Backend validation. The Vue forms check the same things, but a form is
    # not a security boundary -- anyone can POST here with curl.
    if "@" not in email or "." not in email:
        return error("Please give a valid email address.")
    if len(password) < 6:
        return error("Password must be at least 6 characters.")
    if not phone.isdigit() or len(phone) != 10:
        return error("Phone must be 10 digits.")

    if security.datastore.find_user(email=email):
        return error("An account with that email already exists.")

    user = security.datastore.create_user(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        phone=phone,
        roles=[ROLE_USER],
    )
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.get("/me")
@auth_required("token")
def me():
    """Who am I? The SPA calls this on page load to rebuild its navbar.

    to_dict() already includes the role names, which is what the frontend
    router uses to decide which dashboard to show.
    """
    return jsonify(current_user.to_dict())


@auth_bp.put("/profile")
@auth_required("token")
@blocked_check
def update_profile():
    """A user edits their OWN profile. There is no user id in the URL, so this
    route can never be used to edit somebody else's account.

    Email is not editable: it is the login identifier, and changing it would
    invalidate the account the admin sees in their user list.
    """
    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        full_name = str(data["full_name"]).strip()
        if not full_name:
            return error("full_name cannot be empty.")
        current_user.full_name = full_name

    if "phone" in data:
        phone = str(data["phone"]).strip()
        if not phone.isdigit() or len(phone) != 10:
            return error("Phone must be 10 digits.")
        current_user.phone = phone

    # Password is optional: only touched when the field is actually sent.
    if data.get("password"):
        if len(data["password"]) < 6:
            return error("Password must be at least 6 characters.")
        current_user.password = hash_password(data["password"])

    db.session.commit()
    return jsonify(current_user.to_dict())
