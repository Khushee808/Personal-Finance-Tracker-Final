# Personal Finance Tracker - Flask + MongoDB Backend

This version keeps the existing React frontend and replaces the Node/Express backend with **Python Flask**.

## Backend
- Python 3.11+
- Flask
- Flask-CORS
- PyMongo
- MongoDB
- JWT authentication
- Werkzeug password hashing

## Run in Visual Studio Code

### 1. Install Python
Install Python 3.11 or newer and select **Add Python to PATH** during installation.

### 2. Install MongoDB
Install MongoDB Community Server and make sure the MongoDB service is running.

MongoDB default URL:
`mongodb://127.0.0.1:27017/`

### 3. Open the project
Open the extracted **Personal_Finance_Tracker** folder in Visual Studio Code.

### 4. Backend terminal
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

You should see Flask running on `http://127.0.0.1:5000`.

Test:
`http://127.0.0.1:5000/api/health`

### 5. Frontend terminal
Open a second VS Code terminal:
```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

## Database
Database name: `personal_finance_tracker`

Collections created automatically:
- `users`
- `transactions`
- `settings`

## Features
Login/Register/Logout, Dashboard, Income/Expense, Categories, Recurring Transaction option, Monthly Budget, Category Budget, Savings Goal, Charts, Smart Insights, Transaction History, Search/Filter, Delete, Reports, CSV, Print/Save PDF, Dark Mode, Backup/Restore.

## Important
The frontend calls `http://localhost:5000/api`. If you change the Flask port, update the `API` constant in `frontend/src/main.jsx`.
