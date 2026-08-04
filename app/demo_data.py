"""Sample data for `flask seed-demo`, so there is something to show in a demo.

Run `flask init-db` first: that makes the tables, the three roles and the one
admin account. This module only adds staff, treks, trekkers and bookings.

Every password goes through hash_password, exactly as the real registration
route does, so all of these accounts can actually log in.
"""

from datetime import date, datetime, timedelta

from flask_security import hash_password

from .extensions import db, security
from .models import ROLE_STAFF, ROLE_USER, Booking, StaffProfile, Trek

STAFF_PASSWORD = "staff123"
TREKKER_PASSWORD = "trekker123"

# full name, e-mail, phone, employee code
STAFF = [
    ("Ramesh Iyer", "ramesh.staff@example.com", "9800000011", "STF001"),
    ("Fatima Sheikh", "fatima.staff@example.com", "9800000012", "STF002"),
    ("Joseph Mathew", "joseph.staff@example.com", "9800000013", "STF003"),
]

# full name, e-mail, phone
TREKKERS = [
    ("Asha Nair", "asha@example.com", "9900000021"),
    ("Bhavesh Patel", "bhavesh@example.com", "9900000022"),
    ("Chitra Rao", "chitra@example.com", "9900000023"),
    ("Dev Menon", "dev@example.com", "9900000024"),
]


def load_demo_data():
    if not security.datastore.find_role(ROLE_USER):
        print("roles are missing -- run `flask init-db` first")
        return

    # Idempotent: one trek in the table means the demo data is already there.
    if db.session.query(Trek).first():
        print("demo data already present, nothing to do")
        return

    staff_profiles = _create_staff()
    treks = _create_treks(staff_profiles)
    trekkers = _create_trekkers()
    bookings = _create_bookings(trekkers, treks)

    _print_summary(staff_profiles, treks, trekkers, bookings)


def _create_account(email, password, full_name, phone, role):
    return security.datastore.create_user(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        phone=phone,
        roles=[role],
    )


def _create_staff():
    profiles = []
    for full_name, email, phone, employee_code in STAFF:
        user = _create_account(email, STAFF_PASSWORD, full_name, phone, ROLE_STAFF)
        # flush so the new user gets its id, which StaffProfile needs.
        db.session.flush()
        profile = StaffProfile(
            user_id=user.id, employee_code=employee_code, status="Active"
        )
        db.session.add(profile)
        profiles.append(profile)
    db.session.commit()
    return profiles


def _create_treks(staff_profiles):
    today = date.today()
    # Last day of the previous month, so the two finished treks always land in
    # the period the monthly report job looks at, whenever the demo is run.
    last_month_end = today.replace(day=1) - timedelta(days=1)

    # name, location, difficulty, days, slots, status, start date, price, staff
    rows = [
        ("Nandi Hills Sunrise", "Chikkaballapur, Karnataka", "Easy", 1, 30,
         "Open", today + timedelta(days=1), 800, 0),
        ("Kumara Parvatha Climb", "Kukke Subramanya, Karnataka", "Hard", 2, 20,
         "Open", today + timedelta(days=2), 3500, 1),
        ("Kudremukh Peak", "Chikkamagaluru, Karnataka", "Moderate", 2, 25,
         "Open", today + timedelta(days=3), 2800, 2),
        ("Chembra Peak Heart Lake", "Wayanad, Kerala", "Easy", 1, 20,
         "Open", today + timedelta(days=12), 1200, 0),
        ("Hampta Pass Crossing", "Manali, Himachal Pradesh", "Hard", 5, 15,
         "Approved", today + timedelta(days=25), 12000, 1),
        ("Tadiandamol Ridge", "Coorg, Karnataka", "Moderate", 2, 18,
         "Pending", today + timedelta(days=40), 2400, None),
        ("Kodachadri Trail", "Shivamogga, Karnataka", "Moderate", 2, 16,
         "Closed", today + timedelta(days=6), 2200, 2),
        ("Agasthyakoodam Summit", "Thiruvananthapuram, Kerala", "Hard", 3, 12,
         "Completed", last_month_end.replace(day=10), 4500, 1),
        ("Skandagiri Night Trek", "Chikkaballapur, Karnataka", "Easy", 1, 25,
         "Completed", last_month_end.replace(day=20), 1000, 0),
    ]

    treks = []
    for (name, location, difficulty, days, slots, status, start, price,
         staff_index) in rows:
        trek = Trek(
            name=name,
            location=location,
            description=f"A {difficulty.lower()} {days}-day trek near {location}.",
            difficulty=difficulty,
            duration_days=days,
            total_slots=slots,
            available_slots=slots,   # bookings below take slots off this
            status=status,
            start_date=start,
            end_date=start + timedelta(days=days - 1),
            price=price,
            assigned_staff_id=(
                None if staff_index is None else staff_profiles[staff_index].id
            ),
        )
        db.session.add(trek)
        treks.append(trek)
    db.session.commit()
    return treks


def _create_trekkers():
    users = []
    for full_name, email, phone in TREKKERS:
        users.append(
            _create_account(email, TREKKER_PASSWORD, full_name, phone, ROLE_USER)
        )
    db.session.commit()
    return users


def _create_bookings(trekkers, treks):
    # trekker index, trek index, status, how many days ago it was booked
    rows = [
        (0, 0, "Booked", 4),
        (0, 1, "Booked", 3),
        (0, 8, "Completed", 40),
        (1, 1, "Booked", 5),
        (1, 2, "Booked", 2),
        (1, 7, "Completed", 45),
        (2, 0, "Booked", 6),
        (2, 7, "Completed", 45),
        (3, 2, "Booked", 1),
        (3, 3, "Cancelled", 8),
    ]

    bookings = []
    for trekker_index, trek_index, status, days_ago in rows:
        trek = treks[trek_index]
        booking = Booking(
            user_id=trekkers[trekker_index].id,
            trek_id=trek.id,
            booking_date=datetime.now() - timedelta(days=days_ago),
            status=status,
            payment_status="Paid" if status != "Cancelled" else "Refunded",
        )
        db.session.add(booking)
        bookings.append(booking)

        # A cancelled booking holds no slot, so only the others use one up.
        if status != "Cancelled":
            trek.available_slots -= 1

    db.session.commit()
    return bookings


def _print_summary(staff_profiles, treks, trekkers, bookings):
    print(
        f"created {len(staff_profiles)} staff, {len(treks)} treks, "
        f"{len(trekkers)} trekkers, {len(bookings)} bookings"
    )
    print("\nlogin credentials")
    for profile in staff_profiles:
        print(f"  staff   {profile.user.email:32} {STAFF_PASSWORD}")
    for user in trekkers:
        print(f"  trekker {user.email:32} {TREKKER_PASSWORD}")
    print("  (admin credentials are the ones in config.py)")
