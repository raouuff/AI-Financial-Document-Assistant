"""Central configuration, loaded from environment / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "auto").strip().lower()  # auto|true|false
DB_PATH = Path(os.getenv("DB_PATH", "data/expenses.db"))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
SAMPLE_DIR = BASE_DIR / "sample_data"
EXPORT_DIR = BASE_DIR / "exports"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Predefined expense categories (from the task spec)
CATEGORIES = [
    "personnel",
    "travel",
    "equipment",
    "software",
    "events",
    "operational",
]

# Common ISO 4217 codes accepted without a flag
COMMON_CURRENCIES = {
    "USD", "EUR", "GBP", "EGP", "AED", "SAR", "JPY", "CHF", "CAD",
    "AUD", "INR", "TRY", "KWD", "QAR",
}

ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/heic": ".heic",
}

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def demo_active() -> bool:
    """Whether demo mode should be used."""
    if DEMO_MODE == "true":
        return True
    if DEMO_MODE == "false":
        return False
    # auto: demo only when no real key is configured
    return not GEMINI_API_KEY


for _d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
