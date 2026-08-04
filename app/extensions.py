"""Extension instances, created here and bound to the app in create_app().

Keeping them in their own module is what lets models.py import `db` without
importing the application factory, which would be circular.
"""

from flask_caching import Cache
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cache = Cache()
security = Security()
