"""The user-triggered async job: export my booking history as CSV.

Three steps, one endpoint each:

1. POST /api/exports/bookings   -- hand the work to Celery, get a task id back
2. GET  /api/exports/<task_id>  -- the SPA polls this until the state is ready
3. GET  /api/exports/download/<filename> -- fetch the finished file

The Flask request never builds the CSV itself; the Celery worker does, so the
browser is not left waiting on it.
"""

from celery.result import AsyncResult
from flask import Blueprint, current_app, jsonify, send_from_directory
from flask_security import auth_required, current_user
from werkzeug.utils import secure_filename

from ..config import Config
from . import blocked_check, error

exports_bp = Blueprint("exports", __name__, url_prefix="/api")


@exports_bp.post("/exports/bookings")
@auth_required("token")
@blocked_check
def start_export():
    """Queue the CSV job for the logged-in user and return its task id."""
    # Imported inside the view: app/tasks.py imports the models and the app
    # package, so importing it at module level would be circular.
    from ..tasks import export_bookings_csv

    task = export_bookings_csv.delay(current_user.id)
    return jsonify({"task_id": task.id, "state": "PENDING"}), 202


@exports_bp.get("/exports/<task_id>")
@auth_required("token")
def export_status(task_id):
    """Report the job's state; add the filename once it has succeeded."""
    result = AsyncResult(task_id, app=current_app.extensions["celery"])

    body = {"task_id": task_id, "state": result.state, "ready": result.ready()}

    if result.successful():
        # The task returns {"filename": ...}; see app/tasks.py.
        value = result.result or {}
        body["filename"] = value.get("filename")
    elif result.failed():
        body["error"] = str(result.result)

    return jsonify(body)


@exports_bp.get("/exports/download/<filename>")
@auth_required("token")
def download_export(filename):
    """Send a finished CSV out of instance/exports/."""
    # secure_filename strips any path parts, so "../../instance/trekking.sqlite3"
    # cannot escape the export folder.
    safe_name = secure_filename(filename)
    if not safe_name:
        return error("Bad file name.")

    if not (Config.EXPORT_DIR / safe_name).is_file():
        return error("Export file not found.", 404)

    return send_from_directory(Config.EXPORT_DIR, safe_name, as_attachment=True)
