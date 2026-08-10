"""Celery entry point.

    worker: uv run celery -A celery_worker.celery worker --loglevel=info
    beat:   uv run celery -A celery_worker.celery beat --loglevel=info

`create_app()` calls celery_init_app(), which stores the Celery instance in
app.extensions["celery"], which is the object Celery needs here.
"""

from app import create_app

flask_app = create_app()
celery = flask_app.extensions["celery"]
