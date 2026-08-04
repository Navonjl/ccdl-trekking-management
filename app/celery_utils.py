"""Celery wiring.

The Celery instance is created here by `celery_init_app`, which is called from
`create_app` in app/__init__.py. Its configuration comes from the `CELERY`
dict in app/config.py -- there is exactly one place for each.

Tasks need the Flask application context to touch the database, so every task
is wrapped in one by the FlaskTask base class below. That is why a task can
just use `db.session` without any setup of its own.
"""

from celery import Celery, Task
from celery.schedules import crontab
from flask import Flask


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        """Runs each task inside an application context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])

    # Periodic jobs. Times are in the timezone set in config (Asia/Kolkata).
    celery_app.conf.beat_schedule = {
        # Job (a): daily reminders about upcoming treks.
        "daily-trek-reminders": {
            "task": "app.tasks.send_daily_reminders",
            "schedule": crontab(hour=18, minute=0),
        },
        # Job (b): monthly activity report to the admin, first of the month.
        "monthly-activity-report": {
            "task": "app.tasks.send_monthly_activity_report",
            "schedule": crontab(day_of_month=1, hour=6, minute=0),
        },
    }

    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app
