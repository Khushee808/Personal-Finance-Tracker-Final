"""Create or reset the project's admin account from backend/.env.
Run with: python create_admin.py
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

load_dotenv()
email = os.getenv('ADMIN_EMAIL', '').strip().lower()
password = os.getenv('ADMIN_PASSWORD', '')
if not email or len(password) < 12:
    raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters) in backend/.env first.')
client = MongoClient(os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017/'), serverSelectionTimeoutMS=5000)
db = client[os.getenv('MONGO_DB', 'personal_finance_tracker')]
db.users.update_one({'email': email}, {'$set': {'name': 'Administrator', 'email': email, 'password': generate_password_hash(password), 'role': 'admin'}, '$setOnInsert': {'created_at': datetime.utcnow()}}, upsert=True)
print('Admin account is ready for:', email)
client.close()
