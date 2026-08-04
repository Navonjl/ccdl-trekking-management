"""Database models.

Why the schema looks like this (the "idea behind the design"):

* ONE user table for all three roles, not three tables. Admin, staff and
  trekker store the same things (email, password, name, phone) and differ only
  in what they may do. Roles are a separate table joined many-to-many, so
  "log in" is one code path instead of three.

* StaffProfile is separate because it holds fields only staff have (employee
  code, duty status). On the User table those columns would be NULL for every
  trekker.

* Trek.available_slots is a stored column, not a count of bookings. Storing it
  keeps the trek listing a plain SELECT instead of a COUNT per row; we change
  it in the same request that creates the booking so the two stay in step.
"""

from datetime import datetime

from flask_security.models import fsqla_v3 as fsqla

from .extensions import db

# Allowed values, listed once so the API and the UI agree.
DIFFICULTIES = ("Easy", "Moderate", "Hard")
TREK_STATUSES = ("Pending", "Approved", "Open", "Closed", "Completed")
BOOKING_STATUSES = ("Booked", "Cancelled", "Completed")

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_USER = "user"

# Connect the Flask-Security mixins to our db. Must run before the models.
fsqla.FsModels.set_db_info(db)


class Role(db.Model, fsqla.FsRoleMixin):
    """admin, staff or user. Created by the init-db command."""


class User(db.Model, fsqla.FsUserMixin):
    """Every account, whatever its role.

    The mixin gives us id, email, password, active, fs_uniquifier and the
    roles relationship. The columns below are ours.
    """

    full_name = db.Column(db.String(120), nullable=False, default="")
    phone = db.Column(db.String(20), nullable=False, default="")
    is_blacklisted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    bookings = db.relationship("Booking", back_populates="user")
    staff_profile = db.relationship("StaffProfile", back_populates="user", uselist=False)

    @property
    def role_names(self):
        return [r.name for r in self.roles]

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "phone": self.phone,
            "active": self.active,
            "is_blacklisted": self.is_blacklisted,
            "roles": self.role_names,
        }


class StaffProfile(db.Model):
    """Extra fields that only a staff member has."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    employee_code = db.Column(db.String(32), nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default="Active")

    user = db.relationship("User", back_populates="staff_profile")
    treks = db.relationship("Trek", back_populates="assigned_staff")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee_code": self.employee_code,
            "status": self.status,
            "name": self.user.full_name,
            "email": self.user.email,
            "phone": self.user.phone,
            "active": self.user.active,
            "assigned_trek_count": len(self.treks),
        }


class Trek(db.Model):
    """A trekking event: created by admin, run by the assigned staff member."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    difficulty = db.Column(db.String(16), nullable=False, default="Easy")
    duration_days = db.Column(db.Integer, nullable=False, default=1)
    total_slots = db.Column(db.Integer, nullable=False, default=0)
    available_slots = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="Pending")
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    price = db.Column(db.Float, nullable=False, default=0.0)

    assigned_staff_id = db.Column(
        db.Integer, db.ForeignKey("staff_profile.id"), nullable=True
    )

    assigned_staff = db.relationship("StaffProfile", back_populates="treks")
    bookings = db.relationship("Booking", back_populates="trek")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "description": self.description,
            "difficulty": self.difficulty,
            "duration_days": self.duration_days,
            "total_slots": self.total_slots,
            "available_slots": self.available_slots,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "price": self.price,
            "assigned_staff_id": self.assigned_staff_id,
            "assigned_staff_name": (
                self.assigned_staff.user.full_name if self.assigned_staff else None
            ),
        }


class Booking(db.Model):
    """A trekker's reservation on a trek."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("trek.id"), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="Booked")
    payment_status = db.Column(db.String(16), nullable=False, default="Pending")

    user = db.relationship("User", back_populates="bookings")
    trek = db.relationship("Trek", back_populates="bookings")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "trek_id": self.trek_id,
            "booking_date": self.booking_date.isoformat(),
            "status": self.status,
            "payment_status": self.payment_status,
            "trek_name": self.trek.name if self.trek else None,
            "location": self.trek.location if self.trek else None,
            "user_name": self.user.full_name if self.user else None,
            "user_email": self.user.email if self.user else None,
        }
