# backend/main.py
import os
import sqlite3
import requests
import random
import string
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ------------------------- التكوين -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU")  # اتركه فارغاً حالياً (وضع تجريبي)
CRYPTOBOT_API = "https://pay.crypt.bot/api"

# البكسلات المجانية (أول بكسل فقط)
FREE_PIXELS = {(0, 0)}

app = FastAPI()

# ✅ حل مشكلة CORS (الأهم)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------- قاعدة البيانات -------------------------
DB_PATH = "/tmp/pixels.db" if os.environ.get("RAILWAY") else "pixels.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pixels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        owner TEXT NOT NULL,
        url TEXT NOT NULL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        owner TEXT NOT NULL,
        url TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# ------------------------- النماذج -------------------------
class PixelPurchase(BaseModel):
    x: int
    y: int
    owner: str
    url: str

# ------------------------- دوال مساعدة -------------------------
def generate_demo_invoice():
    """إنشاء فاتورة تجريبية (بدون توكن حقيقي)"""
    demo_id = f"DEMO_{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
    demo_url = f"https://t.me/CryptoBot?start={demo_id}"
    return demo_id, demo_url

def create_crypto_invoice(amount: float, description: str):
    """إنشاء فاتورة حقيقية (إذا كان هناك توكن) أو تجريبية"""
    if not BOT_TOKEN:
        # وضع تجريبي
        return generate_demo_invoice()
    
    try:
        response = requests.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers={"Crypto-Pay-API-Token": BOT_TOKEN},
            json={"asset": "USDT", "amount": str(amount), "description": description},
            timeout=30
        )
        data = response.json()
        if data.get("ok"):
            return data["result"]["invoice_id"], data["result"]["pay_url"]
        return generate_demo_invoice()
    except:
        return generate_demo_invoice()

def check_invoice_status(invoice_id: str) -> str:
    """التحقق من حالة الفاتورة"""
    if invoice_id.startswith("DEMO_"):
        # الفواتير التجريبية تعتبر "مدفوعة" بعد 3 ثوانٍ (للتجربة)
        return "paid"
    
    if not BOT_TOKEN:
        return "pending"
    
    try:
        response = requests.get(
            f"{CRYPTOBOT_API}/getInvoices",
            headers={"Crypto-Pay-API-Token": BOT_TOKEN},
            params={"invoice_ids": invoice_id},
            timeout=30
        )
        data = response.json()
        if data.get("ok") and data["result"]["items"]:
            return data["result"]["items"][0]["status"]
        return "pending"
    except:
        return "pending"

def get_all_pixels():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT x, y, owner, url FROM pixels")
    pixels = [{"x": row[0], "y": row[1], "owner": row[2], "url": row[3]} for row in c.fetchall()]
    conn.close()
    return pixels

def save_pixel(x, y, owner, url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
    conn.commit()
    conn.close()

def save_invoice(invoice_id, x, y, owner, url, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO invoices (invoice_id, x, y, owner, url, amount, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (invoice_id, x, y, owner, url, amount, "pending"))
    conn.commit()
    conn.close()

def update_invoice_status(invoice_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE invoices SET status = ? WHERE invoice_id = ?", (status, invoice_id))
    conn.commit()
    conn.close()

def get_pending_invoice(invoice_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT x, y, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
    result = c.fetchone()
    conn.close()
    return result

# ------------------------- واجهات API -------------------------
@app.get("/")
def root():
    return {"message": "Pixel Wall API is running", "status": "active"}

@app.get("/pixels")
def get_pixels():
    return {"pixels": get_all_pixels()}

@app.post("/create-invoice")
def create_invoice(purchase: PixelPurchase):
    # التحقق من أن البكسل غير مباع
    existing_pixels = get_all_pixels()
    for p in existing_pixels:
        if p["x"] == purchase.x and p["y"] == purchase.y:
            raise HTTPException(status_code=400, detail="Pixel already sold")
    
    # التحقق إذا كان البكسل مجانياً
    if (purchase.x, purchase.y) in FREE_PIXELS:
        save_pixel(purchase.x, purchase.y, purchase.owner, purchase.url)
        return {"invoice_id": "free", "pay_url": None, "amount": 0, "free": True}
    
    # إنشاء فاتورة
    amount = 1.0
    invoice_id, pay_url = create_crypto_invoice(amount, f"Pixel ({purchase.x},{purchase.y})")
    
    if not invoice_id:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    save_invoice(invoice_id, purchase.x, purchase.y, purchase.owner, purchase.url, amount)
    
    return {"invoice_id": invoice_id, "pay_url": pay_url, "amount": amount, "free": False}

@app.get("/check-invoice/{invoice_id}")
def check_invoice(invoice_id: str):
    status = check_invoice_status(invoice_id)
    
    if status == "paid":
        pending = get_pending_invoice(invoice_id)
        if pending:
            x, y, owner, url = pending
            save_pixel(x, y, owner, url)
            update_invoice_status(invoice_id, "paid")
    
    return {"status": status, "invoice_id": invoice_id}

@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
        if body.get("event") == "invoice_paid":
            invoice_id = body.get("data", {}).get("invoice_id")
            pending = get_pending_invoice(invoice_id)
            if pending:
                x, y, owner, url = pending
                save_pixel(x, y, owner, url)
                update_invoice_status(invoice_id, "paid")
        return {"status": "ok"}
    except:
        return {"status": "error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
