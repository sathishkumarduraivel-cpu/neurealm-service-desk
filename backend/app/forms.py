"""Form designer: per-tenant custom field definitions, validation, conditional visibility, export."""
import csv, io, re
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import audit, registry
from .db import get_db
from .models import FieldDef, Record, User, Group
from .security import current_user, admin_only, staff

TYPES = ["text", "textarea", "number", "date", "choice", "multichoice", "user", "group", "reference", "checkbox"]
router = APIRouter(prefix="/api/forms", tags=["forms"])

def fields_for(db, tenant_id, module, include_hidden=False):
    rows = db.scalars(select(FieldDef).where(FieldDef.tenant_id == tenant_id).order_by(FieldDef.position, FieldDef.id)).all()
    return [f for f in rows if (module in (f.modules or []) or "*" in (f.modules or [])) and (include_hidden or not f.hidden)]

def out(f):
    return {"id": f.id, "key": f.key, "label": f.label, "type": f.type, "options": f.options or [], "required": f.required,
            "default": (f.default or {}).get("v"), "help": f.help, "section": f.section or "Details", "position": f.position,
            "hidden": f.hidden, "show_in_list": f.show_in_list, "modules": f.modules or [], "condition": f.condition or {}, "ref_module": f.ref_module}

def visible(f, data):
    c = f.condition or {}
    if not c.get("field"): return True
    v = data.get(c["field"]); x = c.get("value"); op = c.get("op", "eq")
    vs = [str(i).lower() for i in v] if isinstance(v, list) else [str(v if v is not None else "").lower()]
    xs = str(x if x is not None else "").lower()
    if op == "eq": return xs in vs
    if op == "neq": return xs not in vs
    if op == "filled": return any(vs) and vs != [""] and v not in (None, False)
    if op == "empty": return not v
    return True

def _coerce(db, tid, f, v):
    if v is None or v == "" or v == []: return None
    t = f.type
    try:
        if t == "number": return float(v) if "." in str(v) else int(v)
        if t == "checkbox": return bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")
        if t == "date": date.fromisoformat(str(v)[:10]); return str(v)[:10]
        if t == "choice":
            if str(v) not in f.options: raise ValueError
            return str(v)
        if t == "multichoice":
            vals = v if isinstance(v, list) else [p.strip() for p in str(v).split(",")]
            if any(x not in f.options for x in vals): raise ValueError
            return vals
        if t in ("user", "group"):
            m = User if t == "user" else Group; o = db.get(m, int(v))
            if not o or o.tenant_id != tid: raise ValueError
            return o.id
        if t == "reference":
            o = db.get(Record, int(v))
            if not o or o.tenant_id != tid or (f.ref_module and o.module != f.ref_module): raise ValueError
            return o.id
        return str(v)[:5000]
    except (ValueError, TypeError):
        raise HTTPException(400, f"“{f.label}” doesn't look right. Please check the value.")

def apply(db, tid, module, data, create=False):
    """Validate + coerce custom values inside record data. Fills defaults on create, enforces required for visible fields."""
    data = dict(data or {})
    defs = fields_for(db, tid, module)
    for f in defs:
        if create and f.key not in data and (f.default or {}).get("v") not in (None, ""): data[f.key] = f.default["v"]
        if f.key in data: data[f.key] = _coerce(db, tid, f, data[f.key])
    for f in defs:
        if f.required and visible(f, data) and data.get(f.key) in (None, "", []):
            raise HTTPException(400, f"Please fill in “{f.label}”.")
        if not visible(f, data) and f.key in data and data[f.key] is not None: data[f.key] = None
    return data

def filter_rows(db, tid, module, rows, params):
    defs = {f.key: f for f in fields_for(db, tid, module, True)}
    for k, v in params.items():
        if not k.startswith("cf_") or k[3:] not in defs: continue
        key = k[3:]
        def ok(r, key=key, v=v):
            x = (r.data or {}).get(key)
            return v.lower() in [str(i).lower() for i in x] if isinstance(x, list) else str(x if x is not None else "").lower() == v.lower()
        rows = [r for r in rows if ok(r)]
    return rows

class FieldIn(BaseModel):
    label: str; type: str = "text"; key: str | None = None; options: list[str] = []; required: bool = False; default: object = None
    help: str = ""; section: str = "Details"; hidden: bool = False; show_in_list: bool = False; modules: list[str] = ["incident"]
    condition: dict = {}; ref_module: str | None = None

def _check(b: FieldIn):
    if b.type not in TYPES: raise HTTPException(400, f"Unknown field type: {b.type}")
    if not b.label.strip(): raise HTTPException(400, "Please give the field a label.")
    if not b.modules or any(m != "*" and m not in registry.MODULES for m in b.modules): raise HTTPException(400, "Pick at least one valid module.")
    if b.type in ("choice", "multichoice") and not [o for o in b.options if o.strip()]: raise HTTPException(400, "Choice fields need at least one option.")
    if b.ref_module and b.ref_module not in registry.MODULES: raise HTTPException(400, "Unknown reference module.")

def _apply_body(f, b):
    f.label = b.label.strip(); f.type = b.type; f.options = [o.strip() for o in b.options if o.strip()]; f.required = b.required
    f.default = {"v": b.default}; f.help = b.help.strip(); f.section = b.section.strip() or "Details"; f.hidden = b.hidden
    f.show_in_list = b.show_in_list; f.modules = b.modules; f.condition = b.condition or {}; f.ref_module = b.ref_module

@router.get("/types")
def types(_=Depends(current_user)): return TYPES

@router.get("/fields")
def list_fields(module: str | None = None, include_hidden: bool = False, u=Depends(current_user), db: Session = Depends(get_db)):
    if module: return [out(f) for f in fields_for(db, u.tenant_id, module, include_hidden and u.role == "admin")]
    return [out(f) for f in db.scalars(select(FieldDef).where(FieldDef.tenant_id == u.tenant_id).order_by(FieldDef.position, FieldDef.id))]

@router.post("/fields", status_code=201)
def create_field(b: FieldIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    _check(b)
    key = re.sub(r"[^a-z0-9_]", "_", (b.key or b.label).strip().lower()).strip("_")[:60] or "field"
    if key in {"title", "description", "state", "priority", "category", "impact", "urgency"}: key = "cf_" + key
    if db.scalar(select(FieldDef).where(FieldDef.tenant_id == u.tenant_id, FieldDef.key == key)): raise HTTPException(409, "A field with that key already exists.")
    n = len(db.scalars(select(FieldDef.id).where(FieldDef.tenant_id == u.tenant_id)).all())
    f = FieldDef(tenant_id=u.tenant_id, key=key, position=n); _apply_body(f, b); db.add(f); db.flush()
    audit.log(db, u.id, "field.create", "field", f.id, {"key": key, "modules": b.modules}); db.commit()
    return out(f)

def _get(db, fid, u):
    f = db.get(FieldDef, fid)
    if not f or f.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    return f

@router.put("/fields/{fid}")
def update_field(fid: int, b: FieldIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    _check(b); f = _get(db, fid, u); _apply_body(f, b)
    audit.log(db, u.id, "field.update", "field", f.id, {"key": f.key}); db.commit(); return out(f)

@router.delete("/fields/{fid}")
def delete_field(fid: int, u=Depends(admin_only), db: Session = Depends(get_db)):
    f = _get(db, fid, u); db.delete(f); audit.log(db, u.id, "field.delete", "field", fid, {"key": f.key}); db.commit(); return {"ok": True}

class OrderIn(BaseModel):
    ids: list[int]

@router.post("/fields/reorder")
def reorder(b: OrderIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    for i, fid in enumerate(b.ids): _get(db, fid, u).position = i
    audit.log(db, u.id, "field.reorder", "field", 0, {"ids": b.ids}); db.commit(); return {"ok": True}

export_router = APIRouter(prefix="/api")
@export_router.get("/records/{module}/export.csv")
def export_csv(module: str, u=Depends(staff), db: Session = Depends(get_db)):
    if module not in registry.MODULES: raise HTTPException(404, "Unknown module")
    defs = fields_for(db, u.tenant_id, module, True)
    rows = db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == module).order_by(Record.id)).all()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["number", "title", "state", "priority", "category", "created_at"] + [f.label for f in defs])
    for r in rows:
        vals = [(r.data or {}).get(f.key) for f in defs]
        w.writerow([r.number, r.title, r.state, r.priority, r.category, r.created_at.isoformat() if r.created_at else ""] + [", ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else v) for v in vals])
    audit.log(db, u.id, "export", module, 0, {"rows": len(rows)}); db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={module}s.csv"})
