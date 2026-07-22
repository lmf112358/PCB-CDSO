from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from pcb_cdso.db.base import Base


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, native_enum=False, create_constraint=True, length=16),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # M1 (migration 0002): locale/theme are account-level preferences per PRD
    # section 11; password_changed_at supports future token-invalidation.
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="zh-CN")
    theme: Mapped[str] = mapped_column(String(8), nullable=False, default="light")
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuthSession(Base):
    """Server-revocable opaque token session (ADR-0002).

    token_hash/refresh_token_hash store sha256(token) hex, never the raw
    token. A session is invalid when revoked_at is set OR user.is_active is
    False OR expires_at has passed. Refresh rotates both hashes in one
    transaction.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Template(Base):
    """Minimal PCB product template skeleton.

    Full lifecycle (DRAFT/PUBLISHED/ARCHIVED, bilingual content, process
    chain, rules, coefficients) is frozen by docs/specs/m1/template-lifecycle.md
    (P0_03, future). M1 only needs PUBLISHED versions to be referenceable.
    """

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TemplateVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class TemplateVersion(Base):
    """Immutable published snapshot of a template's business content."""

    __tablename__ = "template_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    SOFT_DELETED = "SOFT_DELETED"


class Project(Base):
    """A PCB factory project owned by one ENGINEER or created-by ADMIN.

    Per docs/specs/m1/project-weather-dispatch.md: input_revision starts at 1
    and increments when city/template inputs change; ownership_version is
    reserved for future transfer (P0_02 spec, not used in M1).
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    admin_area: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ProjectStatus.ACTIVE)
    input_revision: Mapped[int] = mapped_column(nullable=False, default=1)
    ownership_version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class IdempotencyStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"


class IdempotencyRecord(Base):
    """Command-level dedup keyed by (actor_id, idempotency_key, scope).

    Per migration design section 7: canonical_request_hash is NOT part of any
    unique constraint; hash comparison is done in application code under
    SELECT ... FOR UPDATE. status IN_PROGRESS is transient and must roll back
    on pre-commit failure (no squatting).
    """

    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=IdempotencyStatus.IN_PROGRESS
    )
    result_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_weather_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_snapshot_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TaskStatus(StrEnum):
    DISPATCH_PENDING = "DISPATCH_PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class Task(Base):
    """Generic asynchronous task table; M1 stores WEATHER_HISTORY_FETCH.

    Worker dedup key is (project_id, input_revision, task_type), enforced by
    a unique constraint. status_version supports compare-and-set transitions
    per docs/specs/m1/project-weather-dispatch.md state table.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_revision: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=TaskStatus.DISPATCH_PENDING
    )
    status_version: Mapped[int] = mapped_column(nullable=False, default=1)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(nullable=False, default=0)
    processed: Mapped[int] = mapped_column(nullable=False, default=0)
    total: Mapped[int] = mapped_column(nullable=False, default=0)
    error_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutboxEvent(Base):
    """Reliable dispatch event for at-least-once delivery.

    Per docs/specs/m1/project-weather-dispatch.md: dispatched_at NULL means
    undispatched (reconciler scans this). Confirmation transaction atomically
    sets dispatched_at/attempt metadata AND CAS Task DISPATCH_PENDING->QUEUED.
    """

    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    input_revision: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WeatherDispatchProbe(Base):
    """M1 fake Worker effect table (test-only observable side effect).

    Per docs/specs/m1/project-weather-dispatch.md: effect_key is the Worker
    business dedup key; PRIMARY KEY(effect_key) guarantees exactly one probe
    row per dedup key, proving idempotent execution across crash-replay. M4
    real Provider defines its own request keys and does NOT reuse this.
    """

    __tablename__ = "weather_dispatch_probe"

    effect_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    input_revision: Mapped[int] = mapped_column(nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WeatherExecutionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class WeatherTaskExecution(Base):
    """Persistent Worker execution record (1:N with Task for retries).

    Per migration design section 7: independent table (NOT merged into
    tasks.stage) because executions and tasks are 1:N. Committed in the same
    transaction as weather_dispatch_probe upsert and Task CAS.
    """

    __tablename__ = "weather_task_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WeatherExecutionStatus.IN_PROGRESS
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


# ===== M2 conversation workspace (migration 0003) =====


class Conversation(Base):
    """Per-project conversation state.

    stage_state JSON holds the 8-stage completion cursor; see
    ConversationService for shape. One row per project.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    input_revision: Mapped[int] = mapped_column(nullable=False, default=1)
    stage_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationMessageType(StrEnum):
    AGENT_PROMPT = "AGENT_PROMPT"
    USER_DRAFT = "USER_DRAFT"
    CONFIRMATION_CARD = "CONFIRMATION_CARD"
    TOOL_CARD = "TOOL_CARD"


class ConversationStage(StrEnum):
    PROJECT_TEMPLATE = "PROJECT_TEMPLATE"
    GEOGRAPHY_WEATHER = "GEOGRAPHY_WEATHER"
    BUILDING_FLOOR = "BUILDING_FLOOR"
    AREA_PROCESS = "AREA_PROCESS"
    PROCESS_ENVIRONMENT = "PROCESS_ENVIRONMENT"
    COOLING_INPUT = "COOLING_INPUT"
    SCHEDULE_STORAGE = "SCHEDULE_STORAGE"
    REVIEW = "REVIEW"


class ConversationMessage(Base):
    """One of the four messageType records in the timeline.

    sort_cursor is server-issued and monotonic per conversation so replays
    are deterministic; (conversation_id, sort_cursor) is unique.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_cursor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    refers_to_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationDraft(Base):
    """USER_DRAFT content saved with CAS draft_version per (project, actor, scope)."""

    __tablename__ = "conversation_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_version: Mapped[int] = mapped_column(nullable=False, default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConfirmationChallenge(Base):
    """impact + warning token lifecycle per M2 spec '唯一业务写入路径'."""

    __tablename__ = "confirmation_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_key: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_input_revision: Mapped[int] = mapped_column(nullable=False)
    impact_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warning_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    warning_challenge_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warning_reasons: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    warning_confirmation_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationAuditSource(StrEnum):
    USER_INPUT = "USER_INPUT"
    TEMPLATE_DEFAULT = "TEMPLATE_DEFAULT"
    ENGINEER_OVERRIDE = "ENGINEER_OVERRIDE"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"


class ConversationAudit(Base):
    """Immutable per-COMMITTED audit record.

    Records actor, field path, old/new canonical value, unit, rule version,
    source, warning reasons, before/after revision, request id. Never
    records tokens, credentials, or unnecessary natural-language content.
    """

    __tablename__ = "conversation_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_key: Mapped[str] = mapped_column(String(128), nullable=False)
    field_path: Mapped[str] = mapped_column(String(128), nullable=False)
    old_canonical_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_canonical_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    warning_reasons: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    revision_before: Mapped[int] = mapped_column(nullable=False)
    revision_after: Mapped[int] = mapped_column(nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
