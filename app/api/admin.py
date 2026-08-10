"""Admin endpoints: /api/admin/...

Everything here needs a valid token AND the admin role, so every view carries
both decorators. There is no admin registration anywhere. The single admin
row is made by `flask init-db`.

The business rules (valid difficulty, valid status, cannot delete a trek that
has bookings, ...) are plain `if` statements inside the views. They are not
database constraints, so the API can answer with a readable message instead of
letting SQLAlchemy raise.
"""

from datetime import date

from flask import Blueprint, jsonify, request
from flask_security import auth_required, hash_password, roles_required

from ..extensions import cache, db, security
from ..models import (
    DIFFICULTIES,
    ROLE_ADMIN,
    ROLE_STAFF,
    ROLE_USER,
    TREK_STATUSES,
    Booking,
    StaffProfile,
    Trek,
    User,
)
from . import error, require_fields
from .treks import clear_trek_cache

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

STATS_CACHE_KEY = "admin_stats"


# --------------------------------------------------------------------------
# small helpers used by the views below
# --------------------------------------------------------------------------

def clear_caches():
    """A write changes both the public trek listing and the dashboard counts."""
    clear_trek_cache()
    cache.delete(STATS_CACHE_KEY)


def parse_date(value):
    """"2026-05-01" -> date. Empty means None. Bad text raises ValueError."""
    if not value:
        return None
    return date.fromisoformat(value)


def like(text):
    return f"%{text}%"


def next_employee_code():
    """STF001, STF002, ... skipping any code that is already taken."""
    number = StaffProfile.query.count() + 1
    while StaffProfile.query.filter_by(employee_code=f"STF{number:03d}").first():
        number += 1
    return f"STF{number:03d}"


# --------------------------------------------------------------------------
# dashboard
# --------------------------------------------------------------------------

@admin_bp.get("/stats")
@auth_required("token")
@roles_required(ROLE_ADMIN)
@cache.cached(timeout=60, key_prefix=STATS_CACHE_KEY)
def stats():
    """Counts for the admin dashboard. Cached for 60s (cache expiry)."""
    return jsonify(
        {
            "total_treks": Trek.query.count(),
            "total_users": User.query.filter(User.roles.any(name=ROLE_USER)).count(),
            "total_staff": StaffProfile.query.count(),
            "total_bookings": Booking.query.count(),
            "open_treks": Trek.query.filter_by(status="Open").count(),
            "completed_treks": Trek.query.filter_by(status="Completed").count(),
        }
    )


# --------------------------------------------------------------------------
# treks: create / update / delete / list-with-search
# --------------------------------------------------------------------------

@admin_bp.get("/treks")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def list_treks():
    """Every trek in any status, newest first. `?q=` searches name/location."""
    query = Trek.query
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            db.or_(Trek.name.ilike(like(q)), Trek.location.ilike(like(q)))
        )
    treks = query.order_by(Trek.id.desc()).all()
    return jsonify([t.to_dict() for t in treks])


@admin_bp.post("/treks")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def create_trek():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, "name", "location")
    if missing:
        return error(f"{missing} is required.")

    difficulty = data.get("difficulty", "Easy")
    if difficulty not in DIFFICULTIES:
        return error(f"difficulty must be one of {', '.join(DIFFICULTIES)}.")

    status = data.get("status", "Pending")
    if status not in TREK_STATUSES:
        return error(f"status must be one of {', '.join(TREK_STATUSES)}.")

    try:
        total_slots = int(data.get("total_slots") or 0)
        duration_days = int(data.get("duration_days") or 1)
        price = float(data.get("price") or 0)
        start_date = parse_date(data.get("start_date"))
        end_date = parse_date(data.get("end_date"))
    except (TypeError, ValueError):
        return error("Numbers must be numeric and dates must be YYYY-MM-DD.")

    if total_slots < 0:
        return error("total_slots cannot be negative.")
    if duration_days < 1:
        return error("duration_days must be at least 1.")
    if start_date and end_date and end_date < start_date:
        return error("end_date cannot be before start_date.")

    trek = Trek(
        name=data["name"].strip(),
        location=data["location"].strip(),
        description=(data.get("description") or "").strip(),
        difficulty=difficulty,
        duration_days=duration_days,
        total_slots=total_slots,
        # A brand new trek has nothing booked, so every slot is free.
        available_slots=total_slots,
        status=status,
        start_date=start_date,
        end_date=end_date,
        price=price,
    )
    db.session.add(trek)
    db.session.commit()
    clear_caches()
    return jsonify(trek.to_dict()), 201


@admin_bp.put("/treks/<int:trek_id>")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def update_trek(trek_id):
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        return error("Trek not found.", 404)

    data = request.get_json(silent=True) or {}

    if "difficulty" in data and data["difficulty"] not in DIFFICULTIES:
        return error(f"difficulty must be one of {', '.join(DIFFICULTIES)}.")
    if "status" in data and data["status"] not in TREK_STATUSES:
        return error(f"status must be one of {', '.join(TREK_STATUSES)}.")

    try:
        if "duration_days" in data:
            duration_days = int(data["duration_days"])
        else:
            duration_days = trek.duration_days
        if "price" in data:
            price = float(data["price"])
        else:
            price = trek.price
        start_date = (
            parse_date(data["start_date"]) if "start_date" in data else trek.start_date
        )
        end_date = parse_date(data["end_date"]) if "end_date" in data else trek.end_date
        new_total = int(data["total_slots"]) if "total_slots" in data else trek.total_slots
    except (TypeError, ValueError):
        return error("Numbers must be numeric and dates must be YYYY-MM-DD.")

    if duration_days < 1:
        return error("duration_days must be at least 1.")
    if new_total < 0:
        return error("total_slots cannot be negative.")
    if start_date and end_date and end_date < start_date:
        return error("end_date cannot be before start_date.")

    booked = trek.total_slots - trek.available_slots
    if new_total < booked:
        return error(f"{booked} slots are already booked, total_slots cannot be lower.")

    if "name" in data:
        trek.name = (data["name"] or "").strip() or trek.name
    if "location" in data:
        trek.location = (data["location"] or "").strip() or trek.location
    if "description" in data:
        trek.description = (data["description"] or "").strip()
    if "difficulty" in data:
        trek.difficulty = data["difficulty"]
    if "status" in data:
        trek.status = data["status"]
    trek.duration_days = duration_days
    trek.price = price
    trek.start_date = start_date
    trek.end_date = end_date

    # Growing or shrinking the trek moves the free slots by the same amount;
    # the already-booked seats stay booked.
    trek.total_slots = new_total
    trek.available_slots = new_total - booked

    db.session.commit()
    clear_caches()
    return jsonify(trek.to_dict())


@admin_bp.delete("/treks/<int:trek_id>")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def delete_trek(trek_id):
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        return error("Trek not found.", 404)

    # Deleting would destroy those users' trekking history, so refuse.
    if trek.bookings:
        return error("This trek has bookings; close or complete it instead.")

    db.session.delete(trek)
    db.session.commit()
    clear_caches()
    return jsonify({"message": "Trek deleted."})


@admin_bp.put("/treks/<int:trek_id>/assign-staff")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def assign_staff(trek_id):
    """Give the trek to a staff member. staff_id null removes the assignment."""
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        return error("Trek not found.", 404)

    data = request.get_json(silent=True) or {}
    if "staff_id" not in data:
        return error("staff_id is required.")

    staff_id = data["staff_id"]
    if staff_id is None:
        trek.assigned_staff_id = None
    else:
        profile = db.session.get(StaffProfile, staff_id)
        if profile is None:
            return error("Staff member not found.", 404)
        if not profile.user.active:
            return error("That staff account is deactivated.")
        trek.assigned_staff_id = profile.id

    db.session.commit()
    clear_caches()
    return jsonify(trek.to_dict())


# --------------------------------------------------------------------------
# staff accounts
# --------------------------------------------------------------------------

@admin_bp.get("/staff")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def list_staff():
    """All staff. `?q=` searches name, email or employee code."""
    query = StaffProfile.query.join(User, StaffProfile.user_id == User.id)
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            db.or_(
                User.full_name.ilike(like(q)),
                User.email.ilike(like(q)),
                StaffProfile.employee_code.ilike(like(q)),
            )
        )
    staff = query.order_by(StaffProfile.id).all()
    return jsonify([s.to_dict() for s in staff])


@admin_bp.post("/staff")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def create_staff():
    """Staff never self-register: only the admin can make a staff account."""
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, "email", "password", "full_name")
    if missing:
        return error(f"{missing} is required.")

    email = data["email"].strip().lower()
    if security.datastore.find_user(email=email):
        return error("That email is already registered.")
    if len(data["password"]) < 6:
        return error("Password must be at least 6 characters.")

    employee_code = (data.get("employee_code") or "").strip() or next_employee_code()
    if StaffProfile.query.filter_by(employee_code=employee_code).first():
        return error("That employee code is already used.")

    user = security.datastore.create_user(
        email=email,
        password=hash_password(data["password"]),
        full_name=data["full_name"].strip(),
        phone=(data.get("phone") or "").strip(),
        roles=[ROLE_STAFF],
    )
    db.session.flush()  # gives `user` its id so the profile can point at it

    profile = StaffProfile(user_id=user.id, employee_code=employee_code)
    db.session.add(profile)
    db.session.commit()
    cache.delete(STATS_CACHE_KEY)
    return jsonify(profile.to_dict()), 201


# --------------------------------------------------------------------------
# trekker accounts
# --------------------------------------------------------------------------

@admin_bp.get("/users")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def list_users():
    """All trekkers. `?q=` searches name, email or phone."""
    query = User.query.filter(User.roles.any(name=ROLE_USER))
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            db.or_(
                User.full_name.ilike(like(q)),
                User.email.ilike(like(q)),
                User.phone.ilike(like(q)),
            )
        )
    users = query.order_by(User.id).all()
    return jsonify(
        [dict(u.to_dict(), booking_count=len(u.bookings)) for u in users]
    )


def get_manageable_user(user_id):
    """Find the target of a deactivate/blacklist call.

    Returns (user, None) when the admin may change it, or (None, response)
    with the error to send back. The admin account itself is off limits so a
    demo cannot lock itself out.
    """
    user = db.session.get(User, user_id)
    if user is None:
        return None, error("User not found.", 404)
    if ROLE_ADMIN in user.role_names:
        return None, error("The admin account cannot be changed here.", 403)
    return user, None


@admin_bp.post("/users/<int:user_id>/deactivate")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def deactivate_user(user_id):
    """Works for a trekker or a staff member: one unified user table."""
    user, denied = get_manageable_user(user_id)
    if denied:
        return denied
    user.active = False
    if user.staff_profile:
        user.staff_profile.status = "Inactive"
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/reactivate")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def reactivate_user(user_id):
    user, denied = get_manageable_user(user_id)
    if denied:
        return denied
    user.active = True
    if user.staff_profile:
        user.staff_profile.status = "Active"
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/blacklist")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def blacklist_user(user_id):
    """Blacklisted accounts can still log in but every action is refused
    (see blocked_check in app/api/__init__.py)."""
    user, denied = get_manageable_user(user_id)
    if denied:
        return denied
    user.is_blacklisted = True
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unblacklist")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def unblacklist_user(user_id):
    user, denied = get_manageable_user(user_id)
    if denied:
        return denied
    user.is_blacklisted = False
    db.session.commit()
    return jsonify(user.to_dict())


# --------------------------------------------------------------------------
# bookings across the whole system (historical trekking data)
# --------------------------------------------------------------------------

@admin_bp.get("/bookings")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def list_bookings():
    """Every booking ever made. Optional ?status= and ?trek_id= filters."""
    query = Booking.query

    status = request.args.get("status", "").strip()
    if status:
        query = query.filter(Booking.status == status)

    trek_id = request.args.get("trek_id", "").strip()
    if trek_id.isdigit():
        query = query.filter(Booking.trek_id == int(trek_id))

    bookings = query.order_by(Booking.booking_date.desc()).all()
    return jsonify([b.to_dict() for b in bookings])


@admin_bp.post("/bookings/<int:booking_id>/mark-paid")
@auth_required("token")
@roles_required(ROLE_ADMIN)
def mark_booking_paid(booking_id):
    """Record that a booking has been paid for.

    The spec lists payment as an optional extra, so this is kept deliberately
    simple: there is no real payment gateway, the admin just records that the
    money arrived.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return error("Booking not found.", 404)

    if booking.status == "Cancelled":
        return error("This booking was cancelled.")

    booking.payment_status = "Paid"
    db.session.commit()
    return jsonify(booking.to_dict())
