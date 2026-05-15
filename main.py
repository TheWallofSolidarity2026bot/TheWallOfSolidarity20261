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
import hmac
import hashlib
import requests
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# ------------------------- التكوين -------------------------
# توكن بوت التليجرام (ضع التوكن هنا مباشرة)
BOT_TOKEN = ""  # اتركه فارغاً أو ضع التوكن إذا احتجت
CHAT_ID = ""    # اتركه فارغاً أو ضع المعرف إذا احتجت
CRYPTOBOT_API = "https://pay.crypt.bot/api"

# توكن المحفظة
WALLET_TOKEN = "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU"

app = FastAPI()

# CORS لتسمح للواجهة الأمامية بالتواصل مع الخادم
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------- قاعدة البيانات -------------------------
def init_db():
    conn = sqlite3.connect('pixels.db')
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

init_db()

# ------------------------- النماذج -------------------------
class PixelPurchase(BaseModel):
    x: int
    y: int
    owner: str
    url: str

class InvoiceStatus(BaseModel):
    invoice_id: str
    status: str

# ------------------------- دوال مساعدة -------------------------
def generate_signature(data: dict, secret: str) -> str:
    """توليد توقيع للتحقق من صحة الطلب"""
    sorted_data = sorted(data.items())
    message = json.dumps(sorted_data, separators=(',', ':'))
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def create_crypto_invoice(amount: float, currency: str = "USDT", description: str = "Pixel Purchase"):
    """إنشاء فاتورة عبر CryptoBot API"""
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
    try:
        url = f"{CRYPTOBOT_API}/getInvoices"
        headers = {"Crypto-Pay-API-Token": BOT_TOKEN}
        payload = {"invoice_ids": invoice_id}
        response = requests.get(url, headers=headers, params=payload, timeout=30)
        data = response.json()
        if data.get("ok") and data["result"]["items"]:
            return data["result"]["items"][0]["status"]
        return "pending"
    except:
        return "pending"

def save_pixel(x: int, y: int, owner: str, url: str):
    """حفظ البكسل في قاعدة البيانات"""
    conn = sqlite3.connect('pixels.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)",
        (x, y, owner, url)
    )
    conn.commit()
    conn.close()

def get_all_pixels():
    """جلب جميع البكسلات المباعة"""
    conn = sqlite3.connect('pixels.db')
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, owner, url FROM pixels")
    pixels = [{"x": row[0], "y": row[1], "owner": row[2], "url": row[3]} for row in cursor.fetchall()]
    conn.close()
    return pixels

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
    conn = sqlite3.connect('pixels.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pixels WHERE x = ? AND y = ?", (purchase.x, purchase.y))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        raise HTTPException(status_code=400, detail="Pixel already sold")
    
    # تحديد السعر حسب الموقع (مثال: البكسلات في المنتصف أغلى)
    price = 5.0  # سعر ثابت أو يمكن جعله متغيراً حسب الموقع
    
    # إنشاء فاتورة عبر CryptoBot
    invoice_id, pay_url = create_crypto_invoice(price, "USDT", f"Pixel ({purchase.x},{purchase.y})")
    
    if not invoice_id:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    # حفظ معلومات الفاتورة
    conn = sqlite3.connect('pixels.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (invoice_id, x, y, owner, url, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (invoice_id, purchase.x, purchase.y, purchase.owner, purchase.url, price, "USDT", "pending")
    )
    conn.commit()
    conn.close()
    
    # إرسال إشعار إلى تليجرام (إذا كان هناك توكن)
    if BOT_TOKEN and CHAT_ID:
        try:
            msg = f"🟢 <b>New Invoice Created</b>\n━━━━━━━━━━━━━━━━━━━\n📍 Pixel: ({purchase.x}, {purchase.y})\n👤 Owner: {purchase.owner}\n🔗 URL: {purchase.url}\n💰 Amount: {price} USDT\n🆔 Invoice: {invoice_id}"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except:
            pass
    
    return {"invoice_id": invoice_id, "pay_url": pay_url, "amount": price}

@app.post("/webhook")
async def crypto_webhook(request: Request):
    """Webhook من CryptoBot لتأكيد الدفع"""
    try:
        body = await request.json()
        
        if body.get("event") == "invoice_paid":
            invoice_id = body.get("data", {}).get("invoice_id")
            
            # تحديث حالة الفاتورة
            conn = sqlite3.connect('pixels.db')
            cursor = conn.cursor()
            cursor.execute("SELECT x, y, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
            invoice = cursor.fetchone()
            
            if invoice:
                x, y, owner, url = invoice
                cursor.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
                cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
                conn.commit()
                
                # إرسال إشعار نجاح إلى تليجرام (إذا كان هناك توكن)
                if BOT_TOKEN and CHAT_ID:
                    msg = f"✅ <b>NEW PIXEL SOLD!</b>\n━━━━━━━━━━━━━━━━━━━\n📍 Pixel: ({x}, {y})\n👤 Owner: {owner}\n🔗 URL: {url}\n🆔 Invoice: {invoice_id}"
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
            conn.close()
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}

@app.get("/check-invoice/{invoice_id}")
def check_invoice(invoice_id: str):
    """التحقق من حالة فاتورة"""
    status = check_invoice_status(invoice_id)
    
    if status == "paid":
        # تحديث حالة الفاتورة في قاعدة البيانات المحلية
        conn = sqlite3.connect('pixels.db')
        cursor = conn.cursor()
        cursor.execute("SELECT x, y, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
        invoice = cursor.fetchone()
        
        if invoice:
            x, y, owner, url = invoice
            cursor.execute("INSERT INTO pixels (x, y, owner, url) VALUES (?, ?, ?, ?)", (x, y, owner, url))
            cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
            conn.commit()
            
            # إرسال إشعار (إذا كان هناك توكن)
            if BOT_TOKEN and CHAT_ID:
                msg = f"✅ <b>PIXEL SOLD!</b>\n━━━━━━━━━━━━━━━━━━━\n📍 Pixel: ({x}, {y})\n👤 Owner: {owner}\n🔗 URL: {url}"
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                              json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        conn.close()
    
    return {"status": status, "invoice_id": invoice_id}
