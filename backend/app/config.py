import os
from pathlib import Path
from dotenv import load_dotenv

# Local dev: pick up the env `neon env pull` writes at the repo root. Real env vars (Render) always win.
for _f in (".env", ".env.local"):
    load_dotenv(Path(__file__).resolve().parents[2] / _f, override=False)

def _sa_url(url):
    for pfx in ("postgres://", "postgresql://"):
        if url.startswith(pfx):
            return "postgresql+psycopg2://" + url[len(pfx):]
    return url

DATABASE_URL = _sa_url(os.getenv("DATABASE_URL", "sqlite:///./servicedesk.db"))  # Neon pooled URL for app traffic
MIGRATION_DATABASE_URL = _sa_url(os.getenv("DATABASE_URL_UNPOOLED") or DATABASE_URL)  # direct URL for Alembic DDL
try:
    from sqlalchemy.engine import make_url as _mk
    _mk(DATABASE_URL)
except Exception:  # malformed/placeholder value -> run on local SQLite instead of crash-looping
    import logging as _lg
    _lg.warning("DATABASE_URL is not a valid SQLAlchemy URL; falling back to SQLite (data is ephemeral)")
    DATABASE_URL = "sqlite:///./servicedesk.db"  # e.g. postgresql+psycopg2://servicedesk:servicedesk@db:5432/servicedesk
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-in-production-please-32b")
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "720"))
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.6"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
BRAND_NAME = os.getenv("BRAND_NAME", "Neurealm Service Desk")  # product name used in API titles and emails
