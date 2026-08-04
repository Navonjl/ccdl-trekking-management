# Viva walkthrough

A map from each rubric question to the code that answers it, with the answer to
give. Line numbers are hints only — they move when the code changes, so the
function name is the reliable thing to search for.

**Not part of the submission.** This file and the rest of `docs/` stay out of
the zip.

The two rules that matter more than anything below:

1. **If you do not know, say so, then reason out loud from the code.** Guessing
   confidently and being wrong reads far worse than "I'm not sure, let me look
   — it's in `config.py`, so…".
2. **Open the file before answering.** You are allowed to read your own code.
   An examiner watching you navigate straight to the right file is seeing
   someone who knows their project.

---

## Q1 — Explain the project organization

Open `app/__init__.py` and read `create_app()` top to bottom. It *is* the map.

| Where | What |
| --- | --- |
| `app/config.py` | every setting, one class |
| `app/models.py` | the five tables |
| `app/extensions.py` | the `db`, `cache`, `security` objects |
| `app/__init__.py` | the factory that binds them together |
| `app/api/*.py` | the controllers — one blueprint per area |
| `app/celery_utils.py` | creates the Celery instance |
| `app/tasks.py` | the three batch jobs |
| `app/cli.py` | `init-db`, `seed-demo` |
| `frontend/src/views/` | pages, in `admin/`, `staff/`, `user/` folders |
| `frontend/src/components/` | the pieces shared between pages |
| `frontend/src/api.js` | every call to the backend |

Say: *"Extensions are created in `extensions.py` rather than inside the factory
so that `models.py` can import `db` without importing the app — that would be a
circular import."* That one sentence answers the follow-up before it comes.

## Q2 — Explain how Celery and Redis are set up

They will ask **where the instance is created** and **where the configuration
lives**. Answer with three files:

- **Created:** `app/celery_utils.py:25`, `Celery(app.name, task_cls=FlaskTask)`,
  called from `create_app()` at `app/__init__.py:29`.
- **Configured:** the `CELERY` dict at `app/config.py:60`, read at
  `celery_utils.py:26` via `config_from_object`.
- **Started:** `celery_worker.py`, which picks the instance back out of
  `app.extensions["celery"]`.

Redis does **two separate jobs**, on three databases — know this, it is a
favourite follow-up:

| Redis DB | Used for | Config |
| --- | --- | --- |
| 0 | Celery broker (the job queue) | `config.py:61` |
| 1 | Flask-Caching (trek listings) | `config.py:57` |
| 2 | Celery result backend | `config.py:62` |

**"What is `FlaskTask`?"** (`celery_utils.py:17`) — *"The worker is a separate
process with no Flask request, so it has no application context and
`db.session` would fail. `FlaskTask.__call__` wraps every task in
`app.app_context()`, which is why the tasks can just use the database."*

**"Where is the schedule?"** `celery_utils.py:29` — daily reminders at 18:00
(`crontab(hour=18, minute=0)`), monthly report on the 1st at 06:00
(`crontab(day_of_month=1, hour=6, minute=0)`). The monthly job reports the
*previous* month, because on the 1st the current month has no data yet.

**"Show me a job running."** Do not wait for the schedule:

```bash
uv run python -c "from app import create_app; create_app().app_context().push(); \
from app.tasks import send_daily_reminders; print(send_daily_reminders())"
```

Then open `instance/outbox/` — mail is written there as `.eml` files because
`MAIL_SERVER` is empty. **Know this before the viva**: if asked "where did the
email go?", the answer is that folder, not a mail client.

## Q3 — Explain the database design and the idea behind it

The reasoning is written at the top of `app/models.py`. Three decisions to own:

**One user table, not three.** *"Admin, staff and trekker store the same things
— email, password, name, phone — and differ only in what they may do. So it is
one `User` table with roles joined many-to-many through `roles_users`. That
makes login one code path instead of three, and the spec asks for a unified
user model."*

**`StaffProfile` is separate.** *"It holds `employee_code` and `status`, which
only staff have. On the user table those columns would be NULL for every
trekker."*

**`available_slots` is stored, not counted.** Expect *"why not just count the
bookings?"* — *"Counting means a COUNT query per trek on every listing. Storing
it makes the listing one plain SELECT, and I change the count in the same
request that creates the booking so the two cannot drift."* The honest trade-off
to admit if pushed: a stored number **can** drift if code forgets to update it,
which is why the update lives in exactly one place.

**Draw the ER diagram from this** (you still owe it in the report):

```
Role ──many-to-many(roles_users)── User ──one-to-one── StaffProfile
                                     │                      │
                                 one-to-many            one-to-many
                                     │                      │
                                  Booking ──many-to-one── Trek
```

## Q4 — Explain the application flow between Vue components

Trace one journey out loud — login is the best one:

1. `views/LoginView.vue` collects email + password, calls `api.login()`.
2. `api.js` POSTs `/api/accounts/login?include_auth_token`. **Know why that
   query parameter is there:** without it Flask-Security assumes a cookie
   session and does not put a token in the body.
3. The token goes into `store.js`, a small `reactive()` object.
4. `router/index.js:116` — `router.beforeEach` reads the roles and sends admin
   to `/admin`, staff to `/staff`, trekker to `/treks`.
5. `App.vue` watches `store.token`; when `api.js` clears it on a 401, that
   watcher redirects to login.

**"Why a store instead of props?"** — *"The token is needed by `api.js` and the
router, which are not components, so passing it as props is impossible."*

**Parent → child example:** `AdminTreks.vue` renders `TrekForm.vue`, passing the
trek being edited as a prop and receiving a `save` event back. That is the
"control shifting between components" they are asking about.

## Q5 — Purpose of the API, endpoints, and authentication

*"The Vue app is static files in the browser; it cannot touch the database. The
Flask API is the only thing that does, which also means every rule is enforced
in one place — the browser cannot skip a check."*

Endpoint list: the header comment in `frontend/src/api.js` lists all of them,
grouped. 30 application endpoints plus Flask-Security's login/logout.

**Auth mechanism, in order:**
1. `POST /api/accounts/login?include_auth_token` returns a token.
2. Every later request carries it as `Authentication-Token`
   (`api.js:84`).
3. `@auth_required("token")` checks it; `@roles_required("admin")` checks the
   role. Both are Flask-Security decorators.
4. Config: `SECURITY_API_ENABLED_METHODS` at `config.py:37`.

**"Why is CSRF disabled?"** (`config.py:50`) — *"CSRF attacks work because a
browser sends cookies automatically. We authenticate with a header the attacker
cannot make the browser add, so there is nothing to protect."* This is a good
answer; do not be apologetic about it.

## Q6 & Q7 — Two backend questions

Most likely target: the four rules in `book_trek()` (`app/api/bookings.py`).
They are numbered in the code.

| Rule | Line | Spec wording |
| --- | --- | --- |
| 1 trek exists | :37 | — |
| 2 status must be Open | :41 | "Allow booking only when trek status is Open" |
| 3 slots available | :56 | "Prevent overbooking beyond available slots" |
| 4 no duplicate | :46 | "Prevent duplicate bookings for same trek" |

**The question worth rehearsing: "what if two people book the last slot at the
same time?"** Rule 3 is deliberately not a plain `if`:

```python
rows_changed = Trek.query.filter(
    Trek.id == trek.id, Trek.available_slots > 0
).update({"available_slots": Trek.available_slots - 1})
if rows_changed == 0:
    return error("This trek is full.")
```

*"Reading the count, checking it, then subtracting is three steps — two
requests can both read 1 free slot and both book it. Here it is one UPDATE with
a WHERE clause, so the database only decrements while a slot is free, and the
row count tells me whether I got it."*

Second likely target: **caching** (`app/api/treks.py:51`). *"The trek listing is
cached in Redis for 60 seconds. `query_string=True` makes each filter
combination its own cache key. It is skipped for admin and staff (`unless=`)
because the cache key does not include the role — an admin request would
otherwise put Pending treks into the listing a trekker then sees."* Writes call
`clear_trek_cache()` (`treks.py:28`).

Also know: **`check_assigned()`** in `app/api/staff.py:26` is what stops staff
touching another staff member's trek, and **`is_my_export()`** in
`app/api/exports.py:25` is what stops one user downloading another's CSV (the
owner id is in the filename).

## Q8 & Q9 — Two frontend questions

**The export polling loop** (`views/user/MyBookings.vue`) — *"The CSV is built
by a Celery worker, so the POST only returns a task id. The component then asks
`/api/exports/<task_id>` every couple of seconds until the state is ready, then
shows the download link."*

**The blob download** (`api.js:226`) — *"The download route needs the
`Authentication-Token` header, and a plain `<a href>` cannot send headers. So I
fetch the file, wrap it in a blob URL, and click that."*

**The chart** (`components/BarChart.vue`) — *"ChartJS draws onto a canvas in
`mounted()` and is destroyed in `beforeUnmount()` so it does not leak. The data
is grouped from the bookings list in `AdminDashboard.vue`."* Honest weakness to
admit if pushed: it downloads every booking to draw five bars.

## Q10 — Change the backend when asked

Rehearse these three. The dev server auto-reloads, so a save is enough.

| If they ask | Do this |
| --- | --- |
| "Make the reminder window 7 days instead of 3" | `app/tasks.py`, the day window near the top of `send_daily_reminders` |
| "Change the cache to 5 minutes" | `CACHE_DEFAULT_TIMEOUT`, `config.py:58` |
| "Run the monthly report weekly" | `beat_schedule`, `celery_utils.py:29` — needs a worker restart, say so |
| "Add a field to the trek listing" | add it to `Trek.to_dict()` in `models.py` |
| "Let trekkers see Closed treks too" | `TREKKER_VISIBLE_STATUSES`, `treks.py:20` |

Practise the last one now — it is one tuple and proves you know where
visibility is decided.

## Q11 — Change the frontend when asked

| If they ask | Do this |
| --- | --- |
| "Add a column to a table" | the `<thead>`/`<tbody>` of that view; the field is already in the JSON |
| "Change a label or button text" | the template of that view |
| "Sort treks by name" | a `computed` in `BrowseTreks.vue` |
| "Make a field required" | add `required` to the input — HTML5 does the rest |

Vite hot-reloads, so the change appears without a refresh.

## Q12–Q16 — General questions and presentation

Not about your code. Expect Flask/Vue/Redis/Celery fundamentals: what a
decorator is, what a blueprint is, why caching helps, what a message broker is,
what an ORM is, session vs token auth.

## Q17 — "Do you feel the student has copied this?"

This is the item with the worst consequences, and it is answered by behaviour,
not by anything in a file. What helps:

- Navigate your own code fast, without hunting.
- Answer "why" questions, not just "what" — the *why* is what a copier lacks.
- Be honest about the trade-offs and weak spots. Volunteering "this downloads
  every booking to draw five bars, which I would fix by adding an endpoint"
  sounds like an author. Nobody who copied code says that.
- **Declare your AI/LLM use in the report.** The course permits it: *"Usage of
  AI/LLM/coding agents will be considered only if students showcase basic
  understanding of the code submitted."* The condition is understanding, not
  authorship. An accurate declaration plus fluent answers is a strong position;
  a missing declaration is what turns questions into a malpractice case.

---

## Awkward questions — have these ready

**"Why does the `user` table have `us_totp_secrets` and `fs_webauthn_user_handle`?"**
*"They come from Flask-Security's `fsqla_v3` model mixin, which ships two-factor
and WebAuthn support. I use email, password, active, `fs_uniquifier` and roles;
the rest are unused features of the extension."*

**"Why two servers? Why is `localhost:5000` blank?"**
*"Port 5000 is the API only. The interface is the Vite dev server on 5173, which
proxies `/api` to Flask."*

**"Where is your CORS configuration?"**
*"There isn't any, deliberately. Every request is a relative `/api/...` URL that
Vite proxies, so the browser only ever sees one origin. The spec forbids extra
libraries, and this avoids needing flask-cors at all."*

**"Deactivate and blacklist look like the same thing."**
*"`active` is Flask-Security's flag and blocks login. `is_blacklisted` is my own
column — the user can still log in and look around, but `blocked_check` refuses
booking, cancelling and exporting."*

**"Why can't I delete a trek that has bookings?"**
*"Deleting it would destroy the trekking history the spec says to maintain, so I
refuse and tell the admin to Close or Complete it instead."*

**"Marking a trek Completed also changed the bookings — why?"**
*"Otherwise a finished trek sits in every trekker's history as 'Booked' for
ever."*

**"Can staff mark a trek as Started?"**
*"No — the spec's own list of trek statuses has no Started, so Open is the
running state."* (This is a real gap; the honest answer is the best one.)

**"Is `payment_status` a real payment?"**
*"No. The spec lists payment as optional, so the admin just records that the
money arrived — there is no gateway."*

**"Is this Redis or Valkey?"**
On Arch the package is `valkey`, which provides `redis-server` and `redis-cli`
and speaks the same protocol; the code and config are plain Redis
(`redis://localhost:6379`). Only comes up if they watch you start the service.

**"Why does the database have no data when I open it?"**
`instance/` is not in the zip. Run `init-db` then `seed-demo`.

---

## Before the viva

- [ ] `uv sync` and `npm install` **done in advance** — installing during the
      viva is not allowed, and L1 requires the project running within 10 minutes.
- [ ] Rehearse the cold start from the README, timed, on the machine you will use.
- [ ] Redis running, and know the command to start it.
- [ ] All four processes started: API, Vite, Celery worker, Celery beat.
- [ ] `init-db` + `seed-demo`, and know the demo logins.
- [ ] Trigger one Celery job manually and look in `instance/outbox/` so you have
      seen it work.
- [ ] ID card ready to show, mic/camera/screen-share tested.
- [ ] Report submitted with ER diagram, endpoint list, AI/LLM declaration and
      the video Drive link (set to anyone-with-link).
