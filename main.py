import os
import sqlite3
import requests
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# التوكن الخاص بك
API_TOKEN = "567216:AAUeBN5UmkXwJOcxI8m0FCpxc42457YEyvU"
CRYPTO_BOT_API = "https://pay.crypt.bot/api/"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# تعديل مسار قاعدة البيانات ليكون متوافقاً مع Render
DB_PATH = "/opt/render/project/src/database.db" if os.path.exists("/opt/render/project/src/") else "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS wall 
                      (pixel_id TEXT PRIMARY KEY, url TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.get("/")
async def root():
    return {"message": "Server is running!"}

@app.post("/create-order")
async def create_order(pixel_id: str = Form(...), link: str = Form(...)):
    headers = {"Crypto-Pay-API-Token": API_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": "1.0",
        "description": f"Pixel {pixel_id}",
        "payload": f"{pixel_id}|{link}" 
    }
    r = requests.post(f"{CRYPTO_BOT_API}createInvoice", json=payload, headers=headers)
    return r.json()

@app.get("/get-pixels")
async def get_pixels():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT pixel_id, url FROM wall WHERE status='paid'")
    data = cursor.fetchall()
    conn.close()
    return [{"id": d[0], "url": d[1]} for d in data]
