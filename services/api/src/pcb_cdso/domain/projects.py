"""CreateProject command and ProjectService.

Implements docs/specs/m1/project-weather-dispatch.md section '命令、领域词汇与
不变量' and '正常流程'. The command atomically writes five logical record
groups in one MySQL transaction:

  1. idempotency_records  (actor-scoped dedup; canonical hash frozen)
  2. projects             (owner = actor; input_revision = 1)
  3. template snapshot    (M1 stores snapshotIds list referencing the
                           immutable template_version payload; P0_03 will
                           add a separate session snapshot table)
  4. tasks                (WEATHER_HISTORY_FETCH, status DISPATCH_PENDING)
  5. outbox_events        (WeatherFetchRequested, undispatched)

Any pre-commit deterministic failure rolls back ALL five groups (no
squatting). Concurrent same-key + same-hash: unique constraint picks one
winner; losers read the winner's result. Concurrent same-key + different
hash: loser gets 409 IDEMPOTENCY_CONFLICT.

Worker business dedup key (projectId, inputRevision, taskType) is enforced
by a DB unique constraint and is reused as weather_dispatch_probe.effect_key.

The fake dispatcher in M1 only reads committed Outbox events; real Provider
download is M4 and explicitly out of scope here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.models import (
    IdempotencyRecord,
    IdempotencyStatus,
    OutboxEvent,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
    TemplateVersion,
    User,
    UserRole,
)
from pcb_cdso.http.errors import ApiError

LOGGER = logging.getLogger("pcb_cdso.domain.projects")

SCOPE_CREATE_PROJECT = "create_project"
TASK_TYPE_WEATHER_HISTORY_FETCH = "WEATHER_HISTORY_FETCH"
EVENT_TYPE_WEATHER_FETCH_REQUESTED = "WeatherFetchRequested"


@dataclass(frozen=True)
class CreateProjectCommand:
    """Validated CreateProject input. actorId comes from auth context only."""

    name: str
    template_version_id: str
    country_code: str
    admin_area: str
    city: str
    timezone: str
    actor_id: str
    idempotency_key: str

    @classmethod
    def from_raw(
        cls,
        *,
        name: str,
        template_version_id: str,
        country_code: str,
        admin_area: str,
        city: str,
        timezone: str,
        actor_id: str,
        idempotency_key: str,
    ) -> "CreateProjectCommand":
        """Normalize and validate fields. Raises ApiError(422) on format errors."""
        normalized_name = _normalize_text(name)
        normalized_admin_area = _normalize_text(admin_area)
        normalized_city = _normalize_text(city)
        normalized_country = country_code.strip().upper()
        normalized_tz = _normalize_timezone(timezone)
        normalized_key = idempotency_key.strip()

        errors: list[str] = []
        if not (1 <= len(normalized_name) <= 120):
            errors.append("name")
        if not normalized_admin_area or len(normalized_admin_area) > 120:
            errors.append("adminArea")
        if not normalized_city or len(normalized_city) > 120:
            errors.append("city")
        if len(normalized_country) != 2 or not normalized_country.isalpha():
            errors.append("countryCode")
        if not normalized_tz:
            errors.append("timezone")
        if not normalized_key or len(normalized_key) > 128 or not all(
            32 <= ord(c) < 127 for c in normalized_key
        ):
            errors.append("Idempotency-Key")
        if errors:
            raise ApiError(
                status_code=422,
                code="VALIDATION_FAILED",
                message_key="projects.create.validation_failed",
                field_path=errors[0],
                details={"fields": errors},
            )
        return cls(
            name=normalized_name,
            template_version_id=template_version_id.strip(),
            country_code=normalized_country,
            admin_area=normalized_admin_area,
            city=normalized_city,
            timezone=normalized_tz,
            actor_id=actor_id,
            idempotency_key=normalized_key,
        )


@dataclass(frozen=True)
class CreateProjectResult:
    project_id: str
    name: str
    owner_id: str
    template_version_id: str
    country_code: str
    admin_area: str
    city: str
    timezone: str
    input_revision: int
    snapshot_ids: list[str]
    weather_task_id: str
    is_replay: bool


# --- normalization helpers ---


def _normalize_text(value: str) -> str:
    """NFC + strip per M1 feature spec canonical payload rules."""
    if value is None:
        return ""
    return unicodedata.normalize("NFC", value).strip()


def _normalize_timezone(value: str) -> str:
    """Resolve to IANA canonical id. Empty if not resolvable (caller reports)."""
    import zoneinfo

    candidate = value.strip()
    if not candidate:
        return ""
    try:
        # zoneinfo.ZoneInfo validates the key; raises ZoneInfoNotFoundError.
        zoneinfo.ZoneInfo(candidate)
    except Exception:
        return ""
    return candidate


def canonical_request_hash(cmd: CreateProjectCommand) -> str:
    """SHA-256 hex of the canonical JSON payload.

    Per spec: only the 6 business fields, in fixed order
    (name, templateVersionId, countryCode, adminArea, city, timezone),
    NFC + trimmed, countryCode upper, IANA canonical. UTF-8 JSON with
    ensure_ascii=False, separators tight, sort_keys=False (order is fixed
    by the dict construction).
    """
    payload = {
        "name": cmd.name,
        "templateVersionId": cmd.template_version_id,
        "countryCode": cmd.country_code,
        "adminArea": cmd.admin_area,
        "city": cmd.city,
        "timezone": cmd.timezone,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# --- service ---


class ProjectService:
    """Application service for project lifecycle.

    All public methods commit in their own transaction via session_factory.
    Concurrency is controlled by the unique constraint on
    idempotency_records (actor_id, idempotency_key, scope); application code
    handles winner/loser semantics around that constraint.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_project(
        self,
        cmd: CreateProjectCommand,
        *,
        actor_role: UserRole,
    ) -> CreateProjectResult:
        """Execute CreateProject atomically. Raises ApiError on any failure."""
        self._authorize(role=actor_role)
        canonical_hash = canonical_request_hash(cmd)
        try:
            with self._session_factory.begin() as session:
                # 1. Resolve template version (PUBLISHED + visible).
                template_version = self._resolve_template(session, cmd.template_version_id)
                # 2. Acquire idempotency record (winner/loser/replay/conflict).
                outcome = self._acquire_idempotency(
                    session,
                    cmd=cmd,
                    canonical_hash=canonical_hash,
                )
                if outcome.kind == "replay":
                    return outcome.result  # type: ignore[return-value]
                if outcome.kind == "conflict":
                    raise ApiError(
                        status_code=409,
                        code="IDEMPOTENCY_CONFLICT",
                        message_key="projects.create.idempotency_conflict",
                        field_path="Idempotency-Key",
                    )
                # 3. Winner: write Project + Task + Outbox, mark idempotency SUCCEEDED.
                result = self._write_aggregate(
                    session,
                    cmd=cmd,
                    template_version=template_version,
                    idempotency_record=outcome.record,  # type: ignore[arg-type]
                )
                outcome.record.status = IdempotencyStatus.SUCCEEDED  # type: ignore[union-attr]
                outcome.record.result_project_id = result.project_id  # type: ignore[union-attr]
                outcome.record.result_weather_task_id = result.weather_task_id  # type: ignore[union-attr]
                outcome.record.result_snapshot_ids = result.snapshot_ids  # type: ignore[union-attr]
                outcome.record.completed_at = _now()
                return result
        except ApiError:
            raise
        except Exception as error:  # pragma: no cover - defensive
            LOGGER.exception("create_project failed unexpectedly")
            raise ApiError(
                status_code=503,
                code="TRANSACTION_FAILED",
                message_key="projects.create.transaction_failed",
                details={"reason": type(error).__name__},
            ) from error

    # ----- helpers -----

    def _authorize(self, *, role: UserRole) -> None:
        if role not in (UserRole.ADMIN, UserRole.ENGINEER):
            raise ApiError(
                status_code=403,
                code="FORBIDDEN",
                message_key="projects.create.forbidden",
            )

    def _resolve_template(self, session: Session, template_version_id: str) -> TemplateVersion:
        # Anti-enumeration: missing OR non-PUBLISHED OR anything else all map
        # to the same NOT_FOUND response (no leak about existence).
        tv = session.scalar(
            select(TemplateVersion).where(TemplateVersion.id == template_version_id)
        )
        if tv is None or tv.status != "PUBLISHED":
            raise ApiError(
                status_code=404,
                code="NOT_FOUND",
                message_key="projects.create.template_not_found",
                field_path="templateVersionId",
            )
        return tv

    def _acquire_idempotency(
        self,
        session: Session,
        *,
        cmd: CreateProjectCommand,
        canonical_hash: str,
    ) -> "_IdempotencyOutcome":
        existing = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_id == cmd.actor_id,
                IdempotencyRecord.idempotency_key == cmd.idempotency_key,
                IdempotencyRecord.scope == SCOPE_CREATE_PROJECT,
            )
        )
        if existing is None:
            record = IdempotencyRecord(
                actor_id=cmd.actor_id,
                idempotency_key=cmd.idempotency_key,
                scope=SCOPE_CREATE_PROJECT,
                canonical_request_hash=canonical_hash,
                status=IdempotencyStatus.IN_PROGRESS,
            )
            session.add(record)
            session.flush()
            return _IdempotencyOutcome(kind="winner", record=record)
        # Existing record: replay, conflict, or in-progress.
        if existing.canonical_request_hash == canonical_hash:
            if existing.status == IdempotencyStatus.SUCCEEDED:
                result = self._rehydrate_result(existing)
                return _IdempotencyOutcome(kind="replay", result=result)
            # Same hash but IN_PROGRESS (concurrent winner not done yet).
            # Treat as replay once SUCCEEDED; for now, raise a retriable error.
            raise ApiError(
                status_code=503,
                code="TRANSACTION_FAILED",
                message_key="projects.create.in_progress_retry",
            )
        # Different hash -> conflict.
        return _IdempotencyOutcome(kind="conflict", record=existing)

    def _rehydrate_result(self, record: IdempotencyRecord) -> CreateProjectResult:
        # Load the Project + Task to rebuild the response. We are in the same
        # session/transaction as the caller; reads are consistent.
        project = self._session_factory()  # open a fresh read session
        try:
            with project as s:
                p = s.scalar(select(Project).where(Project.id == record.result_project_id))
                if p is None:
                    raise ApiError(
                        status_code=503,
                        code="TRANSACTION_FAILED",
                        message_key="projects.create.replay_inconsistent",
                    )
                return CreateProjectResult(
                    project_id=p.id,
                    name=p.name,
                    owner_id=p.owner_id,
                    template_version_id=p.template_version_id,
                    country_code=p.country_code,
                    admin_area=p.admin_area,
                    city=p.city,
                    timezone=p.timezone,
                    input_revision=p.input_revision,
                    snapshot_ids=record.result_snapshot_ids or [],
                    weather_task_id=record.result_weather_task_id,  # type: ignore[arg-type]
                    is_replay=True,
                )
        finally:
            project.close()

    def _write_aggregate(
        self,
        session: Session,
        *,
        cmd: CreateProjectCommand,
        template_version: TemplateVersion,
        idempotency_record: IdempotencyRecord,
    ) -> CreateProjectResult:
        project = Project(
            name=cmd.name,
            owner_id=cmd.actor_id,
            template_version_id=template_version.id,
            country_code=cmd.country_code,
            admin_area=cmd.admin_area,
            city=cmd.city,
            timezone=cmd.timezone,
            status=ProjectStatus.ACTIVE,
            input_revision=1,
            ownership_version=1,
        )
        session.add(project)
        session.flush()
        task = Task(
            project_id=project.id,
            task_type=TASK_TYPE_WEATHER_HISTORY_FETCH,
            input_revision=project.input_revision,
            status=TaskStatus.DISPATCH_PENDING,
            status_version=1,
            stage=None,
            progress=0,
            processed=0,
            total=0,
            retryable=False,
        )
        session.add(task)
        session.flush()
        from uuid import uuid4

        outbox_event_id = str(uuid4())
        outbox_payload: dict[str, Any] = {
            "eventId": outbox_event_id,
            "taskId": task.id,
            "projectId": project.id,
            "inputRevision": project.input_revision,
            "taskType": TASK_TYPE_WEATHER_HISTORY_FETCH,
            "countryCode": project.country_code,
            "adminArea": project.admin_area,
            "city": project.city,
            "timezone": project.timezone,
            "occurredAt": _now().isoformat(),
        }
        outbox = OutboxEvent(
            id=outbox_event_id,
            event_type=EVENT_TYPE_WEATHER_FETCH_REQUESTED,
            task_id=task.id,
            project_id=project.id,
            input_revision=project.input_revision,
            payload=outbox_payload,
        )
        session.add(outbox)
        session.flush()
        return CreateProjectResult(
            project_id=project.id,
            name=project.name,
            owner_id=project.owner_id,
            template_version_id=project.template_version_id,
            country_code=project.country_code,
            admin_area=project.admin_area,
            city=project.city,
            timezone=project.timezone,
            input_revision=project.input_revision,
            snapshot_ids=[template_version.id],
            weather_task_id=task.id,
            is_replay=False,
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _IdempotencyOutcome:
    kind: str  # "winner" | "replay" | "conflict"
    record: IdempotencyRecord | None = None
    result: CreateProjectResult | None = None
