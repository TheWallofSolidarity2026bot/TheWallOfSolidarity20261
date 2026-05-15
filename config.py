
# backend/config.py
import os

# رابط خادم FastAPI (لـ webhook)
SERVER_URL = os.environ.get("SERVER_URL", "https://thewallofsolidarity20261-production.up.railway.app")

# سعر البكسل بالدولار
PIXEL_PRICE = float(os.environ.get("PIXEL_PRICE", "5"))
