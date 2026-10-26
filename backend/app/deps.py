"""Shared helpers: tenant scoping, record numbering, serialization, notifications."""
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from . import sla, registry
from .models import Record, Notification, User
from .schemas import RecordOut, RecordDetail

def scoped(stmt, model, u):
    return stmt.where(model.tenant_id == u.tenant_id)

def next_number(db: Session, module: str) -> str:
    n = db.scalar(select(func.count()).select_from(Record).where(Record.module == module)) or 0
    return f"{registry.prefix(module)}{n + 1001:07d}"

def out(r, cls=RecordOut):
    o = cls.model_validate(r); o.sla_status = sla.sla_status(r)
    if cls is RecordDetail: o.allowed_transitions = registry.allowed(r.module, r.state)
    return o

def get_record(db, module, rid, u):
    r = db.get(Record, rid)
    if not r or r.module != module or r.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    if u.role == "end_user" and r.requester_id != u.id: raise HTTPException(403)
    return r

def check_module(module):
    if module not in registry.MODULES: raise HTTPException(404, "Unknown module")

def notify(db, tenant_id, title, kind="info", user_id=None, group_id=None, link=""):
    db.add(Notification(tenant_id=tenant_id, title=title, kind=kind, user_id=user_id, group_id=group_id, link=link))

def link_for(r): return f"/m/{r.module}/{r.id}"

def get_or_404(db, model, id_, u=None):
    o = db.get(model, id_)
    if not o or (u is not None and hasattr(o, "tenant_id") and o.tenant_id != u.tenant_id): raise HTTPException(404, "Not found")
    return o
