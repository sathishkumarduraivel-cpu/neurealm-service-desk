from datetime import datetime, timedelta, UTC
import bcrypt, jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import config
from .db import get_db
from .models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=8)).decode()

def verify_pw(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())

def make_token(u: User, imp: int | None = None, purpose: str = "access", minutes: int | None = None) -> str:
    exp = datetime.now(UTC) + timedelta(minutes=minutes or config.JWT_EXPIRE_MIN)
    claims = {"sub": str(u.id), "role": u.role, "tid": u.tenant_id, "exp": exp, "pur": purpose}
    if imp: claims["imp"] = imp
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALG)

def decode(token: str, purpose: str = "access") -> dict:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    if payload.get("pur", "access") != purpose: raise HTTPException(401, "Invalid token")
    return payload

def key_hash(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode()).hexdigest()

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    if token.startswith("nrsd_"):
        from sqlalchemy import select
        from .models import ApiKey
        k = db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash(token), ApiKey.revoked == False))  # noqa: E712
        if not k: raise HTTPException(401, "Invalid API key")
        k.last_used_at = datetime.now(UTC).replace(tzinfo=None); db.commit()
        u = db.get(User, k.user_id)
        if not u or not u.active: raise HTTPException(401, "Inactive user")
        u._impersonator = None
        return u
    payload = decode(token)
    u = db.get(User, int(payload["sub"]))
    if not u or not u.active:
        raise HTTPException(401, "Inactive user")
    u._impersonator = payload.get("imp")
    return u

def require(*roles):
    def dep(u: User = Depends(current_user)) -> User:
        if u.role not in roles:
            raise HTTPException(403, "Insufficient role")
        return u
    return dep

staff = require("admin", "agent")
admin_only = require("admin")
