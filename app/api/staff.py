"""Trek staff endpoints: /api/staff/...

Staff accounts are made by the admin (see app/api/admin.py), so there is no
staff registration route.

The rule that matters here is "only assigned staff can manage a trek". Every
view that touches a trek calls `check_assigned(trek)` first, which compares
trek.assigned_staff_id with this staff member's own profile id and returns 403
when they differ. Knowing the trek id is not enough to manage it.
"""

from flask import Blueprint, jsonify, request
from flask_security import auth_required, current_user, roles_required

from ..extensions import db
from ..models import ROLE_STAFF, Booking, Trek
from . import error
from .treks import clear_trek_cache

staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")

# The admin owns Pending/Approved; staff only run the trek day to day.
STAFF_STATUSES = ("Open", "Closed", "Completed")


def check_assigned(trek):
    """Return None if the logged-in staff member owns this trek, else a 403.

    Called at the top of every route below, right after the trek is loaded.
    """
    profile = current_user.staff_profile
    if profile is None:
        return error("This account has no staff profile.", 403)
    if trek.assigned_staff_id != profile.id:
        return error("This trek is not assigned to you.", 403)
    return None


def registered_bookings(trek_id):
    """Bookings that still count as a registration (cancelled ones do not)."""
    return (
        Booking.query.filter(Booking.trek_id == trek_id, Booking.status != "Cancelled")
        .order_by(Booking.booking_date)
        .all()
    )


@staff_bp.get("/dashboard")
@auth_required("token")
@roles_required(ROLE_STAFF)
def dashboard():
    """The treks the admin assigned to me, each with its registration count."""
    profile = current_user.staff_profile
    if profile is None:
        return error("This account has no staff profile.", 403)

    treks = (
        Trek.query.filter_by(assigned_staff_id=profile.id).order_by(Trek.start_date).all()
    )

    rows = []
    for trek in treks:
        row = trek.to_dict()
        row["registered_count"] = len(registered_bookings(trek.id))
        rows.append(row)

    return jsonify(
        {
            "staff": profile.to_dict(),
            "assigned_treks": rows,
            "total_assigned": len(rows),
        }
    )


@staff_bp.put("/treks/<int:trek_id>")
@auth_required("token")
@roles_required(ROLE_STAFF)
def update_trek(trek_id):
    """Staff may change only the available slots and the trek status."""
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        return error("Trek not found.", 404)

    denied = check_assigned(trek)
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    if "available_slots" not in data and "status" not in data:
        return error("Send available_slots and/or status.")

    if "available_slots" in data:
        try:
            available = int(data["available_slots"])
        except (TypeError, ValueError):
            return error("available_slots must be a number.")
        if available < 0:
            return error("available_slots cannot be negative.")
        if available > trek.total_slots:
            return error(f"This trek has only {trek.total_slots} slots in total.")
        trek.available_slots = available

    if "status" in data:
        if data["status"] not in STAFF_STATUSES:
            return error(f"status must be one of {', '.join(STAFF_STATUSES)}.")
        trek.status = data["status"]

        # Finishing the trek finishes its bookings too, so each trekker's
        # history shows "Completed" rather than a permanent "Booked".
        if trek.status == "Completed":
            for booking in trek.bookings:
                if booking.status == "Booked":
                    booking.status = "Completed"

    db.session.commit()
    clear_trek_cache()
    return jsonify(trek.to_dict())


@staff_bp.get("/treks/<int:trek_id>/participants")
@auth_required("token")
@roles_required(ROLE_STAFF)
def participants(trek_id):
    """The users registered for one of my treks."""
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        return error("Trek not found.", 404)

    denied = check_assigned(trek)
    if denied:
        return denied

    rows = []
    for booking in registered_bookings(trek.id):
        rows.append(
            {
                "booking_id": booking.id,
                "booking_status": booking.status,
                "payment_status": booking.payment_status,
                "booking_date": booking.booking_date.isoformat(),
                "user_id": booking.user_id,
                "name": booking.user.full_name,
                "email": booking.user.email,
                "phone": booking.user.phone,
            }
        )

    return jsonify(
        {
            "trek": trek.to_dict(),
            "participants": rows,
            "total": len(rows),
        }
    )
