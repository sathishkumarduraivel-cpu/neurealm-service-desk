import hashlib, json
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import AuditLog, now

GENESIS = "0" * 64

def _digest(prev, ts, actor, action, entity, eid, details):
    payload = json.dumps([prev, ts.isoformat(), actor, action, entity, str(eid), details], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()

def log(db: Session, actor_id, action, entity, entity_id, details=None):
    db.flush()  # make pending entries visible so the chain links correctly
    last = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev = last.hash if last else GENESIS
    ts = now(); details = details or {}
    h = _digest(prev, ts, actor_id, action, entity, entity_id, details)
    from .models import User
    actor = db.get(User, actor_id) if actor_id else None
    db.add(AuditLog(tenant_id=actor.tenant_id if actor else None, ts=ts, actor_id=actor_id, action=action, entity=entity, entity_id=str(entity_id),
                    details=details, prev_hash=prev, hash=h))

def verify_chain(db: Session):
    prev = GENESIS
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    for r in rows:
        if r.prev_hash != prev or _digest(prev, r.ts, r.actor_id, r.action, r.entity, r.entity_id, r.details) != r.hash:
            return {"valid": False, "broken_at": r.id, "entries": len(rows)}
        prev = r.hash
    return {"valid": True, "entries": len(rows), "head": prev}
