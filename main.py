# backend/main.py
import os
import sqlite3
import json
import requests
import random
import string
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# ------------------------- التكوين -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU")
CRYPTOBOT_API = "https://pay.crypt.bot/api"

# الألوان المتاحة (16 لوناً)
COLORS = {
    "red": "#e74c3c", "black": "#2c3e50", "white": "#ecf0f1", "green": "#2ecc71",
    "gold": "#f1c40f", "blue": "#3498db", "orange": "#e67e22", "purple": "#9b59b6",
    "cyan": "#1abc9c", "pink": "#fd79a8", "brown": "#8B4513", "navy": "#34495e",
    "lightyellow": "#ffeaa7", "lightgreen": "#55efc4", "lightblue": "#74b9ff", "gray": "#b2bec3"
}

app = FastAPI()

# CORS
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
    # جدول البكسلات المباعة (فقط هذه تُحفظ)
    c.execute('''CREATE TABLE IF NOT EXISTS sold_pixels (
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        color TEXT NOT NULL,
        owner TEXT NOT NULL,
        url TEXT NOT NULL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (x, y)
    )''')
    # جدول الفواتير
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        color TEXT NOT NULL,
        owner TEXT NOT NULL,
        url TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# ------------------------- WebSocket Manager -------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ------------------------- النماذج -------------------------
class PixelPurchase(BaseModel):
    x: int
    y: int
    color: str
    owner: str
    url: str

# ------------------------- دوال مساعدة -------------------------
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

def get_all_sold_pixels():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT x, y, color, owner, url FROM sold_pixels")
    pixels = [{"x": row[0], "y": row[1], "color": row[2], "owner": row[3], "url": row[4]} for row in c.fetchall()]
    conn.close()
    return pixels

def is_pixel_sold(x, y):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM sold_pixels WHERE x = ? AND y = ?", (x, y))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_sold_pixel(x, y, color, owner, url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sold_pixels (x, y, color, owner, url) VALUES (?, ?, ?, ?, ?)", (x, y, color, owner, url))
    conn.commit()
    conn.close()

# ------------------------- WebSocket Endpoint -------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ------------------------- واجهات API -------------------------
@app.get("/")
def root():
    return {"message": "Pixel Wall V2 - Collaborative Drawing", "status": "active"}

@app.get("/pixels")
def get_pixels():
    return {"pixels": get_all_sold_pixels()}

@app.post("/create-invoice")
def create_invoice(purchase: PixelPurchase):
    if is_pixel_sold(purchase.x, purchase.y):
        raise HTTPException(status_code=400, detail="Pixel already sold")
    
    # أول بكسل مجاني (0,0)
    if purchase.x == 0 and purchase.y == 0:
        save_sold_pixel(purchase.x, purchase.y, purchase.color, purchase.owner, purchase.url)
        # بث التحديث لجميع المستخدمين
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "new_pixel",
            "x": purchase.x,
            "y": purchase.y,
            "color": purchase.color,
            "owner": purchase.owner,
            "url": purchase.url
        }))
        return {"invoice_id": "free", "pay_url": None, "amount": 0, "free": True}
    
    amount = 1.0
    invoice_id, pay_url = create_crypto_invoice(amount, f"Pixel ({purchase.x},{purchase.y})")
    
    if not invoice_id:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO invoices (invoice_id, x, y, color, owner, url, amount, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (invoice_id, purchase.x, purchase.y, purchase.color, purchase.owner, purchase.url, amount, "pending"))
    conn.commit()
    conn.close()
    
    return {"invoice_id": invoice_id, "pay_url": pay_url, "amount": amount, "free": False}

@app.get("/check-invoice/{invoice_id}")
def check_invoice(invoice_id: str):
    status = check_invoice_status(invoice_id)
    
    if status == "paid":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT x, y, color, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
        invoice = c.fetchone()
        if invoice:
            x, y, color, owner, url = invoice
            c.execute("INSERT INTO sold_pixels (x, y, color, owner, url) VALUES (?, ?, ?, ?, ?)", (x, y, color, owner, url))
            c.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
            conn.commit()
            
            # بث التحديث لجميع المستخدمين
            import asyncio
            asyncio.create_task(manager.broadcast({
                "type": "new_pixel",
                "x": x,
                "y": y,
                "color": color,
                "owner": owner,
                "url": url
            }))
        conn.close()
    
    return {"status": status, "invoice_id": invoice_id}

@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
        if body.get("event") == "invoice_paid":
            invoice_id = body.get("data", {}).get("invoice_id")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT x, y, color, owner, url FROM invoices WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
            invoice = c.fetchone()
            if invoice:
                x, y, color, owner, url = invoice
                c.execute("INSERT INTO sold_pixels (x, y, color, owner, url) VALUES (?, ?, ?, ?, ?)", (x, y, color, owner, url))
                c.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
                conn.commit()
                
                # بث التحديث لجميع المستخدمين
                import asyncio
                asyncio.create_task(manager.broadcast({
                    "type": "new_pixel",
                    "x": x,
                    "y": y,
                    "color": color,
                    "owner": owner,
                    "url": url
                }))
            conn.close()
        return {"status": "ok"}
    except:
        return {"status": "error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
