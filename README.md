# BookFlow — Appointment Scheduling System

BookFlow is a full-stack web application that allows small businesses to accept and manage appointments online. Customers visit the site, pick a service and a staff member, browse a live calendar of available dates, choose an open time slot, and confirm their booking in under a minute. Business owners log in to a calendar-based admin dashboard where they can view every booking, confirm, complete, cancel, or reschedule appointments, leave internal notes, and have email notifications sent automatically at each step.

The name reflects the product's purpose: a smooth, frictionless flow from wanting an appointment to having one confirmed.

---

## Distinctiveness and Complexity

### Why BookFlow is Distinct from Every Other CS50W Project

BookFlow is an appointment scheduling system — a category that does not appear anywhere in CS50W Projects 1 through 4. Project 1 is a wiki. Project 2 is an auction platform. Project 3 is a mail client. Project 4 is a social network. None of them deal with time, availability, or resource allocation in any form.

The temptation might be to compare BookFlow to Project 2 (Commerce) because both involve a user selecting something and submitting a form. But the similarity is purely surface-level. Commerce is about listings, bids, and winning. BookFlow is about time — specifically, about computing which moments in the future are actually available given a set of constraints that change in real time. There are no listings, no bids, no auctions, no watchlists. The core problem BookFlow solves — "is this 30-minute window on Thursday genuinely free for this specific staff member, accounting for their break, any time-off, existing bookings, the business's buffer policy, and the minimum advance notice requirement?" — is not a problem that appears anywhere in the rest of the course.

### Why BookFlow is Complex

The complexity is not cosmetic. It runs through the architecture at every level.

**The slot generation engine** is the heart of the application. `generate_slots_for_staff` in `views.py` does not simply query a database and return rows. It performs timezone-aware datetime arithmetic using `pytz`, handles Daylight Saving Time edge cases (both the ambiguous fall-back hour and the non-existent spring-forward hour), enforces a configurable minimum notice window so customers cannot book a slot that starts too soon, skips staff break windows, checks per-date time-off records, and filters against all existing confirmed or pending bookings — without issuing N+1 database queries, because both the time-off list and the booked slots are pre-fetched before the slot-generation loop begins.

**Timezone correctness throughout.** Every datetime is stored as a timezone-aware UTC value. The business timezone is set via `BusinessSettings` and applied at runtime. The application uses `pytz.localize(..., is_dst=False)` to avoid `AmbiguousTimeError` on DST fall-back nights, and catches `NonExistentTimeError` for spring-forward gaps, returning an empty slot list for affected dates rather than crashing.

**A two-sided application with two separate JavaScript frontends.** The public booking page is driven by `booking.js`, which chains three dependent API calls — services, then staff, then available slots — each one gating the next. The admin dashboard is driven by `admin_calender.js`, which initialises a FullCalendar instance, fetches booking events via a JSON API, and handles confirm, cancel, complete, reschedule, and note actions through separate POST endpoints, all without a page reload.

**A live public calendar.** The homepage fetches real booking data from `/api/public-calendar/` on load and renders a navigable month-view calendar that highlights days with active bookings in colour. Days with confirmed bookings appear green; days with pending bookings appear amber. Past days are greyed out. This is not decorative — it reflects the actual state of the database and updates every time the page loads.

**A full email notification system.** Three distinct email events are handled: booking confirmation (sent simultaneously to the customer and the business admin), status change notifications (triggered whenever a booking is confirmed, completed, or cancelled), and reschedule notifications. Each email is rendered from an HTML template with a plain-text fallback. Customer and admin emails are sent in separate try/except blocks so that a failure delivering one does not suppress the other. All errors are logged but never bubble up to the user — a booking is never lost because of an email provider outage.

**Customer self-service without an account.** Customers can look up their booking using only their booking ID and phone number, view its current status, cancel it, or reschedule it — no login, no account creation required. The lookup view performs flexible phone matching that handles country-code prefix variations. The reschedule flow re-runs the full slot generation engine against the new date to verify availability before committing the change.

**A configurable business settings model.** `BusinessSettings` exposes six runtime knobs — timezone, slot interval, buffer between appointments, minimum advance notice, and maximum days ahead — that all feed directly into the slot generation engine. Changing a setting in the admin panel immediately changes which slots appear on the booking page.

---

## Files

### `bookflow/` — Django project package

- **`settings.py`** — Project configuration. All sensitive values (`SECRET_KEY`, SMTP credentials, `SITE_URL`, `ALLOWED_HOSTS`, `ADMIN_EMAIL`) are read from environment variables, making the app deployable to Render or any other host without touching code. Configures SMTP email (SendGrid by default), static file collection, and structured logging to stdout.
- **`urls.py`** — Root URL configuration. Mounts all application routes via `scheduler.urls` and Django's built-in admin under `/admin/`.
- **`wsgi.py`** / **`asgi.py`** — Standard WSGI and ASGI entry points.

### `scheduler/` — Application package

- **`models.py`** — Six Django models. `Service` stores name, duration, and price. `Staff` stores name, email, and an active flag. `WorkingHours` stores one row per staff member per weekday with optional break start and end times. `TimeOff` stores full-day or partial time-off entries per staff member. `BusinessSettings` is a singleton configuration table. `Booking` links a service and staff member to a customer (name, phone, email), stores a start and end datetime, and tracks a five-value status lifecycle: booked → confirmed → completed, or booked/confirmed → cancelled/no-show.
- **`views.py`** — All view and API logic for the application. Public page views render the home page, booking form, confirmation page, booking status page, lookup page, and reschedule page. Public API endpoints serve services, staff, available slots, available dates (for the booking calendar), and the public calendar data (for the homepage). Booking creation, customer cancellation, and customer reschedule are handled here. Admin API endpoints handle confirm, cancel, complete, no-show, reschedule, and note actions. The `generate_slots_for_staff` helper function contains the core scheduling engine logic.
- **`admin.py`** — Django admin configuration. `BookingAdmin` hooks into `save_model` to fire status-change emails when a booking is updated through the admin interface. `StaffAdmin` embeds `WorkingHoursInline` and `TimeOffInline` so a staff member's entire availability is managed in one place. `BusinessSettingsAdmin` blocks creation of a second settings row. `WorkingHoursAdmin` shows a readable day name column instead of a raw integer.
- **`urls.py`** — All URL patterns: public pages, public API endpoints, admin dashboard pages, and admin API endpoints.
- **`apps.py`** — Standard Django app config.
- **`utils/email_utils.py`** — `send_booking_confirmation` and `send_booking_status_update`. Renders HTML email templates, sends to customer and admin in independent try/except blocks, and logs outcomes without raising exceptions to the caller.

### `scheduler/static/scheduler/`

- **`booking.js`** — Drives the multi-step public booking form. Loads services on page load. Chains staff fetch on service selection, slot fetch on date selection. Validates all required fields including email format. Updates the live booking summary sidebar as the user selects each option. Submits via `fetch` and redirects to the confirmation page on success.
- **`admin_calender.js`** — Initialises the FullCalendar month/week/day view. Fetches booking events from the admin API and applies status-based colour classes. Handles event click to open a Bootstrap modal with full booking details. Implements confirm, cancel, complete, no-show, reschedule, and note actions as separate `fetch` POST calls. Refreshes the calendar after each action.
- **`styles.css`** — Application-wide custom styles: status badge colours, FullCalendar event hover effects, sticky footer layout, booking form card, and responsive breakpoints.

### `scheduler/templates/`

- **`scheduler/base.html`** — Base layout. Sticky navbar with BookFlow brand, navigation links, staff login/logout, and a prominent Book Now call-to-action. Flash message rendering. Responsive hamburger menu for mobile. Shared CSS design system (CSS variables, typography, form elements, buttons, badges).
- **`scheduler/public/index.html`** — Homepage. Hero section with live booking calendar that fetches real data from `/api/public-calendar/` and renders a navigable month view with colour-coded days. Feature cards below the fold.
- **`scheduler/public/book.html`** — Multi-step booking form with a live summary sidebar. Step 1: service and staff. Step 2: date (loaded from available-dates API). Step 3: time slot grid. Step 4: customer contact form.
- **`scheduler/public/confirmation.html`** — Post-booking confirmation page showing booking ID, service, staff, date, time, and customer details. Links to booking status page.
- **`scheduler/public/booking_status.html`** — Customer-facing booking status page. Shows all booking details, current status badge, admin note if present. Provides cancel and reschedule actions for eligible bookings.
- **`scheduler/public/lookup_booking.html`** — Booking lookup form. Accepts booking ID and phone number and redirects to the booking status page.
- **`scheduler/public/reschedule.html`** — Customer reschedule form. Shows current appointment details, then date and time pickers that fetch available slots dynamically.
- **`scheduler/admin/dashboard.html`** — Admin calendar dashboard built on FullCalendar with booking detail modals, action buttons, reschedule modal, and note modal.
- **`scheduler/admin/bookings.html`**, **`services.html`**, **`staff.html`**, **`settings.html`** — Admin section placeholder pages.
- **`emails/customer_confirmation.html`**, **`emails/admin_notification.html`**, **`emails/status_update.html`** — HTML email templates.

### Root

- **`manage.py`** — Django management command entry point.
- **`requirements.txt`** — All Python dependencies.
- **`db.sqlite3`** — SQLite database used in development. Not committed in production.
- **`.env`** — Local environment variable overrides. Not committed to version control.

---

## How to Run Locally

**Prerequisites:** Python 3.10 or higher, pip.

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd capstone

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Create a superuser for the admin dashboard
python manage.py createsuperuser

# 6. Start the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000` to see the public site.  
Open `http://127.0.0.1:8000/admin/login/` to access the admin dashboard.

**Before any bookings can be made**, log in to the admin panel and create:
1. At least one **Service** (name, duration in minutes, price)
2. At least one **Staff** member with **Working Hours** set for each day they work
3. A **BusinessSettings** row (timezone, slot interval, etc.)

### Testing Email Locally

By default email is silent because `EMAIL_HOST_PASSWORD` is not set. To see emails printed to the terminal instead, add this to `settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

---

## Deploying to Render

1. Create a **Web Service** on Render pointed at this repository.
2. Set these environment variables in the Render dashboard:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `yourapp.onrender.com` |
| `SITE_URL` | `https://yourapp.onrender.com` |
| `EMAIL_HOST` | `smtp.sendgrid.net` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | `apikey` |
| `EMAIL_HOST_PASSWORD` | Your SendGrid API key |
| `DEFAULT_FROM_EMAIL` | `noreply@yourdomain.com` |
| `ADMIN_EMAIL` | Your business inbox |

3. Set the **Start Command** to:
```
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn bookflow.wsgi
```

4. Add `gunicorn` and `whitenoise` to `requirements.txt`. Add `whitenoise.middleware.WhiteNoiseMiddleware` to `MIDDLEWARE` in `settings.py` (immediately after `SecurityMiddleware`) for static file serving.

> **Database note:** Render's free tier has an ephemeral filesystem — SQLite data is lost on redeploy. For a persistent deployment, provision a Render PostgreSQL database, set `DATABASE_URL`, install `dj-database-url`, and update the `DATABASES` setting accordingly.

---

## Additional Notes

- **Weekday convention:** `WorkingHours.weekday` follows Python's `date.weekday()` numbering: `0 = Monday`, `6 = Sunday`. This is the same convention used by Django's admin display choices and the slot generation engine. Make sure entries in the admin match this — a common mistake is entering `0` expecting Sunday.
- **No-show endpoint:** The no-show button in the admin calendar calls `/api/admin/booking/<id>/no-show/`. Make sure `api_admin_booking_no_show` is present in `views.py` and its URL is registered in `urls.py`.
- **iCal download:** `/api/booking/<id>/ical/` generates a `.ics` file the customer can import into any calendar app.
- **Single BusinessSettings row:** The admin is configured to block creation of a second row. If the settings page appears empty, create exactly one row and do not create more.
