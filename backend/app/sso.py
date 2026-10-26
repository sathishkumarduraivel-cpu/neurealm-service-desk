"""SSO-ready OIDC (Azure AD / Okta / any OIDC IdP). Configure via env:
OIDC_PROVIDER=azuread|okta  OIDC_ISSUER=...  OIDC_CLIENT_ID=...  OIDC_CLIENT_SECRET=...  OIDC_REDIRECT_URI=http://host/api/auth/sso/callback
Azure AD issuer: https://login.microsoftonline.com/<tenant>/v2.0 ; Okta: https://<org>.okta.com/oauth2/default"""
import os, secrets, urllib.parse
import httpx, jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import User
from .security import make_token, hash_pw
from . import audit

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])
_states: dict[str, bool] = {}

def cfg():
    return {"provider": os.getenv("OIDC_PROVIDER", ""), "issuer": os.getenv("OIDC_ISSUER", ""), "client_id": os.getenv("OIDC_CLIENT_ID", ""),
            "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""), "redirect_uri": os.getenv("OIDC_REDIRECT_URI", ""),
            "scopes": os.getenv("OIDC_SCOPES", "openid profile email"), "default_role": os.getenv("OIDC_DEFAULT_ROLE", "end_user")}

def enabled(): c = cfg(); return bool(c["issuer"] and c["client_id"])

@router.get("/config")
def config():
    c = cfg(); return {"enabled": enabled(), "provider": c["provider"] or None, "issuer": c["issuer"] or None,
                       "supported": ["azuread", "okta", "ping", "generic-oidc"]}

def discovery():
    r = httpx.get(cfg()["issuer"].rstrip("/") + "/.well-known/openid-configuration", timeout=10); r.raise_for_status(); return r.json()

@router.get("/login")
def login():
    if not enabled(): raise HTTPException(501, "SSO not configured (set OIDC_ISSUER / OIDC_CLIENT_ID)")
    c = cfg(); st = secrets.token_urlsafe(16); _states[st] = True
    q = urllib.parse.urlencode({"client_id": c["client_id"], "response_type": "code", "scope": c["scopes"], "redirect_uri": c["redirect_uri"], "state": st})
    return {"authorize_url": f"{discovery()['authorization_endpoint']}?{q}"}

@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    if not enabled(): raise HTTPException(501, "SSO not configured")
    if not _states.pop(state, None): raise HTTPException(400, "Invalid state")
    c = cfg(); d = discovery()
    tok = httpx.post(d["token_endpoint"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": c["redirect_uri"],
                     "client_id": c["client_id"], "client_secret": c["client_secret"]}, timeout=10).json()
    jwks = jwt.PyJWKClient(d["jwks_uri"])
    claims = jwt.decode(tok["id_token"], jwks.get_signing_key_from_jwt(tok["id_token"]).key, algorithms=["RS256"], audience=c["client_id"])
    email = (claims.get("email") or claims.get("preferred_username") or "").lower()
    u = db.scalar(select(User).where(User.email == email))
    if not u:  # JIT provisioning
        u = User(email=email, full_name=claims.get("name", email), role=c["default_role"], password_hash=hash_pw(secrets.token_hex(16)), sso_subject=claims["sub"])
        db.add(u); db.flush()
    audit.log(db, u.id, "sso_login", "user", u.id, {"provider": c["provider"]}); db.commit()
    return {"access_token": make_token(u), "token_type": "bearer"}
