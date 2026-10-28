# Family Departmental Store Management System

A Flask and SQLite application for managing a departmental store. It provides
user login, stock and product management, supplier records, purchases, billing,
printable receipts, low-stock alerts, and sales reports.

## Technology

- Python 3.10 or newer
- Flask
- SQLite
- Gunicorn in production on Linux

The application entry point is `app.py`. The database is created automatically
at the path configured by `DATABASE_PATH` (by default, `store.db` beside
`app.py`). Local database files are intentionally excluded from Git.

## Run locally on Windows

Open PowerShell in this project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "choose-a-unique-password"
python app.py
```

Choose your own password; do not commit it or share it. The username and
password are used only when the configured database has no users yet. To add
an initial cashier account, also set both `$env:CASHIER_USERNAME` and
`$env:CASHIER_PASSWORD` before the first run. Leave both unset to create only
the administrator.

Visit <http://127.0.0.1:5000>. After the database has been initialized, the
administrator environment variables are not needed on subsequent starts.
Keep `store.db` private and backed up; it can contain store and sales data.

## Configuration

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session signing key. A temporary random value is used locally when unset; configure a stable, private value in production. |
| `DATABASE_PATH` | SQLite database location. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Required to create the administrator in a new, empty database. |
| `CASHIER_USERNAME`, `CASHIER_PASSWORD` | Optional pair for creating a cashier in a new, empty database. |
| `SESSION_COOKIE_SECURE` | Set to `true` when the app is served over HTTPS. |

These initial-account settings do not reset or modify existing accounts in a
database that already contains users.

## Deploy to Render

`render.yaml` configures a Python web service, installs dependencies, and runs
Gunicorn rather than Flask's development server. It places SQLite data on a
persistent disk mounted at `/var/data`. Render requires a paid web service for
persistent disks; without one, the default filesystem is ephemeral and
database changes can be lost on redeploy or restart.

1. Push this project to a GitHub repository.
2. In Render, choose **New → Blueprint**, connect the repository, and select
   this project's `render.yaml`.
3. Before the first deploy, provide `ADMIN_USERNAME` and `ADMIN_PASSWORD` when
   Render prompts for the values marked `sync: false`. Use a unique password
   and never place it in the repository. Optionally provide both cashier
   variables.
4. Review the selected paid service plan and disk cost, then confirm creation.
   The blueprint generates `SECRET_KEY` for the service and configures HTTPS
   cookies and the persistent SQLite path.
5. Wait for Render's deploy status to become **Live**, then open the service's
   URL and sign in with the initial account you configured.

The included SQLite setup is suitable for a small demonstration or a
single-instance store deployment. For higher traffic, multiple application
instances, or production business data, use a managed database such as
PostgreSQL and implement appropriate backups and access controls.
