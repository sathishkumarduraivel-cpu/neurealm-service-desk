from datetime import datetime, UTC
from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey, JSON, Float, Table, Column, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    """Naive UTC timestamp (timezone-aware source; stored naive for SQLite/Postgres parity)."""
    return datetime.now(UTC).replace(tzinfo=None)

def TID():
    return mapped_column(Integer, ForeignKey("tenants.id"), default=1, index=True)

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    domain: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Group(Base):
    tenant_id: Mapped[int] = TID()
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255), default="")

class User(Base):
    tenant_id: Mapped[int] = TID()
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="end_user")  # admin|agent|end_user
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    sso_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    group = relationship("Group")

class ApiKey(Base):
    __tablename__ = "api_keys"
    tenant_id: Mapped[int] = TID()
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

record_links = Table("record_links", Base.metadata,
    Column("parent_id", ForeignKey("records.id"), primary_key=True),
    Column("child_id", ForeignKey("records.id"), primary_key=True))

class FieldDef(Base):
    """Admin-defined custom field (form designer). Values live in Record.data[key]."""
    __tablename__ = "field_defs"
    tenant_id: Mapped[int] = TID()
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), index=True)
    label: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="text")
    options: Mapped[list] = mapped_column(JSON, default=list)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    default: Mapped[dict] = mapped_column(JSON, default=dict)  # {"v": value}
    help: Mapped[str] = mapped_column(String(300), default="")
    section: Mapped[str] = mapped_column(String(80), default="Details")
    position: Mapped[int] = mapped_column(Integer, default=0)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    show_in_list: Mapped[bool] = mapped_column(Boolean, default=False)
    modules: Mapped[list] = mapped_column(JSON, default=list)  # ["incident", ...] or ["*"]
    condition: Mapped[dict] = mapped_column(JSON, default=dict)  # {"field","op","value"} -> show only when true
    ref_module: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Record(Base):
    """Generic task record. module: incident | problem | change | request"""
    __tablename__ = "records"
    tenant_id: Mapped[int] = TID()
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("records.id"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(30), default="new", index=True)
    priority: Mapped[str] = mapped_column(String(5), default="P3")
    impact: Mapped[int] = mapped_column(Integer, default=3)
    urgency: Mapped[int] = mapped_column(Integer, default=3)
    category: Mapped[str] = mapped_column(String(50), default="general")
    assignment_group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # module-specific fields
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_suggestion: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assignment_group = relationship("Group")
    assignee = relationship("User", foreign_keys=[assignee_id])
    requester = relationship("User", foreign_keys=[requester_id])
    linked = relationship("Record", secondary=record_links,
        primaryjoin=id == record_links.c.parent_id, secondaryjoin=id == record_links.c.child_id)
    comments = relationship("Comment", order_by="Comment.created_at", cascade="all,delete-orphan")
    approvals = relationship("Approval", cascade="all,delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    author = relationship("User")

class Attachment(Base):
    __tablename__ = "attachments"
    tenant_id: Mapped[int] = TID()
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    level: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default="requested")  # requested|approved|rejected
    comment: Mapped[str] = mapped_column(String(500), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approver = relationship("User")

class CatalogItem(Base):
    tenant_id: Mapped[int] = TID()
    __tablename__ = "catalog_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(10), default="📦")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    fulfillment_group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    form_fields: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_stages: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # [{"name","approver": "admin"|"group:<name>"|"user:<id>"}]
    fulfilment_tasks: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # ["Order laptop", ...]
    entitled: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # [] = everyone; roles or "group:<name>"

class KBArticle(Base):
    tenant_id: Mapped[int] = TID()
    __tablename__ = "kb_articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="general")
    tags: Mapped[str] = mapped_column(String(300), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    versions: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    helpful: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    not_helpful: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

class SLAPolicy(Base):
    tenant_id: Mapped[int] = TID()
    __tablename__ = "sla_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    module: Mapped[str] = mapped_column(String(20), default="incident")
    priority: Mapped[str] = mapped_column(String(5))
    response_minutes: Mapped[int] = mapped_column(Integer)
    resolution_minutes: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), default="info")  # info|sla_warning|sla_breach|escalation|approval|ai
    title: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(200), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)

class CIRelation(Base):
    __tablename__ = "ci_relations"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    parent_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    child_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    rel_type: Mapped[str] = mapped_column(String(50), default="depends_on")  # depends_on|runs_on|hosted_on|connects_to

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    source: Mapped[str] = mapped_column(String(50))
    node: Mapped[str] = mapped_column(String(200))
    metric: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))  # critical|major|minor|warning|info|clear
    message: Mapped[str] = mapped_column(Text, default="")
    correlation_key: Mapped[str] = mapped_column(String(300), index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default="open")  # open|closed|suppressed
    ci_id: Mapped[int | None] = mapped_column(ForeignKey("records.id"), nullable=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("records.id"), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)

class CostRecord(Base):
    __tablename__ = "cost_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    provider: Mapped[str] = mapped_column(String(50))  # AWS|Azure|GCP|SaaS|...
    service: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20), default="cloud")  # cloud|saas|license|asset|service
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    amount: Mapped[float] = mapped_column(Float)
    utilization: Mapped[float] = mapped_column(Float, default=1.0)

class AutoRun(Base):
    __tablename__ = "auto_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    playbook: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)
    risk: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(30))  # resolved|awaiting_approval|rejected|no_match|escalated|dry_run
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class WorkflowDef(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(30))
    trigger: Mapped[str] = mapped_column(String(20), default="created")  # created|updated
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    edges: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    modules: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # [] -> [module]; ["*"] = all
    trigger_cfg: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")  # field/op/value, to_state, every_minutes
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    tenant_id: Mapped[int] = TID()
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="done")  # done|waiting|awaiting_approval|failed
    trace: Mapped[list] = mapped_column(JSON, default=list)
    resume_nodes: Mapped[list] = mapped_column(JSON, default=list)
    resume_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class QualityAudit(Base):
    __tablename__ = "quality_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    findings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class DexDevice(Base):
    __tablename__ = "dex_devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    hostname: Mapped[str] = mapped_column(String(100))
    user_email: Mapped[str] = mapped_column(String(200), default="")
    os: Mapped[str] = mapped_column(String(50), default="Windows 11")
    boot_seconds: Mapped[float] = mapped_column(Float, default=40)
    crashes_7d: Mapped[int] = mapped_column(Integer, default=0)
    cpu_pct: Mapped[float] = mapped_column(Float, default=30)
    mem_pct: Mapped[float] = mapped_column(Float, default=50)
    disk_free_pct: Mapped[float] = mapped_column(Float, default=40)
    sentiment: Mapped[float] = mapped_column(Float, default=4.0)  # 1-5 survey
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Connector(Base):
    __tablename__ = "connectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    kind: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    secret: Mapped[str] = mapped_column(String(100), default="")

class ConnectorLog(Base):
    __tablename__ = "connector_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = TID()
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("connectors.id"), nullable=True)
    direction: Mapped[str] = mapped_column(String(10))  # in|out
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
