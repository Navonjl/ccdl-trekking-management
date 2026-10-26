"""All application configuration lives in this one class.

Anything that is a secret, or that changes between machines, is read from the
environment, which is the .env file in the project root during development
and the variables projected from Key Vault in the AKS cluster. Every one has a
default that runs the app locally with SQLite and a local Redis.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def load_env_file():
    """Copy KEY=value lines from .env into the environment.

    Written by hand rather than with python-dotenv, since eight lines do the
    job. Existing environment variables win, so `GCHAT_WEBHOOK_URL=... uv run
    python main.py` still overrides the file.
    """
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file()


def env(name, default=""):
    return os.environ.get(name, default)


# Azure Managed Redis only accepts TLS (rediss://). Celery's Redis result
# backend refuses a rediss URL unless it says how to check the certificate.
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_URL = (
    f"{REDIS_URL}?ssl_cert_reqs=required" if REDIS_URL.startswith("rediss://") else REDIS_URL
)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)


class Config:
    # --- Flask ----------------------------------------------------------
    SECRET_KEY = env("SECRET_KEY", "dev-secret-change-me")

    # DEBUG gives us the auto-reloader, which is handy while developing.
    # PROPAGATE_EXCEPTIONS turns off the interactive Werkzeug debugger page,
    # so an unexpected error returns the JSON error below instead of an HTML
    # page containing our source code.
    DEBUG = env("FLASK_DEBUG", "1") == "1"
    PROPAGATE_EXCEPTIONS = False

    # Paths, exposed on the class so create_app() can make the folders.
    INSTANCE_DIR = INSTANCE_DIR

    # --- Database: SQLite locally, Azure PostgreSQL in the cluster ---------
    # In the cluster DATABASE_URL is postgresql+psycopg://...?sslmode=require.
    SQLALCHEMY_DATABASE_URI = env(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'trekking.sqlite3'}"
    )
    # Drop pooled connections the server has closed, instead of failing the
    # next request on them. Matters after a database failover.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Flask-Security-Too --------------------------------------------
    SECURITY_PASSWORD_SALT = env("SECURITY_PASSWORD_SALT", "146585145368132386173505678016728509634")
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
    # would fail on a machine with no network, so it is turned off.
    # (Note: reserved domains like ".local" are rejected whatever this is set
    # to, which is why the demo accounts use example.com.)
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}

    # The SPA authenticates with a token in a header, not a cookie, so there
    # is no CSRF risk to protect against and we never set up Flask-WTF's
    # CSRFProtect. (Setting SECURITY_CSRF_PROTECT_MECHANISMS here without
    # initialising CSRFProtect makes Flask-Security refuse to start.)
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False

    # --- Redis: response cache and Celery results -------------------------
    # Azure Managed Redis has a single database, so the cache and Celery's
    # results share it and the cache keys carry a prefix. The prefix also
    # makes cache.clear() delete only cache keys instead of the database.
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_KEY_PREFIX = "cache:"
    CACHE_DEFAULT_TIMEOUT = 60      # seconds before a cached value expires

    # The broker is Redis locally and Azure Service Bus in the cluster.
    CELERY = {
        "broker_url": CELERY_BROKER_URL,
        "result_backend": CELERY_RESULT_URL,
        # Load the task module explicitly, so the worker registers the three
        # jobs regardless of which parts of the app get imported.
        "include": ["app.tasks"],
        "timezone": "Asia/Kolkata",
        "enable_utc": False,
        "broker_connection_retry_on_startup": True,
        # Service Bus has no fanout exchange, which Celery's remote control
        # and event broadcasts need. Nothing here uses either.
        "worker_enable_remote_control": not CELERY_BROKER_URL.startswith("azureservicebus://"),
        "worker_send_task_events": False,
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

    # Paste a Google Chat "incoming webhook" URL here and the daily reminder
    # job posts to that space instead of writing an e-mail. Easier to show
    # working than e-mail: the message just appears in the chat.
    # "off" exists because Key Vault cannot store an empty secret.
    GCHAT_WEBHOOK_URL = "" if env("GCHAT_WEBHOOK_URL") == "off" else env("GCHAT_WEBHOOK_URL")

    OUTBOX_DIR = INSTANCE_DIR / "outbox"
    EXPORT_DIR = INSTANCE_DIR / "exports"

    # When set, CSV exports go to this Blob Storage account instead of
    # EXPORT_DIR, because a worker pod's disk is not visible to the API pods.
    # Access is through the pod's workload identity; there is no account key.
    EXPORT_BLOB_ACCOUNT_URL = env("EXPORT_BLOB_ACCOUNT_URL")
    EXPORT_BLOB_CONTAINER = env("EXPORT_BLOB_CONTAINER", "exports")

    # --- The one admin account, created by init-db ----------------------
    ADMIN_EMAIL = env("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = env("ADMIN_PASSWORD", "admin123")
