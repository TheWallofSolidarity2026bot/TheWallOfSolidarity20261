# backend/main.py
"""
╔══════════════════════════════════════════════════════════════════════╗
║                    PIXEL WALL - CRYPTO PAYMENT GATEWAY               ║
║                    FastAPI Backend + CryptoBot Integration           ║
║                           @q_U_G14 | MAXLYTH                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sqlite3
import json
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ------------------------- التكوين -------------------------
# ✅ ضع توكن البوت الخاص بك هنا (من @CryptoBot)
BOT_TOKEN = ""  # اتركه فارغاً حالياً، أو ضع التوكن إذا كان لديك
CHAT_ID = ""    # اتركه فارغاً
CRYPTOBOT_API = "https://pay.crypt.bot/api"

# توكن المحفظة
WALLET_TOKEN = "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU"

# البكسلات المجانية (أول بكسل فقط)
FREE_PIXELS = {(0, 0)}

app = FastAPI()

# ✅✅✅ حل مشكلة CORS (الأهم) ✅✅✅
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # يسمح لجميع المواقع (GitHub Pages, إلخ)
    allow_credentials=True,
    allow_methods=["*"],  # يسمح بجميع الطرق (GET, POST, إلخ)
    allow_headers=["*"],  # يسمح بجميع الرؤوس
)

# ------------------------- قاعدة البيانات -------------------------
DB_PATH = "/tmp/pixels.db" if os.environ.get("RAILWAY") else "pixels.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
    print("✅ Database initialized at", DB_PATH)

init_db()

# ------------------------- النماذج -------------------------
class PixelPurchase(BaseModel):
    x: int
    y: int
    owner: str
    url: str

# ------------------------- دوال مساعدة -------------------------
def create_crypto_invoice(amount: float, currency: str = "USDT", description: str = "Pixel Purchase"):
    """إنشاء فاتورة عبر CryptoBot API"""
    if not BOT_TOKEN:
        # ✅ وضع تجريبي (للتجربة بدون دفع حقيقي)
        return f"test_{description.replace(' ', '_')}", f"https://t.me/CryptoBot?start=test_{description.replace(' ', '_')}"
    
    try:
        url = f"{CRYPTOBOT_API}/createInvoice"
        headers = {"Crypto-Pay-API-Token": BOT_TOKEN}
        payload = {
            "asset": currency,
            "amount": str(amount),
            "description": description,
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/YourBot"
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        if data.get("ok"):
            return data["result"]["invoice_id"], data["result"]["pay_url"]
        return None, None
    except Exception as e:
        print(f"Error creating invoice: {e}")
        return None, None

def check_invoice_status(invoice_id: str) -> str:
    """التحقق من حالة الفاتورة"""
    if not BOT_TOKEN or invoice_id.startswith("test_"):
        return "paid"  # وضع تجريبي
    
    try:
        url = f"{CRYPTOBOT_API}/getInvoices"
        headers = {"Crypto-Pay-API-Token": BOT_TOKEN}
        response = requests.get(url, headers=headers, params={"invoice_ids": invoice_id}, timeout=30)
        data = response.json()
        if data.get("ok") and data["result"]["items"]:
            return data["result"]["items"][0]["status"]
        return "pending"
    except:
        return "pending"

def get_all_pixels():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, owner, url FROM pixels")
    pixels = [{"x": row[0], "y": row[1], "owner": row[2], "url": row[3]} for row in cursor.fetchall()]
    conn.close()
    return pixels

def save_pixel(x, y, owner, url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
    conn.commit()
    conn.close()

# ------------------------- واجهات API -------------------------
@app.get("/")
def root():
    return {"message": "Pixel Wall API is running", "status": "active"}

@app.get("/pixels")
def get_pixels():
    """جلب جميع البكسلات المباعة"""
    return {"pixels": get_all_pixels()}

@app.post("/create-invoice")
def create_invoice(purchase: PixelPurchase):
    """إنشاء فاتورة دفع لبكسل معين"""
    # التحقق من أن البكسل غير مباع
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pixels WHERE x = ? AND y = ?", (purchase.x, purchase.y))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        raise HTTPException(status_code=400, detail="Pixel already sold")
    
    # ✅ التحقق إذا كان البكسل مجانياً (أول بكسل)
    is_free = (purchase.x, purchase.y) in FREE_PIXELS
    
    if is_free:
        save_pixel(purchase.x, purchase.y, purchase.owner, purchase.url)
        return {"invoice_id": "free_pixel", "pay_url": None, "amount": 0, "free": True}
    
    # ✅ البكسلات المدفوعة (1 دولار)
    price = 1.0
    invoice_id, pay_url = create_crypto_invoice(price, "USDT", f"Pixel ({purchase.x},{purchase.y})")
    
    if not invoice_id:
        # ✅ في حال فشل إنشاء الفاتورة، نرجع رد خطأ واضح
        raise HTTPException(status_code=500, detail="Failed to create invoice. Check BOT_TOKEN.")
    
    # حفظ معلومات الفاتورة
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (invoice_id, x, y, owner, url, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (invoice_id, purchase.x, purchase.y, purchase.owner, purchase.url, price, "USDT", "pending")
    )
    conn.commit()
    conn.close()
    
    return {"invoice_id": invoice_id, "pay_url": pay_url, "amount": price, "free": False}

@app.post("/webhook")
async def crypto_webhook(request: Request):
    """Webhook من CryptoBot لتأكيد الدفع"""
    try:
        body = await request.json()
        if body.get("event") == "invoice_paid":
            invoice_id = body.get("data", {}).get("invoice_id")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT x, y, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
            invoice = cursor.fetchone()
            if invoice:
                x, y, owner, url = invoice
                cursor.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
                cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
                conn.commit()
            conn.close()
        return {"status": "ok"}
    except:
        return {"status": "error"}

@app.get("/check-invoice/{invoice_id}")
def check_invoice(invoice_id: str):
    """التحقق من حالة فاتورة"""
    status = check_invoice_status(invoice_id)
    if status == "paid":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT x, y, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
        invoice = cursor.fetchone()
        if invoice:
            x, y, owner, url = invoice
            cursor.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
            cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
            conn.commit()
        conn.close()
    return {"status": status, "invoice_id": invoice_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
