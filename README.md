# FinPilot — Advanced Personal Finance Tracker

A React + Vite frontend, Python Flask REST API, and MongoDB database project. Existing finance workflows are retained and expanded with budget tracking, analytics, exports, a transaction-aware finance assistant, and an admin panel.

## Features
- Register, login, JWT authentication and per-account transaction privacy
- Dashboard totals, quick add transaction and recent activity
- Income and expense records, categories, search/filter, delete, recurring flag
- Monthly budget, category budgets, savings goal and budget warnings at 80% / 100%
- Monthly analytics and expense-category breakdown
- Finance Assistant answers questions using the signed-in user's actual transaction data (rule-based; not a generative AI model)
- Monthly/filtered reports, CSV export and browser Print / Save as PDF
- JSON backup and restore; dark mode
- Admin overview, aggregate app stats, user/role management
- Password hashing, JWT auth, backend authorization for admin routes

## Requirements
- Python 3.10+ (Python 3.11 recommended)
- Node.js LTS and npm
- MongoDB Community Server running locally OR MongoDB Atlas URI
- Visual Studio Code

## Run in VS Code (Windows)
1. Extract this ZIP and open the extracted `Personal_Finance_Tracker_Advanced_Agent` folder in VS Code.
2. Start MongoDB locally, or create a MongoDB Atlas database and use its connection string.
3. Open Terminal → New Terminal and run:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

4. Open `backend/.env`. Set `MONGO_URI` to your working MongoDB URI. Change `JWT_SECRET` to a long random private value. For local MongoDB, the default URI is okay only if MongoDB Community Server is installed and running.
5. Create an admin account (recommended for demo): in `backend/.env`, set `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` (at least 12 characters), then run:

```powershell
.venv\Scripts\python.exe create_admin.py
```

6. Start the backend in the same terminal:

```powershell
.venv\Scripts\python.exe app.py
```

Backend health check: `http://127.0.0.1:5000/api/health`

7. Open a second VS Code terminal:

```powershell
cd frontend
npm install
npm run dev
```

8. Open the Vite URL printed in the terminal, normally `http://localhost:5173`.

## Login
- Normal user: use **Create an account** in the application.
- Admin: use the exact email and password configured in `backend/.env` and provisioned with `create_admin.py`.
- Do not upload `.env` or share database passwords. `.env` is intended to remain local and is excluded by `.gitignore`.

## API routes
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me`
- `GET/POST /api/transactions`, `DELETE /api/transactions/<id>`
- `GET/PUT /api/settings`, `GET /api/backup`, `POST /api/backup/restore`
- `GET /api/analytics`, `GET /api/reports/csv`, `POST /api/agent/chat`
- Admin only: `GET /api/admin/overview`, `GET /api/admin/users`, `PATCH /api/admin/users/<id>/role`, `DELETE /api/admin/users/<id>`

## Important notes
- The Finance Assistant is a **rule-based agent** that reads the current signed-in user's transaction totals and answers common finance questions. It does not call a third-party AI model and does not provide investment advice.
- The recurring field labels a transaction as recurring; it does not automatically create future transactions or send scheduled notifications yet.
- Admin statistics are aggregated; the admin UI does not expose users' individual transaction lists. Only trusted admins should be provisioned.
- For public hosting, configure strong environment variables, a restricted CORS origin, HTTPS, and MongoDB Atlas network access. Never use development secrets in production.
