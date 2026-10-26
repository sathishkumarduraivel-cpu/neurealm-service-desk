from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from . import config
import logging

def _make_engine(url):
    kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True, "pool_recycle": 300}  # Neon computes scale to zero
    return create_engine(url, **kw)

engine = _make_engine(config.DATABASE_URL)
if not config.DATABASE_URL.startswith("sqlite"):
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
    except Exception as e:  # Postgres unavailable -> SQLite fallback
        logging.warning("Postgres unavailable (%s); falling back to SQLite", e)
        engine = _make_engine("sqlite:///./servicedesk.db")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

NAMING = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s",
          "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
