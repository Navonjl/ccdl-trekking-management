"""Bookings: a trekker reserves a slot, sees their history, or cancels.

All the "other core functionality" rules from the spec live in book_trek()
below as plain if-statements, so they are easy to read out and easy to change.

Two of them are backed up in the database as well, because an `if` on its own
only works when requests arrive one at a time: the slot count is decremented
by a conditional UPDATE, and a unique index stops a second active booking for
the same user and trek. The if-statements still come first, so the normal case
returns a helpful message rather than a database error.
"""

from flask import Blueprint, jsonify, request
from flask_security import auth_required, current_user
from sqlalchemy.exc import IntegrityError

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
    # `isinstance(True, int)` is True in Python, so booleans have to be
    # excluded by hand or {"trek_id": true} would book trek 1.
    if not isinstance(trek_id, int) or isinstance(trek_id, bool):
        return error("trek_id is required.")

    trek = Trek.query.get(trek_id)

    # Rule 1: the trek has to exist.
    if not trek:
        return error("Trek not found.", 404)

    # Rule 2: "Allow booking only when trek status is Open". Approved treks
    # are visible in the listing but not yet taking bookings.
    if trek.status != "Open":
        return error(f"This trek is not open for booking (status: {trek.status}).")

    # Rule 4: "Prevent duplicate bookings for same trek". A Cancelled booking
    # does not count, so a user who changed their mind can book again.
    existing = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.trek_id == trek.id,
        Booking.status != "Cancelled",
    ).first()
    if existing:
        return error("You have already booked this trek.")

    # Rule 3: "Prevent overbooking beyond available slots".
    #
    # Written as one UPDATE with a WHERE clause rather than "read the count,
    # check it, then subtract one". If two people press Book on the last slot
    # at the same moment, both of their reads would see 1 free slot and both
    # would book it. Here the database itself only decrements while a slot is
    # still free, and tells us how many rows it changed: 0 means we lost the
    # race and the trek is now full.
    rows_changed = Trek.query.filter(
        Trek.id == trek.id, Trek.available_slots > 0
    ).update({"available_slots": Trek.available_slots - 1})
    if rows_changed == 0:
        db.session.rollback()
        return error("This trek is full.")

    booking = Booking(user_id=current_user.id, trek_id=trek.id, status="Booked")
    db.session.add(booking)

    # The seat count and the booking row are saved in ONE commit, so the two
    # can never disagree: if the insert fails, the decrement rolls back too.
    try:
        db.session.commit()
    except IntegrityError:
        # The unique index in models.py refused a second active booking for
        # this user and trek -- two requests raced past the check above.
        db.session.rollback()
        return error("You have already booked this trek.")

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
