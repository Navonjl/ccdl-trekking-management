"""All application configuration lives in this one class."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    # --- Flask ----------------------------------------------------------
    SECRET_KEY = "dev-secret-change-me"

    # DEBUG gives us the auto-reloader, which is handy while developing.
    # PROPAGATE_EXCEPTIONS turns off the interactive Werkzeug debugger page,
    # so an unexpected error returns the JSON error below instead of an HTML
    # page containing our source code.
    DEBUG = True
    PROPAGATE_EXCEPTIONS = False

    # Paths, exposed on the class so create_app() can make the folders.
    INSTANCE_DIR = INSTANCE_DIR

    # --- Database: SQLite, created by the init-db command ---------------
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_DIR / 'trekking.sqlite3'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Flask-Security-Too --------------------------------------------
    SECURITY_PASSWORD_SALT = "146585145368132386173505678016728509634"
    SECURITY_URL_PREFIX = "/api/accounts"   # so /api/accounts/login works
    SECURITY_FLASH_MESSAGES = False         # JSON API, nothing to flash
    SECURITY_REGISTERABLE = False           # we use our own /api/register
    SECURITY_CONFIRMABLE = False
    SECURITY_RECOVERABLE = False

    # Log in with email + password, get back a token the SPA sends on
    # every later request as the Authentication-Token header.
    SECURITY_API_ENABLED_METHODS = ["session", "token"]

    # By default Flask-Security checks an e-mail domain really exists by doing
    # a DNS lookup. We only need addresses to be well-formed, and the lookup
    # would fail on a machine with no network -- so it is turned off.
    # (Note: reserved domains like ".local" are rejected whatever this is set
    # to, which is why the demo accounts use example.com.)
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}

    # The SPA authenticates with a token in a header, not a cookie, so there
    # is no CSRF risk to protect against and we never set up Flask-WTF's
    # CSRFProtect. (Setting SECURITY_CSRF_PROTECT_MECHANISMS here without
    # initialising CSRFProtect makes Flask-Security refuse to start.)
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False

    # --- Redis: used for caching AND as the Celery broker ---------------
    REDIS_URL = "redis://localhost:6379"

    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = f"{REDIS_URL}/1"
    CACHE_DEFAULT_TIMEOUT = 60      # seconds before a cached value expires

    CELERY = {
        "broker_url": f"{REDIS_URL}/0",
        "result_backend": f"{REDIS_URL}/2",
        # Load the task module explicitly, so the worker registers the three
        # jobs regardless of which parts of the app get imported.
        "include": ["app.tasks"],
        "timezone": "Asia/Kolkata",
        "enable_utc": False,
        "broker_connection_retry_on_startup": True,
    }

    # --- Mail ------------------------------------------------------------
    # If MAIL_SERVER is empty, send_email() writes the message to
    # instance/outbox/ instead of sending it. That way the Celery jobs can
    # be demonstrated without a real SMTP server.
    MAIL_SERVER = ""
    MAIL_PORT = 587
    MAIL_USERNAME = ""
    MAIL_PASSWORD = ""
    MAIL_SENDER = "no-reply@example.com"

    # Optional: Google Chat webhook for the daily reminder job.
    GCHAT_WEBHOOK_URL = ""

    OUTBOX_DIR = INSTANCE_DIR / "outbox"
    EXPORT_DIR = INSTANCE_DIR / "exports"

    # --- The one admin account, created by init-db ----------------------
    ADMIN_EMAIL = "admin@example.com"
    ADMIN_PASSWORD = "admin123"
