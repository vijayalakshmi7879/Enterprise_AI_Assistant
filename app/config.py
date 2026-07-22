import os
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(".").resolve()
UPLOAD_DIR = BASE_DIR / "uploaded_pdfs"
LOG_DIR = BASE_DIR / "logs"
VECTORDB_DIR = BASE_DIR / "vectordb"
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "enterprise_sales.db"

for d in (UPLOAD_DIR, LOG_DIR, VECTORDB_DIR, DB_DIR):
    d.mkdir(exist_ok=True)

class Config:
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    GEMINI_CANDIDATE_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
    ]

    SQL_MODEL_NAME = "llama-3.3-70b-versatile"
    EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

    MAX_USER_MESSAGE_CHARS = 2000
    MAX_SQL_ROWS = 200
    MAX_PREVIEW_CHARS = 1500
    MAX_PREVIEW_PAGES = 2
    TOP_K_RETRIEVAL = 4
    CHUNK_SIZE = 700
    CHUNK_OVERLAP = 120

    # New: PostgreSQL connection settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "enterprise_db")
    DB_USER = os.getenv("DB_USER", "app_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "app_password")

app_state: Dict[str, Any] = {
    "uploaded_files": [],
    "knowledge_base_ready": False,
    "total_chunks": 0,
    "chat_history": [],
    "working_gemini_model": None,
}

def get_log_file_path() -> Path:
    date_str = datetime.now().strftime("%Y%m%d")
    return LOG_DIR / f"enterprise_ai_assistant_{date_str}.jsonl"

def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "payload": payload,
    }
    try:
        with open(get_log_file_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # avoid crashing app on logging failures
        pass

def safe_user_message(message: str) -> str:
    text = (message or "").strip()
    return text[:Config.MAX_USER_MESSAGE_CHARS]

def safe_public_error(
    default_message: str,
    event_type: str,
    error: Exception,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    payload = {"error": str(error)}
    if extra:
        payload.update(extra)
    log_event(event_type, payload)
    return default_message