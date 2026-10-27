import os, csv, io, re
from functools import wraps
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request, g, Response
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*")}})
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
DB_NAME = os.getenv("MONGO_DB", "personal_finance_tracker")
JWT_SECRET = os.getenv("JWT_SECRET", "change_this_secret_key")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
users, transactions, settings = db.users, db.transactions, db.settings
users.create_index("email", unique=True)
transactions.create_index([("user_id", 1), ("date", DESCENDING)])


def oid(value):
    return ObjectId(value) if ObjectId.is_valid(str(value)) else None

def serialize(doc):
    if not doc: return None
    out = dict(doc)
    for key in ("_id", "user_id"):
        if key in out: out[key] = str(out[key])
    out.pop("password", None)
    return out

def token_for(user):
    payload = {"user_id": str(user["_id"]), "role": user.get("role", "user"), "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "): return jsonify(message="Authentication required"), 401
        try:
            payload = jwt.decode(header.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
            user_id = oid(payload.get("user_id"))
            user = users.find_one({"_id": user_id}) if user_id else None
            if not user: raise ValueError("User not found")
            g.user_id, g.current_user = user_id, user
        except Exception:
            return jsonify(message="Invalid or expired token"), 401
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    @auth_required
    def wrapper(*args, **kwargs):
        if g.current_user.get("role") != "admin": return jsonify(message="Admin access required"), 403
        return fn(*args, **kwargs)
    return wrapper

def tx_summary(user_id):
    tx = list(transactions.find({"user_id": user_id}))
    income = sum(float(t.get("amount", 0)) for t in tx if t.get("type") == "income")
    expense = sum(float(t.get("amount", 0)) for t in tx if t.get("type") == "expense")
    now = datetime.now().strftime("%Y-%m")
    month_expense = sum(float(t.get("amount", 0)) for t in tx if t.get("type") == "expense" and str(t.get("date", "")).startswith(now))
    categories = {}
    for t in tx:
        if t.get("type") == "expense": categories[t.get("category", "Other")] = categories.get(t.get("category", "Other"), 0) + float(t.get("amount", 0))
    return tx, {"totalIncome": round(income, 2), "totalExpense": round(expense, 2), "balance": round(income-expense, 2), "monthExpense": round(month_expense, 2), "categories": categories, "transactionCount": len(tx)}

@app.get("/")
def home(): return jsonify(message="Personal Finance Tracker API is running")
@app.get("/api/health")
def health():
    try: client.admin.command("ping"); return jsonify(status="ok", database="connected")
    except Exception: return jsonify(status="error", database="not connected"), 503

@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name, email, password = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower(), data.get("password", "")
    if not name or not email or not password: return jsonify(message="Name, email and password are required"), 400
    if len(password) < 8: return jsonify(message="Password must be at least 8 characters"), 400
    if users.find_one({"email": email}): return jsonify(message="Email already registered"), 409
    user = {"name": name, "email": email, "password": generate_password_hash(password), "role": "user", "created_at": datetime.utcnow()}
    result = users.insert_one(user); user["_id"] = result.inserted_id
    return jsonify(token=token_for(user), user={"id": str(result.inserted_id), "name": name, "email": email, "role": "user"}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}; email = str(data.get("email", "")).strip().lower(); password = data.get("password", "")
    user = users.find_one({"email": email})
    if not user or not check_password_hash(user.get("password", ""), password): return jsonify(message="Invalid email or password"), 401
    return jsonify(token=token_for(user), user={"id": str(user["_id"]), "name": user.get("name", "User"), "email": user["email"], "role": user.get("role", "user")})

@app.get("/api/me")
@auth_required
def me(): return jsonify(user={"id": str(g.current_user["_id"]), "name": g.current_user.get("name", "User"), "email": g.current_user["email"], "role": g.current_user.get("role", "user")})

@app.get("/api/transactions")
@auth_required
def get_transactions(): return jsonify([serialize(x) for x in transactions.find({"user_id": g.user_id}).sort("date", DESCENDING)])
@app.post("/api/transactions")
@auth_required
def add_transaction():
    data = request.get_json(silent=True) or {}; required = ["date", "description", "category", "amount", "type"]
    if any(data.get(k) in (None, "") for k in required): return jsonify(message="All transaction fields are required"), 400
    try:
        amount = float(data["amount"])
        if amount <= 0: raise ValueError
    except (TypeError, ValueError): return jsonify(message="Amount must be greater than zero"), 400
    if data["type"] not in ("income", "expense"): return jsonify(message="Type must be income or expense"), 400
    doc = {"user_id": g.user_id, "date": str(data["date"]), "description": str(data["description"])[:200], "category": str(data["category"])[:60], "amount": amount, "type": data["type"], "recurring": bool(data.get("recurring", False)), "created_at": datetime.utcnow()}
    result = transactions.insert_one(doc)
    return jsonify(serialize(transactions.find_one({"_id": result.inserted_id}))), 201
@app.delete("/api/transactions/<transaction_id>")
@auth_required
def delete_transaction(transaction_id):
    tx_id = oid(transaction_id)
    if not tx_id: return jsonify(message="Invalid transaction id"), 400
    result = transactions.delete_one({"_id": tx_id, "user_id": g.user_id})
    if not result.deleted_count: return jsonify(message="Transaction not found"), 404
    return jsonify(message="Transaction deleted")

@app.get("/api/settings")
@auth_required
def get_settings():
    doc = settings.find_one({"user_id": g.user_id}) or {"monthlyBudget": 0, "savingsGoal": 0, "darkMode": False, "categoryBudgets": {}}
    doc.pop("_id", None); doc.pop("user_id", None); return jsonify(settings=doc)
@app.put("/api/settings")
@auth_required
def update_settings():
    data = request.get_json(silent=True) or {}
    try: monthly = max(0, float(data.get("monthlyBudget", 0) or 0)); goal = max(0, float(data.get("savingsGoal", 0) or 0))
    except (TypeError, ValueError): return jsonify(message="Budget and goal must be numbers"), 400
    cats = data.get("categoryBudgets", {})
    if not isinstance(cats, dict): cats = {}
    allowed = {"monthlyBudget": monthly, "savingsGoal": goal, "darkMode": bool(data.get("darkMode", False)), "categoryBudgets": cats}
    settings.update_one({"user_id": g.user_id}, {"$set": allowed}, upsert=True); return jsonify(settings=allowed)
@app.get("/api/backup")
@auth_required
def backup():
    tx = [serialize(x) for x in transactions.find({"user_id": g.user_id})]
    st = settings.find_one({"user_id": g.user_id}) or {"monthlyBudget": 0, "savingsGoal": 0, "darkMode": False, "categoryBudgets": {}}
    st.pop("_id", None); st.pop("user_id", None); return jsonify(transactions=tx, settings=st)
@app.post("/api/backup/restore")
@auth_required
def restore():
    data = request.get_json(silent=True) or {}; txs = data.get("transactions", [])
    if not isinstance(txs, list): return jsonify(message="Invalid backup file"), 400
    clean = []
    for item in txs:
        try:
            amount = float(item["amount"])
            if amount <= 0 or item.get("type") not in ("income", "expense"): continue
            clean.append({"user_id": g.user_id, "date": str(item["date"]), "description": str(item["description"]), "category": str(item["category"]), "amount": amount, "type": item["type"], "recurring": bool(item.get("recurring", False)), "created_at": datetime.utcnow()})
        except (KeyError, TypeError, ValueError): continue
    transactions.delete_many({"user_id": g.user_id})
    if clean: transactions.insert_many(clean)
    st = data.get("settings", {}); settings.update_one({"user_id": g.user_id}, {"$set": {"monthlyBudget": float(st.get("monthlyBudget", 0) or 0), "savingsGoal": float(st.get("savingsGoal", 0) or 0), "darkMode": bool(st.get("darkMode", False)), "categoryBudgets": st.get("categoryBudgets", {})}}, upsert=True)
    return jsonify(message="Backup restored successfully")

# Advanced analytics and budgets
@app.get("/api/analytics")
@auth_required
def analytics():
    tx, summary = tx_summary(g.user_id)
    monthly = {}
    for t in tx:
        month = str(t.get("date", ""))[:7]
        if len(month) != 7: continue
        monthly.setdefault(month, {"month": month, "income": 0, "expense": 0})
        monthly[month][t["type"]] += float(t.get("amount", 0))
    for row in monthly.values(): row["savings"] = round(row["income"] - row["expense"], 2)
    st = settings.find_one({"user_id": g.user_id}) or {}
    budget = float(st.get("monthlyBudget", 0) or 0)
    status = "not-set" if budget <= 0 else "exceeded" if summary["monthExpense"] >= budget else "warning" if summary["monthExpense"] >= budget * .8 else "safe"
    return jsonify(summary=summary, monthly=sorted(monthly.values(), key=lambda x: x["month"], reverse=True), budget={"limit": budget, "spent": summary["monthExpense"], "remaining": max(0, round(budget-summary["monthExpense"],2)), "status": status})

@app.get("/api/reports/csv")
@auth_required
def export_csv():
    rows = transactions.find({"user_id": g.user_id}).sort("date", DESCENDING)
    out = io.StringIO(); writer = csv.writer(out); writer.writerow(["Date", "Type", "Category", "Description", "Amount", "Recurring"])
    for t in rows: writer.writerow([t.get("date", ""), t.get("type", ""), t.get("category", ""), t.get("description", ""), t.get("amount", 0), t.get("recurring", False)])
    return Response("\ufeff"+out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=personal-finance-report.csv"})

# Finance assistant: deterministic answers based on the signed-in user's real transactions.
@app.post("/api/agent/chat")
@auth_required
def finance_agent():
    body = request.get_json(silent=True) or {}; question = str(body.get("question", "")).strip().lower()
    if not question: return jsonify(message="Please enter a question"), 400
    tx, s = tx_summary(g.user_id); st = settings.find_one({"user_id": g.user_id}) or {}; budget = float(st.get("monthlyBudget", 0) or 0)
    if any(k in question for k in ["budget", "बजेट"]):
        if budget <= 0: reply = f"या महिन्याचा खर्च {s['monthExpense']:.2f} आहे. अजून monthly budget set केलेला नाही. Settings मध्ये budget सेट करा."
        else: reply = f"या महिन्याचा खर्च ₹{s['monthExpense']:.2f} आहे आणि budget ₹{budget:.2f} आहे. " + ("Budget ओलांडला आहे." if s["monthExpense"] >= budget else f"₹{budget-s['monthExpense']:.2f} budget शिल्लक आहे.")
    elif any(k in question for k in ["category", "where", "कुठे", "category-wise", "जास्त खर्च"]):
        top = sorted(s["categories"].items(), key=lambda x:x[1], reverse=True)
        reply = f"सर्वाधिक खर्चाची category {top[0][0]} आहे: ₹{top[0][1]:.2f}." if top else "अजून expense transactions नाहीत. आधी खर्चाची नोंद करा."
    elif any(k in question for k in ["income", "उत्पन्न"]): reply = f"तुमचे एकूण income ₹{s['totalIncome']:.2f} आहे."
    elif any(k in question for k in ["expense", "spent", "खर्च"]): reply = f"एकूण expenses ₹{s['totalExpense']:.2f} आहेत. या महिन्यात ₹{s['monthExpense']:.2f} खर्च झाला आहे."
    elif any(k in question for k in ["balance", "saving", "शिल्लक", "बचत"]): reply = f"तुमचा current balance (income minus expenses) ₹{s['balance']:.2f} आहे."
    elif any(k in question for k in ["summary", "report", "overview", "सारांश"]): reply = f"Summary: Income ₹{s['totalIncome']:.2f}, expenses ₹{s['totalExpense']:.2f}, balance ₹{s['balance']:.2f}, this month expenses ₹{s['monthExpense']:.2f}."
    else: reply = "मी income, expenses, balance, budget आणि highest spending category बद्दल उत्तर देऊ शकतो. उदाहरण: 'या महिन्यात माझा खर्च किती?'"
    return jsonify(reply=reply, source="your-account-transactions", assistant_type="rule-based-finance-agent")

# Admin-only APIs. Admin is created by the bootstrap script, not public registration.
@app.get("/api/admin/overview")
@admin_required
def admin_overview():
    total_users = users.count_documents({}); total_tx = transactions.count_documents({})
    pipeline = [{"$group": {"_id": "$type", "total": {"$sum": "$amount"}}}]
    totals = {r["_id"]: round(r["total"], 2) for r in transactions.aggregate(pipeline)}
    latest = [serialize(u) for u in users.find({}, {"password": 0}).sort("created_at", DESCENDING).limit(10)]
    return jsonify(totalUsers=total_users, totalTransactions=total_tx, totalIncome=totals.get("income", 0), totalExpenses=totals.get("expense", 0), recentUsers=latest)
@app.get("/api/admin/users")
@admin_required
def admin_users():
    return jsonify([serialize(u) for u in users.find({}, {"password": 0}).sort("created_at", DESCENDING).limit(500)])
@app.patch("/api/admin/users/<user_id>/role")
@admin_required
def admin_set_role(user_id):
    uid = oid(user_id); data = request.get_json(silent=True) or {}; role = data.get("role")
    if not uid or role not in ("admin", "user"): return jsonify(message="Invalid user or role"), 400
    if uid == g.user_id and role != "admin": return jsonify(message="You cannot remove your own admin role"), 400
    result = users.update_one({"_id": uid}, {"$set": {"role": role}})
    if not result.matched_count: return jsonify(message="User not found"), 404
    return jsonify(message="User role updated")
@app.delete("/api/admin/users/<user_id>")
@admin_required
def admin_delete_user(user_id):
    uid = oid(user_id)
    if not uid: return jsonify(message="Invalid user id"), 400
    if uid == g.user_id: return jsonify(message="You cannot delete your own account"), 400
    users.delete_one({"_id": uid}); transactions.delete_many({"user_id": uid}); settings.delete_many({"user_id": uid})
    return jsonify(message="User and associated data deleted")

if __name__ == "__main__":
    # Bootstrap a single admin only from private environment variables.
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower(); admin_password = os.getenv("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        users.update_one({"email": admin_email}, {"$set": {"name": "Administrator", "email": admin_email, "password": generate_password_hash(admin_password), "role": "admin"}, "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
