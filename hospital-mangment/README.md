# CarePoint Hospital Management System

A lightweight hospital appointment and records application built with Flask, SQLite, server-rendered HTML, and Bootstrap.

## Features

- Patient registration, login, and appointment history
- Separate patient, doctor, and administrator roles
- Doctor directory with all ten supported specializations and filtering
- Doctor profile management for administrators
- Doctor availability management and appointment status updates
- Appointment references, status tracking, cancellations, and database-enforced slot booking protection
- Admin dashboard with totals and today's appointments, plus patient and appointment directories

## Run locally

Requires Python 3.10 or later.

1. Open this folder in VS Code and create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Configure local secrets before starting. Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"` and set it in PowerShell:

   ```powershell
   $env:SECRET_KEY = "paste-a-generated-secret-here"
   $env:ADMIN_PASSWORD = "choose-a-strong-local-admin-password"
   $env:ADMIN_EMAIL = "admin@hospital.local"
   ```

   The database creates a local admin account from `ADMIN_EMAIL` and `ADMIN_PASSWORD` the first time it is initialized. If no admin password is configured, the development default is `admin123`; replace it before using the application beyond local testing.

4. Start the server:

   ```powershell
   python app.py
   ```

5. Visit http://127.0.0.1:5000.

The SQLite database (`hospital.db`) is created in the project folder automatically. Set `COOKIE_SECURE=1` only when serving over HTTPS. Set `FLASK_DEBUG=1` for local debugging only.

## Demo accounts

Sample doctor accounts are seeded with the password `doctor123`:

- `asha.rao@hospital.local`
- `daniel.kim@hospital.local`
- `maya.patel@hospital.local`
- `ethan.lee@hospital.local`
- `sofia.ahmed@hospital.local`

Choose **Doctor** on the login form. Patients can register through the site. Admin credentials are the values configured with `ADMIN_EMAIL` and `ADMIN_PASSWORD`.

## Tests

Run the built-in tests with:

```powershell
python -m unittest discover -s tests -v
```

The booking test creates two patient accounts and verifies that the same available doctor slot can only be booked once.

## Data and deployment notes

Use synthetic data only. This starter is intended for local development and demonstration, not production healthcare use. Before real deployment, configure a persistent random secret, HTTPS, CSRF protection, secure operational access controls, backups, audit logging, and applicable privacy/security compliance. Bootstrap is loaded from its public CDN by default, so the interface needs an internet connection to load Bootstrap assets.
