# Trekking Management Application (MAD-2)

A web application for running trekking trips, with three roles: Admin, Trek
Staff and User (Trekker). Flask serves a JSON API, Vue 3 provides the
interface, SQLite stores the data, Redis caches the trek listing, and Celery
runs the batch jobs.

## Demo video

https://drive.google.com/file/d/1U_JzIsp07bKsglbXrQOeZfjqiluvrjXR/view?usp=sharing

## What is where

| Path | Contents |
| --- | --- |
| `main.py` | entry point, starts the API server |
| `celery_worker.py` | entry point for the Celery worker and beat |
| `app/__init__.py` | the application factory, worth reading first |
| `app/config.py` | every configuration value, in one class |
| `app/models.py` | the database models, with the reasoning for the schema |
| `app/extensions.py` | the `db`, `cache` and `security` objects |
| `app/celery_utils.py` | creates the Celery instance and the beat schedule |
| `app/tasks.py` | the three batch jobs |
| `app/mailer.py` | sending mail and Google Chat messages |
| `app/cli.py` | the `init-db` and `seed-demo` commands |
| `app/api/` | one blueprint per area, all mounted under `/api` |
| `frontend/src/views/` | pages, grouped by role |
| `frontend/src/components/` | the pieces shared between pages |

## Requirements

Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 22 or newer, and Redis
on `localhost:6379`. Node 22 is the floor because Vite 8 requires it; the exact
range is in `engines` in `frontend/package.json`.

## Running it

The first two steps download packages and are the slow part, so do them ahead
of any demo.

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

Then start four processes, each in its own terminal:

```bash
uv run python main.py                                    # API       -> :5000
cd frontend && npm run dev                               # interface -> :5173
uv run celery -A celery_worker.celery worker --loglevel=info
uv run celery -A celery_worker.celery beat --loglevel=info
```

Open http://localhost:5173. Port 5000 is the API on its own and has nothing to
show at `/`. The Vite dev server proxies `/api` through to Flask, so the
browser only ever sees one origin and no CORS handling is needed.

## Logging in

`init-db` creates the admin, whose details are at the bottom of
`app/config.py`. `seed-demo` prints the credentials of every account it makes.

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@example.com` | `admin123` |
| Trek Staff | `ramesh.staff@example.com` | `staff123` |
| Trekker | `asha@example.com` | `trekker123` |

Only trekkers can sign up. The admin comes from `init-db` and staff accounts
are created by the admin, so neither has a registration route.

## The batch jobs

`app/tasks.py` holds three jobs, scheduled in `app/celery_utils.py`:

| Job | When | What it does |
| --- | --- | --- |
| `send_daily_reminders` | daily, 18:00 | reminds trekkers about treks starting soon |
| `send_monthly_activity_report` | 1st of the month, 06:00 | e-mails the admin an HTML report for the previous month |
| `export_bookings_csv` | when a user asks | writes that user's booking history to CSV |

To run one straight away instead of waiting for its schedule:

```bash
uv run python -c "from app import create_app; create_app().app_context().push(); \
from app.tasks import send_daily_reminders; print(send_daily_reminders())"
```

### Where the reminders go

The reminder job posts to a Google Chat space when a webhook is configured, and
writes e-mail when it is not.

`GCHAT_WEBHOOK_URL` comes from the `.env` file in the project root, read by
`load_env_file()` in `app/config.py`. That function is written by hand because
python-dotenv is not one of the libraries the project statement allows. To use
a different space, create an incoming webhook there under Apps & integrations,
Add webhooks, and replace the value in `.env`.

`Config.MAIL_SERVER` is empty by default, so e-mail is written to
`instance/outbox/` as `.eml` files rather than sent. The monthly report and the
export alert can therefore be demonstrated with no SMTP server. Fill in the
`MAIL_*` values in `app/config.py` to send for real.

## Notes

`instance/` holds the SQLite database, the mail outbox and the generated CSVs.
It is created at runtime and is not in version control.

The database is created by `db.create_all()` in `app/cli.py`, never by hand in
a GUI tool.

Redis has to be running before the API starts, or the first request that hits
the cache will fail.
