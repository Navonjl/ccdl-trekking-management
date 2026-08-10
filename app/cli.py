"""Command line commands.

`flask init-db` creates the tables and the one admin account. The database is
created here in code, because the project spec forbids making it by hand in a tool
like DB Browser for SQLite.
"""

import click
from flask_security import hash_password

from .extensions import db, security
from .models import ROLE_ADMIN, ROLE_STAFF, ROLE_USER


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create tables, the three roles, and the admin account."""
        db.create_all()

        for name, description in (
            (ROLE_ADMIN, "Manages the whole system"),
            (ROLE_STAFF, "Runs the treks assigned to them"),
            (ROLE_USER, "Books and goes on treks"),
        ):
            security.datastore.find_or_create_role(name=name, description=description)
        db.session.commit()

        # Exactly one admin, created programmatically. There is no admin
        # registration route anywhere in the app.
        email = app.config["ADMIN_EMAIL"]
        if not security.datastore.find_user(email=email):
            security.datastore.create_user(
                email=email,
                password=hash_password(app.config["ADMIN_PASSWORD"]),
                full_name="Administrator",
                roles=[ROLE_ADMIN],
            )
            db.session.commit()
            click.echo(f"created admin {email}")
        else:
            click.echo(f"admin {email} already exists")

        click.echo("database ready")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Add a few staff, treks and trekkers to demo with."""
        from .demo_data import load_demo_data

        load_demo_data()
        click.echo("demo data loaded")
