"""Timer triggers that replace Celery beat.

Each trigger puts one ordinary Celery message on the Service Bus queue, and
whichever worker pod is free runs the job. The schedule lives in Azure, so the
cluster has no singleton scheduler process that must stay alive.

Azure Functions on Linux run cron expressions in UTC. India is UTC+5:30, so
18:00 IST is 12:30 UTC and 06:00 IST is 00:30 UTC.
"""

import logging
import os

import azure.functions as func
from celery import Celery

app = func.FunctionApp()

# Only used to send; the task code itself lives in the worker image.
celery = Celery(broker=os.environ["CELERY_BROKER_URL"])


def dispatch(task_name):
    result = celery.send_task(task_name)
    logging.info("queued %s as %s", task_name, result.id)


@app.timer_trigger(schedule="0 30 12 * * *", arg_name="timer", run_on_startup=False)
def daily_reminders(timer: func.TimerRequest) -> None:
    """Every day at 18:00 IST."""
    dispatch("app.tasks.send_daily_reminders")


@app.timer_trigger(schedule="0 30 0 1 * *", arg_name="timer", run_on_startup=False)
def monthly_report(timer: func.TimerRequest) -> None:
    """06:00 IST on the 1st of every month."""
    dispatch("app.tasks.send_monthly_activity_report")
