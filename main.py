# backend/main.py
import os
import sqlite3
import json
import requests
import base64
import random
import string
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

# ===================== التكوين =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU")
CRYPTOBOT_API = "https://pay.crypt.bot/api"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== قاعدة البيانات =====================
DB_PATH = "/tmp/advertising.db" if os.environ.get("RAILWAY") else "advertising.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # جدول المناطق المباعة
    c.execute('''CREATE TABLE IF NOT EXISTS sold_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        image_url TEXT NOT NULL,
        link_url TEXT NOT NULL,
        owner TEXT NOT NULL,
        amount REAL NOT NULL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # جدول الفواتير
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        image_data TEXT NOT NULL,
        link_url TEXT NOT NULL,
        owner TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# ===================== النماذج =====================
class AreaPurchase(BaseModel):
    x: int
    y: int
    width: int
    height: int
    link_url: str
    owner: str

# ===================== دوال مساعدة =====================
def generate_demo_invoice():
    demo_id = f"DEMO_{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
    demo_url = f"https://t.me/CryptoBot?start={demo_id}"
    return demo_id, demo_url

def create_crypto_invoice(amount: float, description: str):
    if not BOT_TOKEN:
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
    if invoice_id.startswith("DEMO_"):
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

def is_area_available(x, y, width, height):
    """التحقق من أن المنطقة المحددة غير مباعة"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT x, y, width, height FROM sold_areas")
    sold = c.fetchall()
    conn.close()
    
    for sx, sy, sw, sh in sold:
        if not (x + width <= sx or sx + sw <= x or y + height <= sy or sy + sh <= y):
            return False
    return True

def save_area(x, y, width, height, image_url, link_url, owner, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sold_areas (x, y, width, height, image_url, link_url, owner, amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (x, y, width, height, image_url, link_url, owner, amount))
    conn.commit()
    conn.close()

def get_all_areas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT x, y, width, height, image_url, link_url, owner, amount FROM sold_areas")
    areas = [{"x": row[0], "y": row[1], "width": row[2], "height": row[3], "image_url": row[4], "link_url": row[5], "owner": row[6], "amount": row[7]} for row in c.fetchall()]
    conn.close()
    return areas

# ===================== واجهات API =====================
@app.get("/")
def root():
    return {"message": "Advertising Canvas API", "status": "active"}

@app.get("/areas")
def get_areas():
    return {"areas": get_all_areas()}

@app.post("/create-invoice")
async def create_invoice(
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    link_url: str = Form(...),
    owner: str = Form(...),
    image: UploadFile = File(...)
):
    # التحقق من أن المنطقة غير مباعة
    if not is_area_available(x, y, width, height):
        raise HTTPException(status_code=400, detail="Area already sold")
    
    # حساب السعر
    pixels_count = width * height
    amount = pixels_count * 1.0
    
    # قراءة الصورة وتحويلها إلى base64 للتخزين المؤقت
    image_data = await image.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    # إنشاء فاتورة
    invoice_id, pay_url = create_crypto_invoice(amount, f"Advertising Area ({width}x{height}) - {pixels_count} pixels")
    
    if not invoice_id:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    # حفظ معلومات الفاتورة
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO invoices (invoice_id, x, y, width, height, image_data, link_url, owner, amount, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (invoice_id, x, y, width, height, image_base64, link_url, owner, amount, "pending"))
    conn.commit()
    conn.close()
    
    return {"invoice_id": invoice_id, "pay_url": pay_url, "amount": amount, "pixels": pixels_count}

@app.get("/check-invoice/{invoice_id}")
def check_invoice(invoice_id: str):
    status = check_invoice_status(invoice_id)
    
    if status == "paid":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT x, y, width, height, image_data, link_url, owner, amount FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
        invoice = c.fetchone()
        if invoice:
            x, y, width, height, image_data, link_url, owner, amount = invoice
            # حفظ الصورة كملف
            image_bytes = base64.b64decode(image_data)
            image_filename = f"area_{x}_{y}_{width}_{height}_{invoice_id}.png"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            image_url = f"/uploads/{image_filename}"
            
            c.execute("INSERT INTO sold_areas (x, y, width, height, image_url, link_url, owner, amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (x, y, width, height, image_url, link_url, owner, amount))
            c.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
            conn.commit()
        conn.close()
    
    return {"status": status, "invoice_id": invoice_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
