"""The three Celery jobs asked for in the project statement.

  a. send_daily_reminders          -- scheduled, runs every evening
  b. send_monthly_activity_report  -- scheduled, runs on the 1st of the month
  c. export_bookings_csv           -- triggered by a user from their dashboard

The schedules for (a) and (b) are in the beat_schedule in app/celery_utils.py;
the task names below are what that schedule refers to.

FlaskTask in app/celery_utils.py runs every task inside a Flask application
context, so `db.session` here needs no setup of its own.
"""

import csv
from datetime import date, datetime, timedelta

from celery import shared_task

from .config import Config
from .extensions import db
from .mailer import send_email, send_gchat
from .models import Booking, Trek, User

# Remind people about treks starting within this many days.
REMINDER_WINDOW_DAYS = 3

# What a trekker should bring. Kept in one place so both the chat message and
# the e-mail say the same thing.
INSTRUCTIONS = (
    "Please carry a photo ID, at least 2 litres of water, a warm layer and "
    "sturdy shoes, and reach the base camp one hour before the start time."
)


@shared_task(name="app.tasks.send_daily_reminders")
def send_daily_reminders():
    """Job (a): remind trekkers about the treks they have booked."""
    today = date.today()
    window_end = today + timedelta(days=REMINDER_WINDOW_DAYS)

    treks = (
        db.session.query(Trek)
        .filter(Trek.status == "Open")
        .filter(Trek.start_date.isnot(None))
        .filter(Trek.start_date >= today)
        .filter(Trek.start_date <= window_end)
        .order_by(Trek.start_date)
        .all()
    )

    sent = 0
    for trek in treks:
        details = (
            f"{trek.name} at {trek.location} starts on {trek.start_date} "
            f"({trek.difficulty}, {trek.duration_days} day(s)). {INSTRUCTIONS}"
        )
        for booking in trek.bookings:
            if booking.status != "Booked":
                continue

            user = booking.user
            name = user.full_name or user.email

            # Google Chat when a webhook is configured, e-mail otherwise.
            if send_gchat(f"Hi {name}, reminder: {details}"):
                sent += 1
            elif send_email(
                user.email,
                f"Reminder: {trek.name} starts on {trek.start_date}",
                f"<p>Hi {name},</p><p>{details}</p><p>Happy trekking!</p>",
            ):
                sent += 1

    print(f"[reminders] {len(treks)} upcoming trek(s), {sent} reminder(s) sent")
    return {"upcoming_treks": len(treks), "reminders_sent": sent}


@shared_task(name="app.tasks.send_monthly_activity_report")
def send_monthly_activity_report():
    """Job (b): e-mail the admin an HTML report for the previous month."""
    # Day 1 of this month minus one day is the last day of the previous month.
    last_day = date.today().replace(day=1) - timedelta(days=1)
    first_day = last_day.replace(day=1)

    treks = (
        db.session.query(Trek)
        .filter(Trek.start_date.isnot(None))
        .filter(Trek.start_date >= first_day)
        .filter(Trek.start_date <= last_day)
        .all()
    )

    participant_ids = set()
    # One (headcount, trek) pair per trek, so we can sort by headcount below.
    headcounts = []
    for trek in treks:
        joined = [b for b in trek.bookings if b.status in ("Booked", "Completed")]
        for booking in joined:
            participant_ids.add(booking.user_id)
        headcounts.append((len(joined), trek))

    headcounts.sort(key=lambda pair: pair[0], reverse=True)
    popular = headcounts[:5]

    rows = "".join(
        f"<tr><td>{trek.name}</td><td>{trek.location}</td>"
        f"<td>{trek.difficulty}</td><td>{count}</td></tr>"
        for count, trek in popular
    )
    if not rows:
        rows = "<tr><td colspan='4'>No treks in this period.</td></tr>"

    month_label = last_day.strftime("%B %Y")
    html = f"""\
<html><body style="font-family: Arial, sans-serif;">
  <h2>Trekking Activity Report - {month_label}</h2>
  <p>Period: {first_day} to {last_day}</p>
  <ul>
    <li>Treks conducted: <b>{len(treks)}</b></li>
    <li>Users who participated: <b>{len(participant_ids)}</b></li>
  </ul>
  <h3>Most popular treks</h3>
  <table border="1" cellpadding="6" cellspacing="0">
    <tr><th>Trek</th><th>Location</th><th>Difficulty</th><th>Trekkers</th></tr>
    {rows}
  </table>
  <p style="color: #666;">Generated automatically by the Trekking Management Application.</p>
</body></html>"""

    sent = send_email(
        Config.ADMIN_EMAIL, f"Monthly Activity Report - {month_label}", html
    )
    return {
        "month": month_label,
        "treks_conducted": len(treks),
        "participants": len(participant_ids),
        "emailed_to": Config.ADMIN_EMAIL,
        "sent": sent,
    }


# Exactly the columns the project statement asks for.
CSV_COLUMNS = [
    "User ID",
    "Trek Name",
    "Location",
    "Booking Status",
    "Booking Date",
    "Start Date",
    "End Date",
]


@shared_task(name="app.tasks.export_bookings_csv")
def export_bookings_csv(user_id):
    """Job (c): write one user's trekking history to a CSV, then alert them."""
    user = db.session.get(User, user_id)
    if user is None:
        return {"filename": None, "error": f"no user with id {user_id}"}

    bookings = (
        db.session.query(Booking)
        .filter(Booking.user_id == user_id)
        .order_by(Booking.booking_date)
        .all()
    )

    # Timestamp keeps every export a separate file, so two clicks never clash.
    filename = f"bookings-user{user_id}-{datetime.now():%Y%m%d-%H%M%S}.csv"
    Config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = Config.EXPORT_DIR / filename

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for booking in bookings:
            trek = booking.trek
            writer.writerow([
                booking.user_id,
                trek.name,
                trek.location,
                booking.status,
                booking.booking_date.strftime("%Y-%m-%d %H:%M"),
                trek.start_date or "",
                trek.end_date or "",
            ])

    send_email(
        user.email,
        "Your trekking history export is ready",
        f"<p>Hi {user.full_name or user.email},</p>"
        f"<p>Your export of {len(bookings)} booking(s) is ready: "
        f"<b>{filename}</b>. Download it from your dashboard.</p>",
    )

    print(f"[export] wrote {path} ({len(bookings)} rows)")
    return {"filename": filename, "rows": len(bookings)}
