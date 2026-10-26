"""Phase 1 — identity & access: TOTP 2FA, self-registration, API keys, impersonation, roles matrix, groups."""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import audit, totp, settings_store
from ..db import get_db
from ..models import User, ApiKey, Group, Tenant
from ..schemas import UserOut
from ..security import current_user, admin_only, make_token, decode, hash_pw, verify_pw, key_hash

router = APIRouter(prefix="/api")

ROLES = {
    "admin": {"label": "Administrator", "hint": "Full access, including settings, users and the audit trail."},
    "agent": {"label": "Agent", "hint": "Works tickets, changes, problems, assets and knowledge."},
    "end_user": {"label": "Employee", "hint": "Raises requests and incidents and reads the knowledge base."},
}
PERMISSIONS = [
    ("tickets.view_all", "See all tickets", ["admin", "agent"]),
    ("tickets.work", "Update and resolve tickets", ["admin", "agent"]),
    ("tickets.raise", "Raise incidents and requests", ["admin", "agent", "end_user"]),
    ("changes.approve", "Approve changes", ["admin", "agent"]),
    ("kb.publish", "Publish knowledge articles", ["admin", "agent"]),
    ("assets.manage", "Manage assets and CMDB", ["admin", "agent"]),
    ("users.manage", "Manage users and groups", ["admin"]),
    ("settings.manage", "Change settings and features", ["admin"]),
    ("audit.view", "View the audit trail", ["admin"]),
    ("users.impersonate", "Sign in as another user", ["admin"]),
]
AUTH_DEFAULTS = {"registration": False, "require_2fa_admins": False}

def _session(u, imp=None):
    return {"access_token": make_token(u, imp=imp), "token_type": "bearer", "user": UserOut.model_validate(u), "impersonator": imp}

def begin_login(db, u):
    """Called after the password checks out. Returns a session or an MFA challenge."""
    if u.totp_enabled:
        return {"mfa_required": True, "mfa_token": make_token(u, purpose="mfa", minutes=5)}
    audit.log(db, u.id, "login", "user", u.id); db.commit()
    return _session(u)

# ---------- public auth config / registration ----------
@router.get("/auth/config")
def auth_config(db: Session = Depends(get_db)):
    s = {**AUTH_DEFAULTS, **settings_store.get(db, 1, "auth")}
    t = db.get(Tenant, 1)
    return {"registration": bool(s["registration"]), "domain": t.domain if t else None}

class MfaIn(BaseModel):
    mfa_token: str; code: str

@router.post("/auth/mfa")
def auth_mfa(body: MfaIn, db: Session = Depends(get_db)):
    p = decode(body.mfa_token, "mfa"); u = db.get(User, int(p["sub"]))
    if not u or not u.active or not u.totp_enabled: raise HTTPException(401, "Invalid token")
    if not totp.verify(u.totp_secret, body.code):
        audit.log(db, u.id, "login.mfa_failed", "user", u.id); db.commit()
        raise HTTPException(401, "That code didn't match. Please try the latest one from your app.")
    audit.log(db, u.id, "login", "user", u.id, {"mfa": True}); db.commit()
    return _session(u)

class RegisterIn(BaseModel):
    email: str; full_name: str; password: str

@router.post("/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    cfg = auth_config(db)
    if not cfg["registration"]: raise HTTPException(403, "Self sign-up is turned off. Please ask your administrator for an invite.")
    email = body.email.strip().lower()
    if "@" not in email or (cfg["domain"] and not email.endswith("@" + cfg["domain"])):
        raise HTTPException(400, f"Please use your @{cfg['domain']} work email.")
    if len(body.password) < 8: raise HTTPException(400, "Passwords need at least 8 characters.")
    if len(body.full_name.strip()) < 2: raise HTTPException(400, "Please tell us your name.")
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, "That email already has an account. Try signing in.")
    u = User(tenant_id=1, email=email, full_name=body.full_name.strip(), role="end_user", password_hash=hash_pw(body.password))
    db.add(u); db.flush(); audit.log(db, u.id, "user.register", "user", u.id); db.commit()
    return _session(u)

@router.get("/admin/auth-settings")
def get_auth_settings(u: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {**AUTH_DEFAULTS, **settings_store.get(db, u.tenant_id, "auth")}

@router.put("/admin/auth-settings")
def put_auth_settings(body: dict, u: User = Depends(admin_only), db: Session = Depends(get_db)):
    clean = {k: bool(body[k]) for k in AUTH_DEFAULTS if k in body}
    v = settings_store.put(db, u.tenant_id, "auth", clean); audit.log(db, u.id, "auth.settings", "settings", 0, clean); db.commit()
    return {**AUTH_DEFAULTS, **v}

# ---------- my account / 2FA ----------
@router.get("/me/security")
def my_security(u: User = Depends(current_user), db: Session = Depends(get_db)):
    keys = db.scalars(select(ApiKey).where(ApiKey.user_id == u.id, ApiKey.revoked == False).order_by(ApiKey.id.desc())).all()  # noqa: E712
    return {"totp_enabled": u.totp_enabled, "impersonator": getattr(u, "_impersonator", None),
            "api_keys": [{"id": k.id, "name": k.name, "prefix": k.prefix, "created_at": k.created_at, "last_used_at": k.last_used_at} for k in keys]}

@router.post("/me/2fa/setup")
def twofa_setup(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.totp_enabled: raise HTTPException(400, "Two-step sign-in is already on.")
    u.totp_secret = totp.new_secret(); db.commit()
    return {"secret": u.totp_secret, "otpauth": totp.uri(u.totp_secret, u.email)}

class CodeIn(BaseModel):
    code: str

@router.post("/me/2fa/enable")
def twofa_enable(body: CodeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not u.totp_secret or not totp.verify(u.totp_secret, body.code): raise HTTPException(400, "That code didn't match. Please try again.")
    u.totp_enabled = True; audit.log(db, u.id, "2fa.enable", "user", u.id); db.commit()
    return {"totp_enabled": True}

@router.post("/me/2fa/disable")
def twofa_disable(body: CodeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not u.totp_enabled: return {"totp_enabled": False}
    if not totp.verify(u.totp_secret, body.code): raise HTTPException(400, "That code didn't match. Please try again.")
    u.totp_enabled = False; u.totp_secret = None; audit.log(db, u.id, "2fa.disable", "user", u.id); db.commit()
    return {"totp_enabled": False}

@router.post("/admin/users/{uid}/reset-2fa")
def reset_2fa(uid: int, a: User = Depends(admin_only), db: Session = Depends(get_db)):
    t = db.get(User, uid)
    if not t or t.tenant_id != a.tenant_id: raise HTTPException(404, "Not found")
    t.totp_enabled = False; t.totp_secret = None; audit.log(db, a.id, "2fa.reset", "user", uid); db.commit()
    return {"ok": True}

class PwIn(BaseModel):
    current: str; new: str

@router.post("/me/password")
def change_pw(body: PwIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_pw(body.current, u.password_hash): raise HTTPException(400, "Your current password isn't right.")
    if len(body.new) < 8: raise HTTPException(400, "Passwords need at least 8 characters.")
    u.password_hash = hash_pw(body.new); audit.log(db, u.id, "password.change", "user", u.id); db.commit()
    return {"ok": True}

# ---------- API keys ----------
class KeyIn(BaseModel):
    name: str

@router.post("/me/api-keys")
def create_key(body: KeyIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "end_user": raise HTTPException(403, "API keys are available to agents and admins.")
    raw = "nrsd_" + secrets.token_urlsafe(32)
    k = ApiKey(tenant_id=u.tenant_id, user_id=u.id, name=(body.name.strip() or "API key")[:100], prefix=raw[:12], key_hash=key_hash(raw))
    db.add(k); db.flush(); audit.log(db, u.id, "apikey.create", "api_key", k.id, {"name": k.name}); db.commit()
    return {"id": k.id, "name": k.name, "prefix": k.prefix, "key": raw}

@router.delete("/me/api-keys/{kid}")
def revoke_key(kid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid)
    if not k or (k.user_id != u.id and u.role != "admin") or k.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    k.revoked = True; audit.log(db, u.id, "apikey.revoke", "api_key", k.id); db.commit()
    return {"ok": True}

# ---------- impersonation ----------
@router.post("/admin/impersonate/stop")
def stop_impersonation(u: User = Depends(current_user), db: Session = Depends(get_db)):
    imp = getattr(u, "_impersonator", None)
    if not imp: raise HTTPException(400, "You are not impersonating anyone.")
    a = db.get(User, imp)
    if not a or not a.active or a.role != "admin": raise HTTPException(401, "Invalid session")
    audit.log(db, a.id, "impersonate.stop", "user", u.id); db.commit()
    return _session(a)

@router.post("/admin/impersonate/{uid}")
def impersonate(uid: int, a: User = Depends(admin_only), db: Session = Depends(get_db)):
    if getattr(a, "_impersonator", None): raise HTTPException(400, "Please stop the current impersonation first.")
    t = db.get(User, uid)
    if not t or t.tenant_id != a.tenant_id or not t.active: raise HTTPException(404, "Not found")
    if t.id == a.id: raise HTTPException(400, "You are already signed in as yourself.")
    audit.log(db, a.id, "impersonate.start", "user", t.id, {"as": t.email}); db.commit()
    return _session(t, imp=a.id)

# ---------- roles & groups ----------
@router.get("/roles")
def roles(u: User = Depends(current_user)):
    return {"roles": [{"key": k, **v} for k, v in ROLES.items()],
            "permissions": [{"key": k, "label": l, "roles": r} for k, l, r in PERMISSIONS]}

class GroupIn(BaseModel):
    name: str; description: str = ""

@router.post("/admin/groups")
def create_group(body: GroupIn, a: User = Depends(admin_only), db: Session = Depends(get_db)):
    if len(body.name.strip()) < 2: raise HTTPException(400, "Please give the group a name.")
    g = Group(tenant_id=a.tenant_id, name=body.name.strip(), description=body.description.strip())
    db.add(g); db.flush(); audit.log(db, a.id, "group.create", "group", g.id, {"name": g.name}); db.commit()
    return {"id": g.id, "name": g.name, "description": g.description}

@router.patch("/admin/groups/{gid}")
def update_group(gid: int, body: GroupIn, a: User = Depends(admin_only), db: Session = Depends(get_db)):
    g = db.get(Group, gid)
    if not g or g.tenant_id != a.tenant_id: raise HTTPException(404, "Not found")
    g.name = body.name.strip() or g.name; g.description = body.description.strip()
    audit.log(db, a.id, "group.update", "group", g.id); db.commit()
    return {"id": g.id, "name": g.name, "description": g.description}
