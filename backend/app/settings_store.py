from sqlalchemy import select
from .models import Setting
DEFAULTS = {"autoresolve": {"enabled": True, "on_create": False, "threshold": 0.6}, "patch.kill_switch": {"engaged": False, "reason": ""}}
def get(db, tenant_id, key):
    s = db.scalar(select(Setting).where(Setting.tenant_id == tenant_id, Setting.key == key))
    return {**DEFAULTS.get(key, {}), **(s.value if s else {})}
def put(db, tenant_id, key, value):
    s = db.scalar(select(Setting).where(Setting.tenant_id == tenant_id, Setting.key == key))
    if not s: s = Setting(tenant_id=tenant_id, key=key, value={}); db.add(s)
    s.value = {**get(db, tenant_id, key), **value}; return s.value
