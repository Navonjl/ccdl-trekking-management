"""Application factory.

Read this file first: it shows how every other piece is attached.
"""

from flask import Flask
from flask_security import SQLAlchemyUserDatastore

from .celery_utils import celery_init_app
from .config import Config
from .extensions import cache, db, security
from .models import Role, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Folders the app writes into (SQLite file, e-mail outbox, CSV exports).
    Config.INSTANCE_DIR.mkdir(exist_ok=True)
    Config.OUTBOX_DIR.mkdir(exist_ok=True)
    Config.EXPORT_DIR.mkdir(exist_ok=True)

    # Extensions
    db.init_app(app)
    cache.init_app(app)
    security.init_app(app, SQLAlchemyUserDatastore(db, User, Role))
    celery_init_app(app)

    # API blueprints, all mounted under /api
    from .api.admin import admin_bp
    from .api.auth import auth_bp
    from .api.bookings import bookings_bp
    from .api.exports import exports_bp
    from .api.staff import staff_bp
    from .api.treks import treks_bp

    for bp in (auth_bp, treks_bp, bookings_bp, admin_bp, staff_bp, exports_bp):
        app.register_blueprint(bp)

    from .cli import register_cli
    register_cli(app)

    return app
