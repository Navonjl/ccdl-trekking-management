"""Reading treks: the list (with search + filters) and one trek's detail.

Creating and editing treks is not here -- admin does that in api/admin.py and
staff in api/staff.py. This module is the read side, and the read side is the
part that gets hit on every page load, so it is the part we cache in Redis.
"""

from flask import Blueprint, jsonify, request
from flask_security import auth_required, current_user

from ..config import Config
from ..extensions import cache
from ..models import ROLE_ADMIN, ROLE_STAFF, Trek

treks_bp = Blueprint("treks", __name__, url_prefix="/api")

# What a trekker is allowed to see in the listing. "Pending" treks are waiting
# for approval, "Closed"/"Completed" ones cannot be booked any more.
TREKKER_VISIBLE_STATUSES = ("Approved", "Open")


def is_privileged():
    """True for admin and staff, who see every trek in every status."""
    return current_user.has_role(ROLE_ADMIN) or current_user.has_role(ROLE_STAFF)


def clear_trek_cache():
    """Throw away the cached trek listings.

    Every place that CHANGES a trek calls this: admin create/update/delete,
    staff slot and status edits, and booking/cancelling (which moves
    available_slots). Without it a trekker could be shown a sold-out trek for
    up to CACHE_DEFAULT_TIMEOUT seconds.

    cache.clear() drops the whole cache rather than one key. That is on
    purpose: the listing is cached under one key per query-string combination,
    and we have no list of which combinations exist.
    """
    cache.clear()


def _int_arg(name):
    """Read a query parameter as an int, or None if absent/not a number."""
    value = request.args.get(name, "").strip()
    return int(value) if value.isdigit() else None


@treks_bp.get("/treks")
@auth_required("token")
@cache.cached(
    # Timeout is read from config so there is one place to change it. It is
    # Config.CACHE_DEFAULT_TIMEOUT and not current_app.config[...] only
    # because decorators run at import time, when there is no app context.
    timeout=Config.CACHE_DEFAULT_TIMEOUT,
    query_string=True,          # ?difficulty=Hard is a different cache entry
    unless=is_privileged,       # see the comment below
)
def list_treks():
    """List treks, filtered by the query string.

    Caching note: `unless=is_privileged` means only the trekker view is
    cached. The cache key is the path plus the query string, so it does not
    include the role -- if admins shared it, one admin request would poison
    the trekker listing with Pending treks. Admin and staff are also the
    people editing treks, so they want live numbers anyway.

    Query params: q, difficulty, location, min_days, max_days.
    """
    query = Trek.query

    # Role filter first: a trekker only ever sees treks that are on offer.
    if not is_privileged():
        query = query.filter(Trek.status.in_(TREKKER_VISIBLE_STATUSES))

    # Search box: matches either the trek name or its location.
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(Trek.name.ilike(like) | Trek.location.ilike(like))

    difficulty = request.args.get("difficulty", "").strip()
    if difficulty:
        query = query.filter(Trek.difficulty == difficulty)

    location = request.args.get("location", "").strip()
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))

    # Duration filter, in days.
    min_days = _int_arg("min_days")
    if min_days is not None:
        query = query.filter(Trek.duration_days >= min_days)

    max_days = _int_arg("max_days")
    if max_days is not None:
        query = query.filter(Trek.duration_days <= max_days)

    treks = query.order_by(Trek.start_date, Trek.name).all()
    return jsonify([trek.to_dict() for trek in treks])
