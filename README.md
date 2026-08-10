# Trekking Management Application (MAD-2)

A trekking management web application with three roles: Admin, Trek Staff and
User (Trekker). Flask serves a JSON API, Vue 3 provides the interface, SQLite
stores the data, Redis caches trek listings, and Celery runs the batch jobs.

## What is where

| Path | Contents |
| --- | --- |
| `main.py` | entry point; starts the API server |
| `celery_worker.py` | entry point for the Celery worker and beat |
| `app/config.py` | every configuration value, in one class |
| `app/models.py` | the database models, with the reasoning for the schema |
| `app/__init__.py` | the application factory, read this first |
| `app/extensions.py` | the `db`, `cache` and `security` objects |
| `app/celery_utils.py` | creates the Celery instance and the beat schedule |
| `app/tasks.py` | the three batch jobs |
| `app/mailer.py` | sending mail and Google Chat messages |
| `app/cli.py` | the `init-db` and `seed-demo` commands |
| `app/api/` | one blueprint per area, all mounted under `/api` |
| `frontend/src/views/` | pages, grouped by role |
| `frontend/src/components/` | the pieces shared between pages |

## Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node 22 or newer (Vite 8 requires it; see engines in frontend/package.json)
- Redis on `localhost:6379`

## Running it

Do steps 1 and 2 **before** a demo, since they download packages and are the slow
part.

```bash
# 1. Python dependencies
uv sync

# 2. Frontend dependencies
cd frontend && npm install && cd ..

# 3. Redis (on Arch the package is valkey, which provides redis-server)
sudo systemctl start valkey     # or: redis-server

# 4. Create the database and the admin account
uv run flask --app main init-db

# 5. Optional: some treks, staff and trekkers to click through
uv run flask --app main seed-demo
```

Then start the four processes, each in its own terminal:

```bash
uv run python main.py                                    # API      -> :5000
cd frontend && npm run dev                               # interface -> :5173
uv run celery -A celery_worker.celery worker --loglevel=info
uv run celery -A celery_worker.celery beat --loglevel=info
```

Open **http://localhost:5173**, not port 5000. Port 5000 is the API only and
has nothing to show at `/`.

The Vite dev server proxies `/api` to Flask, so the browser sees a single
origin and no CORS handling is needed.

## Logging in

The admin is created by `init-db`; its details are at the bottom of
`app/config.py`. `seed-demo` prints the credentials of every account it makes.

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@example.com` | `admin123` |
| Trek Staff | `ramesh.staff@example.com` | `staff123` |
| Trekker | `asha@example.com` | `trekker123` |

Admin and staff accounts cannot be registered: the admin is created by
`init-db`, and staff are created by the admin. Only trekkers may sign up.

## The batch jobs

`app/tasks.py` holds three jobs, scheduled in `app/celery_utils.py`:

| Job | When | What it does |
| --- | --- | --- |
| `send_daily_reminders` | daily, 18:00 | reminds trekkers about treks starting soon |
| `send_monthly_activity_report` | 1st of the month, 06:00 | e-mails the admin an HTML report for the previous month |
| `export_bookings_csv` | when a user asks | writes that user's booking history to CSV |

To run one immediately instead of waiting for its schedule:

```bash
uv run python -c "from app import create_app; create_app().app_context().push(); \
from app.tasks import send_daily_reminders; print(send_daily_reminders())"
```

### Where the reminders go

The daily reminder job posts to a Google Chat space when a webhook is
configured, and falls back to e-mail when it is not.

`GCHAT_WEBHOOK_URL` is read from the `.env` file in the project root by
`load_env_file()` in `app/config.py` (written by hand, because python-dotenv is not
one of the libraries the project statement allows). To point the reminders at
a different space, create an incoming webhook in that space under
**Apps & integrations -> Add webhooks** and replace the value in `.env`.

`Config.MAIL_SERVER` is empty by default, so e-mail is written to
`instance/outbox/` as `.eml` files rather than sent. That way the monthly
report and the export alert can be demonstrated without an SMTP server. Set
the `MAIL_*` values in `app/config.py` to send for real.

## Notes

- `instance/` holds the SQLite database, the mail outbox and generated CSVs.
  It is created at runtime and is not in version control.
- The database is created by `db.create_all()` in `app/cli.py`, never by hand
  in a GUI tool.
- Redis must be running before the API starts, or the first cached request
  will fail.
