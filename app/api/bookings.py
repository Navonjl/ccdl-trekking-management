"""Bookings: a trekker reserves a slot, sees their history, or cancels.

All the "other core functionality" rules from the spec live in book_trek()
below as plain if-statements. They are deliberately NOT database constraints:
the viva asks us to explain and change them, and an `if` is something we can
point at and read out loud. It also lets us return a useful message instead of
an IntegrityError.
"""

from flask import Blueprint, jsonify, request
from flask_security import auth_required, current_user

from ..extensions import db
from ..models import Booking, Trek
from . import blocked_check, error
from .treks import clear_trek_cache

bookings_bp = Blueprint("bookings", __name__, url_prefix="/api")


@bookings_bp.post("/bookings")
@auth_required("token")
@blocked_check
def book_trek():
    """Book the current user onto a trek. Body: {"trek_id": 1}."""
    data = request.get_json(silent=True) or {}
    trek_id = data.get("trek_id")
    if not isinstance(trek_id, int):
        return error("trek_id is required.")

    trek = Trek.query.get(trek_id)

    # Rule 1: the trek has to exist.
    if not trek:
        return error("Trek not found.", 404)

    # Rule 2: "Allow booking only when trek status is Open". Approved treks
    # are visible in the listing but not yet taking bookings.
    if trek.status != "Open":
        return error(f"This trek is not open for booking (status: {trek.status}).")

    # Rule 3: "Prevent overbooking beyond available slots".
    if trek.available_slots <= 0:
        return error("This trek is full.")

    # Rule 4: "Prevent duplicate bookings for same trek". A Cancelled booking
    # does not count, so a user who changed their mind can book again.
    existing = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.trek_id == trek.id,
        Booking.status != "Cancelled",
    ).first()
    if existing:
        return error("You have already booked this trek.")

    booking = Booking(user_id=current_user.id, trek_id=trek.id, status="Booked")
    db.session.add(booking)

    # The seat count and the booking row change in ONE commit, so the two can
    # never disagree: if the insert fails, the decrement is rolled back too.
    trek.available_slots = trek.available_slots - 1
    db.session.commit()

    # available_slots just changed, so the cached trek listing is now stale.
    clear_trek_cache()

    return jsonify(booking.to_dict()), 201


@bookings_bp.get("/bookings")
@auth_required("token")
def my_bookings():
    """The current user's own bookings -- their complete trekking history.

    Filtered by current_user.id, so a user cannot read anyone else's history.
    The admin's "all bookings" view is a separate route in api/admin.py.
    """
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return jsonify([booking.to_dict() for booking in bookings])


@bookings_bp.post("/bookings/<int:booking_id>/cancel")
@auth_required("token")
@blocked_check
def cancel_booking(booking_id):
    """Cancel one of the current user's own bookings and free the slot."""
    booking = Booking.query.get(booking_id)
    if not booking:
        return error("Booking not found.", 404)

    # Ownership check: the id is in the URL, so without this anyone could
    # cancel anyone else's booking by guessing a number.
    if booking.user_id != current_user.id:
        return error("You can only cancel your own bookings.", 403)

    if booking.status == "Cancelled":
        return error("This booking is already cancelled.")

    # A finished trek stays in the history as a record of what happened.
    if booking.status == "Completed":
        return error("A completed trek cannot be cancelled.")

    booking.status = "Cancelled"

    # Give the seat back, in the same commit as the status change.
    if booking.trek:
        booking.trek.available_slots = booking.trek.available_slots + 1
    db.session.commit()

    clear_trek_cache()

    return jsonify(booking.to_dict())
