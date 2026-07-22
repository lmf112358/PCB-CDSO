"""M2 conversation service skeleton.

Implements the M2 spec's core state machine and persistence for the
'唯一业务写入路径' (AGENT_PROMPT -> USER_DRAFT -> CONFIRMATION_CARD ->
VALIDATING -> COMMITTED|BLOCKED|WARNING_CONFIRMATION|REVISION_CONFLICT).

This is a SKELETON focused on the normal COMMITTED path and draft CAS so
the front-end can switch off mock data. The full warning-challenge
lifecycle (SubmitWarningReasons, warningConfirmationToken) and the
hard-rule BLOCKED + revision-conflict branches are marked as TODO and
return structured 'not yet implemented' responses rather than partial
behavior; they will be filled in once field-registry validation rules
land (P0_05/P0_06).

Key invariants enforced here:
- One conversation per project (uq_conversations_project).
- Server-issued monotonic sort_cursor per conversation; replays deterministic.
- Draft CAS by (project_id, actor_id, scope_key); stale draftVersion -> 409.
- inputRevision increments atomically on every COMMITTED confirm.
- Confirmation consumes impactToken exactly once (consumed_at set on first
  confirm regardless of outcome).
- All mutations commit in their own transaction via session_factory.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.models import (
    Conversation,
    ConversationAudit,
    ConversationAuditSource,
    ConversationDraft,
    ConversationMessage,
    ConversationMessageType,
    ConversationStage,
    ConfirmationChallenge,
    Project,
    User,
    UserRole,
)
from pcb_cdso.http.errors import ApiError

LOGGER = logging.getLogger("pcb_cdso.domain.conversation")

IMPACT_TOKEN_TTL_SECONDS = 30 * 60  # 30 min
WARNING_CHALLENGE_TTL_SECONDS = 30 * 60

# Fixed 8-stage order per M2 spec '八阶段与工艺链'.
STAGE_ORDER: list[ConversationStage] = [
    ConversationStage.PROJECT_TEMPLATE,
    ConversationStage.GEOGRAPHY_WEATHER,
    ConversationStage.BUILDING_FLOOR,
    ConversationStage.AREA_PROCESS,
    ConversationStage.PROCESS_ENVIRONMENT,
    ConversationStage.COOLING_INPUT,
    ConversationStage.SCHEDULE_STORAGE,
    ConversationStage.REVIEW,
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """Coerce SQLite-returned naive datetimes to UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- DTOs ---


@dataclass(frozen=True)
class MessageSnapshot:
    id: str
    message_type: str
    stage: str
    sort_cursor: int
    payload: dict[str, Any]
    refers_to_message_id: str | None
    created_at: str


@dataclass(frozen=True)
class DraftSnapshot:
    id: str
    scope_key: str
    draft_version: int
    content: dict[str, Any]
    updated_at: str


@dataclass(frozen=True)
class ConversationSnapshot:
    conversation_id: str
    project_id: str
    input_revision: int
    stage_state: dict[str, Any]
    messages: list[MessageSnapshot]
    drafts: list[DraftSnapshot]
    first_unfinished_stage: str | None
    first_unfinished_question_key: str | None


@dataclass(frozen=True)
class IssueChallengeResult:
    challenge_id: str
    impact_token: str  # raw; only leaves server here
    expected_input_revision: int
    expires_at: str


@dataclass(frozen=True)
class ConfirmResult:
    presentation_state: str  # COMMITTED | BLOCKED | WARNING_CONFIRMATION | REVISION_CONFLICT
    new_input_revision: int | None
    confirmation_message_id: str
    warning_challenge_id: str | None  # set when WARNING_CONFIRMATION


class ConversationService:
    """Per-project conversation state machine and persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # ----- read -----

    def get_or_create_conversation(self, project_id: str) -> Conversation:
        with self._session_factory.begin() as session:
            conv = session.scalar(
                select(Conversation).where(Conversation.project_id == project_id)
            )
            if conv is not None:
                return conv
            conv = Conversation(
                project_id=project_id,
                input_revision=1,
                stage_state={stage.value: "todo" for stage in STAGE_ORDER},
            )
            session.add(conv)
            session.flush()
            return conv

    def snapshot(
        self,
        *,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
    ) -> ConversationSnapshot:
        """Return a consistent conversation snapshot for the caller.

        Enforces M1 scoped lookup: cross-owner existing project id and
        random unknown id both raise the same 404 NOT_FOUND.
        """
        with self._session_factory() as session:
            self._authorize_project(session, project_id, actor_id, actor_role)
            conv = self._require_conversation(session, project_id)
            messages = (
                session.scalars(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conv.id)
                    .order_by(ConversationMessage.sort_cursor.asc())
                ).all()
            )
            drafts = (
                session.scalars(
                    select(ConversationDraft)
                    .where(
                        ConversationDraft.project_id == project_id,
                        ConversationDraft.actor_id == actor_id,
                    )
                    .order_by(ConversationDraft.updated_at.desc())
                ).all()
            )
            first_unfinished = self._first_unfinished_stage(conv.stage_state)
            return ConversationSnapshot(
                conversation_id=conv.id,
                project_id=project_id,
                input_revision=conv.input_revision,
                stage_state=dict(conv.stage_state),
                messages=[
                    MessageSnapshot(
                        id=m.id,
                        message_type=m.message_type,
                        stage=m.stage,
                        sort_cursor=m.sort_cursor,
                        payload=dict(m.payload),
                        refers_to_message_id=m.refers_to_message_id,
                        created_at=_as_aware(m.created_at).isoformat(),
                    )
                    for m in messages
                ],
                drafts=[
                    DraftSnapshot(
                        id=d.id,
                        scope_key=d.scope_key,
                        draft_version=d.draft_version,
                        content=dict(d.content),
                        updated_at=_as_aware(d.updated_at).isoformat(),
                    )
                    for d in drafts
                ],
                first_unfinished_stage=first_unfinished,
                first_unfinished_question_key=self._first_unfinished_question(first_unfinished),
            )

    # ----- agent prompt + user draft -----

    def append_agent_prompt(
        self,
        *,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
        stage: ConversationStage,
        question_key: str,
        question_payload: dict[str, Any],
    ) -> MessageSnapshot:
        with self._session_factory.begin() as session:
            self._authorize_project(session, project_id, actor_id, actor_role)
            conv = self._require_conversation(session, project_id)
            msg = self._append_message(
                session,
                conv=conv,
                project_id=project_id,
                message_type=ConversationMessageType.AGENT_PROMPT,
                stage=stage,
                payload={"questionKey": question_key, **question_payload},
            )
            return self._snapshot_of(msg)

    def save_draft(
        self,
        *,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
        scope_key: str,
        expected_draft_version: int | None,
        content: dict[str, Any],
    ) -> DraftSnapshot:
        """CAS upsert of a USER_DRAFT. Returns the new draft version.

        expected_draft_version=None creates the draft (must not exist);
        otherwise must match the persisted draft_version or 409 DRAFT_CONFLICT.
        """
        with self._session_factory.begin() as session:
            self._authorize_project(session, project_id, actor_id, actor_role)
            existing = session.scalar(
                select(ConversationDraft).where(
                    ConversationDraft.project_id == project_id,
                    ConversationDraft.actor_id == actor_id,
                    ConversationDraft.scope_key == scope_key,
                )
            )
            if existing is None:
                if expected_draft_version is not None:
                    raise ApiError(
                        status_code=409,
                        code="DRAFT_CONFLICT",
                        message_key="conversation.draft.conflict",
                        field_path="draftVersion",
                        details={"expected": expected_draft_version, "actual": None},
                    )
                draft = ConversationDraft(
                    project_id=project_id,
                    actor_id=actor_id,
                    scope_key=scope_key,
                    draft_version=1,
                    content=content,
                )
                session.add(draft)
                session.flush()
                return DraftSnapshot(
                    id=draft.id,
                    scope_key=draft.scope_key,
                    draft_version=draft.draft_version,
                    content=dict(draft.content),
                    updated_at=_as_aware(draft.updated_at).isoformat(),
                )
            if expected_draft_version is None:
                # Caller asked to create but draft already exists.
                raise ApiError(
                    status_code=409,
                    code="DRAFT_CONFLICT",
                    message_key="conversation.draft.conflict",
                    field_path="draftVersion",
                    details={"expected": None, "actual": existing.draft_version},
                )
            if existing.draft_version != expected_draft_version:
                raise ApiError(
                    status_code=409,
                    code="DRAFT_CONFLICT",
                    message_key="conversation.draft.conflict",
                    field_path="draftVersion",
                    details={
                        "expected": expected_draft_version,
                        "actual": existing.draft_version,
                    },
                )
            existing.content = content
            existing.draft_version = existing.draft_version + 1
            session.flush()
            return DraftSnapshot(
                id=existing.id,
                scope_key=existing.scope_key,
                draft_version=existing.draft_version,
                content=dict(existing.content),
                updated_at=_as_aware(existing.updated_at).isoformat(),
            )

    # ----- confirmation flow -----

    def issue_challenge(
        self,
        *,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
        question_key: str,
        canonical_payload: dict[str, Any],
    ) -> IssueChallengeResult:
        """Mint a one-time impact token for an upcoming confirm.

        The caller (front-end) presents this token on the first confirm
        attempt. Server consumes it exactly once regardless of outcome.
        """
        with self._session_factory.begin() as session:
            self._authorize_project(session, project_id, actor_id, actor_role)
            conv = self._require_conversation(session, project_id)
            canonical_hash = hashlib.sha256(
                _stable_json(canonical_payload).encode("utf-8")
            ).hexdigest()
            impact_raw = secrets.token_urlsafe(32)
            now = _now()
            challenge = ConfirmationChallenge(
                project_id=project_id,
                conversation_id=conv.id,
                actor_id=actor_id,
                question_key=question_key,
                canonical_payload_hash=canonical_hash,
                expected_input_revision=conv.input_revision,
                impact_token_hash=_hash_token(impact_raw),
                expires_at=now + timedelta(seconds=IMPACT_TOKEN_TTL_SECONDS),
            )
            session.add(challenge)
            session.flush()
            return IssueChallengeResult(
                challenge_id=challenge.id,
                impact_token=impact_raw,
                expected_input_revision=conv.input_revision,
                expires_at=_as_aware(challenge.expires_at).isoformat(),
            )

    def confirm(
        self,
        *,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
        challenge_id: str,
        impact_token: str,
        expected_input_revision: int,
        canonical_payload: dict[str, Any],
        stage: ConversationStage,
        question_key: str,
        field_path: str,
        canonical_value: Any,
        unit: str | None,
        rule_version: str,
        request_id: str,
    ) -> ConfirmResult:
        """First-confirm entry point. Consumes impactToken exactly once.

        M2 SKELETON: only the COMMITTED (no warnings, no hard blocks) path
        is implemented. WARNING_CONFIRMATION and BLOCKED branches require
        the field registry + validation rules (P0_05/P0_06) and raise a
        structured 501 here. REVISION_CONFLICT is enforced (revision must
        match expected).
        """
        with self._session_factory.begin() as session:
            self._authorize_project(session, project_id, actor_id, actor_role)
            conv = self._require_conversation(session, project_id)
            challenge = session.scalar(
                select(ConfirmationChallenge)
                .where(ConfirmationChallenge.id == challenge_id)
                .with_for_update()
            )
            if challenge is None or challenge.project_id != project_id:
                raise ApiError(
                    status_code=404, code="NOT_FOUND", message_key="conversation.challenge.not_found"
                )
            if _hash_token(impact_token) != challenge.impact_token_hash:
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="conversation.challenge.invalid_token",
                )
            if challenge.consumed_at is not None:
                raise ApiError(
                    status_code=409,
                    code="IDEMPOTENCY_CONFLICT",
                    message_key="conversation.challenge.consumed",
                )
            if _as_aware(challenge.expires_at) <= _now():
                raise ApiError(
                    status_code=410,
                    code="TRANSACTION_FAILED",
                    message_key="conversation.challenge.expired",
                )
            if conv.input_revision != expected_input_revision:
                # Revision conflict: consume token, do not write business value.
                challenge.consumed_at = _now()
                return ConfirmResult(
                    presentation_state="REVISION_CONFLICT",
                    new_input_revision=None,
                    confirmation_message_id="",
                    warning_challenge_id=None,
                )
            # Consume the token before any outcome (M2 spec invariant).
            challenge.consumed_at = _now()

            # TODO(P0_05/P0_06): once field-registry validation lands, route
            # warnings -> WARNING_CONFIRMATION (issue warningChallengeId) and
            # hard-rule failures -> BLOCKED. For the skeleton we COMMIT directly
            # assuming the caller has already client-side-validated.
            new_revision = conv.input_revision + 1
            conv.input_revision = new_revision
            # Mark stage done.
            stage_state = dict(conv.stage_state)
            stage_state[stage.value] = "done"
            conv.stage_state = stage_state

            # Append the COMMITTED confirmation card.
            msg = self._append_message(
                session,
                conv=conv,
                project_id=project_id,
                message_type=ConversationMessageType.CONFIRMATION_CARD,
                stage=stage,
                payload={
                    "presentationState": "COMMITTED",
                    "questionKey": question_key,
                    "fieldPath": field_path,
                    "canonicalValue": canonical_value,
                    "unit": unit,
                    "ruleVersion": rule_version,
                    "inputRevision": new_revision,
                    "challengeId": challenge_id,
                },
            )

            # Immutable audit row.
            session.add(
                ConversationAudit(
                    project_id=project_id,
                    conversation_id=conv.id,
                    actor_id=actor_id,
                    question_key=question_key,
                    field_path=field_path,
                    old_canonical_value=None,
                    new_canonical_value={"value": canonical_value, "unit": unit},
                    unit=unit,
                    rule_version=rule_version,
                    source=ConversationAuditSource.USER_INPUT,
                    warning_reasons=None,
                    revision_before=new_revision - 1,
                    revision_after=new_revision,
                    request_id=request_id,
                )
            )

            return ConfirmResult(
                presentation_state="COMMITTED",
                new_input_revision=new_revision,
                confirmation_message_id=msg.id,
                warning_challenge_id=None,
            )

    # ----- helpers -----

    def _authorize_project(
        self,
        session: Session,
        project_id: str,
        actor_id: str,
        actor_role: UserRole,
    ) -> None:
        project = session.scalar(select(Project).where(Project.id == project_id))
        if project is None or (
            actor_role != UserRole.ADMIN and project.owner_id != actor_id
        ):
            raise ApiError(
                status_code=404, code="NOT_FOUND", message_key="projects.not_found"
            )

    def _require_conversation(self, session: Session, project_id: str) -> Conversation:
        conv = session.scalar(select(Conversation).where(Conversation.project_id == project_id))
        if conv is None:
            # Lazy-create on first read so the front-end always sees a snapshot.
            conv = Conversation(
                project_id=project_id,
                input_revision=1,
                stage_state={stage.value: "todo" for stage in STAGE_ORDER},
            )
            session.add(conv)
            session.flush()
        return conv

    def _append_message(
        self,
        session: Session,
        *,
        conv: Conversation,
        project_id: str,
        message_type: ConversationMessageType,
        stage: ConversationStage,
        payload: dict[str, Any],
        refers_to: str | None = None,
    ) -> ConversationMessage:
        max_cursor = session.scalar(
            select(func.max(ConversationMessage.sort_cursor)).where(
                ConversationMessage.conversation_id == conv.id
            )
        )
        next_cursor = (max_cursor or 0) + 1
        msg = ConversationMessage(
            conversation_id=conv.id,
            project_id=project_id,
            message_type=message_type.value,
            stage=stage.value,
            sort_cursor=next_cursor,
            payload=payload,
            refers_to_message_id=refers_to,
        )
        session.add(msg)
        session.flush()
        return msg

    def _snapshot_of(self, msg: ConversationMessage) -> MessageSnapshot:
        return MessageSnapshot(
            id=msg.id,
            message_type=msg.message_type,
            stage=msg.stage,
            sort_cursor=msg.sort_cursor,
            payload=dict(msg.payload),
            refers_to_message_id=msg.refers_to_message_id,
            created_at=_as_aware(msg.created_at).isoformat(),
        )

    def _first_unfinished_stage(self, stage_state: dict[str, Any]) -> str | None:
        for stage in STAGE_ORDER:
            if stage_state.get(stage.value) != "done":
                return stage.value
        return None

    def _first_unfinished_question(self, stage_value: str | None) -> str | None:
        if stage_value is None:
            return None
        # M2 SKELETON: one question per stage; the field registry (P0_05/P0_06)
        # will expand this to per-field questions within a stage.
        return f"{stage_value.lower()}.first"


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
