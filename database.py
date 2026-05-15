
# backend/database.py
import sqlite3
from datetime import datetime

DB_NAME = "pixels.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جدول البكسلات المباعة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pixels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            owner TEXT NOT NULL,
            url TEXT NOT NULL,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول الفواتير
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            owner TEXT NOT NULL,
            url TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
