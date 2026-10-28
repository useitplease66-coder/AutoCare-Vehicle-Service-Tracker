# AutoCare — Vehicle Service History Tracker

A working DBMS mini-project built with **Flask, MySQL 8, PyMySQL, HTML/CSS/JS and Chart.js**. Includes login, vehicle registration, service history, workshops, date/mileage reminders, spending dashboard, analytics, triggers, views, stored procedure, indexes, and ACID transactions.

## Setup on Windows (VS Code + MySQL Workbench)

### 1. Install
- Python 3.10+ and MySQL Server 8.0+ (MySQL Workbench is optional but convenient).
- Make sure the local MySQL server is running.

### 2. Create the database
Open MySQL Workbench as a MySQL administrator and run the full `sql/schema.sql` script (File → Open SQL Script → Execute All). Run `sql/create_app_user.sql` **after replacing the sample password**.

> Important: The sample `autocare_app` MySQL account is for local development. Use a strong password and don't commit `.env` to Git. If the user already exists, reset its password using `ALTER USER 'autocare_app'@'localhost' IDENTIFIED BY 'your-new-password';`.

### 3. Configure the application
Open a terminal in the `AutoCare_Project` folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

In `.env`, set `MYSQL_PASSWORD` to the password chosen above and replace `SECRET_KEY` with a long random value. Keep `MYSQL_HOST=127.0.0.1` if you are running MySQL on the same computer. The account created with host `localhost` normally works for this local configuration; if your MySQL installation treats connections differently, create the app user for the matching host.

### 4. Run
```powershell
python app.py
```
Open **http://127.0.0.1:5000** and register an account. Data is stored in your actual MySQL database. The site has no preconfigured web admin or sample password.

### 5. Demo sequence
1. Register a user and sign in.
2. Add a car with registration `MH10AB1234` and odometer `12000`.
3. Add a workshop.
4. Log two services and verify expense totals on dashboard.
5. Create a reminder due on a nearby date or odometer reading.
6. Open Analytics; check the MySQL view and trigger-driven audit entries.
7. Run `sql/demo_queries.sql` in MySQL Workbench for JOIN, GROUP BY, HAVING, subquery, view and audit output.
8. Explain why saving a service locks the vehicle row and commits both service insertion and mileage update in the same transaction.

## App pages
- `/register`, `/login`: authentication using salted password hashes.
- `/dashboard`: KPIs, spending chart, reminders and recent services.
- `/vehicles`: vehicle CRUD (create/list/delete).
- `/services`: service CRUD (create/list/delete) and transactional mileage update.
- `/workshops`: add/list workshops.
- `/reminders`: create/list/complete/delete reminders.
- `/reports`: live SQL view and GROUP BY analytics, visible audit events for currently existing service records.

## DBMS concepts covered
- **ER model:** one user → many vehicles/workshops; one vehicle → many services/reminders; one workshop → many service records.
- **Normalization:** user, vehicle, workshop, service and reminder attributes stored separately (3NF design suitable for the application).
- **Constraints:** primary/foreign keys, UNIQUE registration numbers and emails, NOT NULL, CHECK constraints, ENUM types.
- **Joins:** service records joined with vehicles and workshops.
- **Views:** `vw_vehicle_expenses` used in dashboard and reports.
- **Stored procedure:** `CALL sp_vehicle_service_summary(<user_id>);` run in MySQL Workbench as an authorized user.
- **Triggers:** insert/update/delete audit on `service_records`. The app currently exposes create/delete actions; update triggers can be demonstrated with SQL directly.
- **Transactions & concurrency:** INSERT service + UPDATE odometer in one transaction, SELECT ... FOR UPDATE lock, COMMIT/ROLLBACK.
- **Indexes:** indexed service records by vehicle/date and reminders by status/date.
- **Security:** parameterized SQL queries, hashed passwords, session login, per-user ownership checks and low-privilege MySQL account.

## Important scope notes
- Reminders are displayed in-app, **not delivered by SMS or email**.
- Chart.js and the Google font load from CDNs; the core site functions offline but graphs/fonts may need an internet connection.
- Delete a vehicle only after considering that it removes related service and reminder records. Audit rows do not include user/vehicle IDs, so delete events and audits for deleted records exist in the SQL audit table but are not shown in owner-scoped reports.
- This is a **local educational project**, not hardened for public internet deployment. Before production, add CSRF protection, rate limiting, stronger validation and a production WSGI server.
- User registration creates owner accounts; the reserved `admin` enum role is not used by the interface.

## Files
```
AutoCare_Project/
  app.py                  Flask routes and database queries
  requirements.txt        Python dependencies
  .env.example            Configuration template
  sql/schema.sql          MySQL schema, triggers, view, procedure
  sql/create_app_user.sql Least-privilege local MySQL account
  sql/demo_queries.sql    DBMS viva/demo queries
  templates/              Jinja2 HTML pages
  static/css/style.css    Responsive interface
  static/js/main.js       Dashboard graph and search controls
  docs/PROJECT_REPORT.md  Academic report outline and ER notation
```
