from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class GroupOut(ORM):
    id: int; name: str; description: str = ""

class UserOut(ORM):
    id: int; email: str; full_name: str; role: str; group_id: int | None = None; active: bool

class UserCreate(BaseModel):
    email: str; full_name: str; password: str; role: str = "end_user"; group_id: int | None = None

class UserUpdate(BaseModel):
    full_name: str | None = None; role: str | None = None; group_id: int | None = None; active: bool | None = None; password: str | None = None

class RecordCreate(BaseModel):
    title: str; description: str = ""; priority: str | None = None; impact: int | None = None; urgency: int | None = None
    category: str | None = None; assignment_group_id: int | None = None; assignee_id: int | None = None
    data: dict[str, Any] = {}; use_ai: bool = True

class RecordUpdate(BaseModel):
    title: str | None = None; description: str | None = None; state: str | None = None; priority: str | None = None
    impact: int | None = None; urgency: int | None = None; category: str | None = None
    assignment_group_id: int | None = None; assignee_id: int | None = None; data: dict[str, Any] | None = None
    expected_updated_at: str | None = None  # optimistic concurrency: 409 if the record changed meanwhile

class CommentIn(BaseModel):
    body: str; internal: bool = False

class CommentOut(ORM):
    id: int; body: str; internal: bool; created_at: datetime; author: UserOut | None = None

class ApprovalOut(ORM):
    id: int; level: int; state: str; comment: str; decided_at: datetime | None; approver: UserOut | None = None

class RecordBrief(ORM):
    id: int; number: str; module: str; title: str; state: str; priority: str

class RecordOut(ORM):
    id: int; number: str; module: str; title: str; description: str; state: str; priority: str; impact: int; urgency: int
    category: str; assignment_group: GroupOut | None = None; assignee: UserOut | None = None; requester: UserOut | None = None
    assignment_group_id: int | None = None; assignee_id: int | None = None
    data: dict; sla_due_at: datetime | None; response_due_at: datetime | None; sla_breached: bool; sla_status: str = "none"
    ai_suggestion: dict; created_at: datetime; updated_at: datetime; resolved_at: datetime | None

class RecordDetail(RecordOut):
    linked: list[RecordBrief] = []; comments: list[CommentOut] = []; approvals: list[ApprovalOut] = []
    allowed_transitions: list[str] = []

class Decision(BaseModel):
    approve: bool; comment: str = ""

class CatalogItemIn(BaseModel):
    name: str; category: str; description: str = ""; icon: str = "📦"; requires_approval: bool = True
    fulfillment_group_id: int | None = None; form_fields: list = []

class CatalogItemOut(CatalogItemIn, ORM):
    id: int; active: bool

class OrderIn(BaseModel):
    values: dict[str, Any] = {}; justification: str = ""

class KBIn(BaseModel):
    title: str; body: str; category: str = "general"; tags: str = ""; published: bool = True

class KBOut(ORM):
    id: int; number: str; title: str; body: str; category: str; tags: str; published: bool; views: int; ai_generated: bool; created_at: datetime; version: int = 1; helpful: int = 0; not_helpful: int = 0

class SLAIn(BaseModel):
    name: str; module: str = "incident"; priority: str; response_minutes: int; resolution_minutes: int; active: bool = True

class SLAOut(SLAIn, ORM):
    id: int

class TriageIn(BaseModel):
    title: str; description: str = ""

class AuditOut(ORM):
    id: int; ts: datetime; actor_id: int | None; action: str; entity: str; entity_id: str; details: dict; prev_hash: str; hash: str
