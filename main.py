import sqlite3
import requests
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# التوكن الخاص بك مفعل وجاهز
API_TOKEN = "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU"
CRYPTO_BOT_API = "https://pay.crypt.bot/api/"

app = FastAPI()

# حل مشكلة الاتصال بين الموقع والسيرفر (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد قاعدة البيانات تلقائياً
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS wall 
                      (pixel_id TEXT PRIMARY KEY, url TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.post("/create-order")
async def create_order(pixel_id: str = Form(...), link: str = Form(...)):
    # إنشاء فاتورة حقيقية
    headers = {"Crypto-Pay-API-Token": API_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": "1.0", # سعر البكسل 1 دولار
        "description": f"Pixel {pixel_id}",
        "payload": f"{pixel_id}|{link}" 
    }
    r = requests.post(f"{CRYPTO_BOT_API}createInvoice", json=payload, headers=headers)
    return r.json()

@app.get("/get-pixels")
async def get_pixels():
    # جلب البكسلات المحجوزة فقط للعرض
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT pixel_id, url FROM wall WHERE status='paid'")
    data = cursor.fetchall()
    conn.close()
    return [{"id": d[0], "url": d[1]} for d in data]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
