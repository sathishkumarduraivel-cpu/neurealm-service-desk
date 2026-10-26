import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./servicedesk.db")
for _pfx in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_pfx):
        DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(_pfx):]
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
