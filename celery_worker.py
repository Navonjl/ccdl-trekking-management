"""Celery entry point.

    worker: uv run celery -A celery_worker.celery worker --loglevel=info
    beat:   uv run celery -A celery_worker.celery beat --loglevel=info

`create_app()` calls celery_init_app(), which stores the Celery instance in
app.extensions["celery"], which is the object Celery needs here.
"""

import logging

from app import create_app

# The Azure Service Bus SDK logs every AMQP state change at INFO.
logging.getLogger("azure").setLevel(logging.WARNING)

flask_app = create_app()
celery = flask_app.extensions["celery"]
