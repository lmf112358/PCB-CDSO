"""M2 conversation HTTP endpoints.

Exposes ConversationService over the contract surface:
- GET  /projects/{projectId}/conversation      consistent snapshot
- POST /projects/{projectId}/conversation/draft CAS upsert of USER_DRAFT
- POST /projects/{projectId}/conversation/challenge  mint impact token
- POST /projects/{projectId}/conversation/confirm    first-confirm (COMMITTED)

The warning-reason and warning-confirm endpoints are out of scope for the
skeleton (TODO once field-registry validation lands per P0_05/P0_06).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.models import ConversationStage, UserRole
from pcb_cdso.domain.conversation import ConversationService
from pcb_cdso.http.auth import ActorContext
from pcb_cdso.http.errors import ErrorEnvelope


class MessageSnapshotModel(BaseModel):
    id: str
    message_type: str
    stage: str
    sort_cursor: int
    payload: dict
    refers_to_message_id: str | None = None
    created_at: str


class DraftSnapshotModel(BaseModel):
    id: str
    scope_key: str
    draft_version: int
    content: dict
    updated_at: str


class ConversationSnapshotModel(BaseModel):
    conversation_id: str
    project_id: str
    input_revision: int
    stage_state: dict
    messages: list[MessageSnapshotModel]
    drafts: list[DraftSnapshotModel]
    first_unfinished_stage: str | None
    first_unfinished_question_key: str | None


class SaveDraftRequest(BaseModel):
    scope_key: str = Field(min_length=1, max_length=128)
    expected_draft_version: int | None = None
    content: dict


class SaveDraftResponse(BaseModel):
    id: str
    scope_key: str
    draft_version: int
    updated_at: str


class IssueChallengeRequest(BaseModel):
    question_key: str = Field(min_length=1, max_length=128)
    canonical_payload: dict


class IssueChallengeResponse(BaseModel):
    challenge_id: str
    impact_token: str
    expected_input_revision: int
    expires_at: str


class ConfirmRequest(BaseModel):
    challenge_id: str
    impact_token: str = Field(min_length=16)
    expected_input_revision: int = Field(ge=0)
    canonical_payload: dict
    stage: str
    question_key: str = Field(min_length=1, max_length=128)
    field_path: str = Field(min_length=1, max_length=128)
    canonical_value: object
    unit: str | None = None
    rule_version: str = Field(min_length=1, max_length=64)


class ConfirmResponse(BaseModel):
    presentation_state: str
    new_input_revision: int | None
    confirmation_message_id: str
    warning_challenge_id: str | None


def build_conversation_router(
    session_factory: sessionmaker[Session],
    conversation_service: ConversationService,
    get_actor: callable,  # type: ignore[type-arg]
) -> APIRouter:
    router = APIRouter(tags=["conversation"])

    @router.get(
        "/projects/{project_id}/conversation",
        operation_id="conversation_get",
        response_model=ConversationSnapshotModel,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            404: {"model": ErrorEnvelope, "description": "Project not visible or unknown."},
        },
    )
    def get_conversation(
        project_id: str = Path(..., alias="project_id"),
        actor: ActorContext = Depends(get_actor),
    ) -> ConversationSnapshotModel:
        snapshot = conversation_service.snapshot(
            project_id=project_id,
            actor_id=actor.actor_id,
            actor_role=UserRole(actor.role),
        )
        return ConversationSnapshotModel(
            conversation_id=snapshot.conversation_id,
            project_id=snapshot.project_id,
            input_revision=snapshot.input_revision,
            stage_state=snapshot.stage_state,
            messages=[
                MessageSnapshotModel(**m.__dict__) for m in snapshot.messages
            ],
            drafts=[DraftSnapshotModel(**d.__dict__) for d in snapshot.drafts],
            first_unfinished_stage=snapshot.first_unfinished_stage,
            first_unfinished_question_key=snapshot.first_unfinished_question_key,
        )

    @router.post(
        "/projects/{project_id}/conversation/draft",
        operation_id="conversation_save_draft",
        response_model=SaveDraftResponse,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            404: {"model": ErrorEnvelope, "description": "Project not visible."},
            409: {"model": ErrorEnvelope, "description": "Draft version conflict."},
        },
    )
    def save_draft(
        body: SaveDraftRequest,
        project_id: str = Path(..., alias="project_id"),
        actor: ActorContext = Depends(get_actor),
    ) -> SaveDraftResponse:
        result = conversation_service.save_draft(
            project_id=project_id,
            actor_id=actor.actor_id,
            actor_role=UserRole(actor.role),
            scope_key=body.scope_key,
            expected_draft_version=body.expected_draft_version,
            content=body.content,
        )
        return SaveDraftResponse(
            id=result.id,
            scope_key=result.scope_key,
            draft_version=result.draft_version,
            updated_at=result.updated_at,
        )

    @router.post(
        "/projects/{project_id}/conversation/challenge",
        operation_id="conversation_issue_challenge",
        response_model=IssueChallengeResponse,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            404: {"model": ErrorEnvelope, "description": "Project not visible."},
        },
    )
    def issue_challenge(
        body: IssueChallengeRequest,
        project_id: str = Path(..., alias="project_id"),
        actor: ActorContext = Depends(get_actor),
    ) -> IssueChallengeResponse:
        result = conversation_service.issue_challenge(
            project_id=project_id,
            actor_id=actor.actor_id,
            actor_role=UserRole(actor.role),
            question_key=body.question_key,
            canonical_payload=body.canonical_payload,
        )
        return IssueChallengeResponse(
            challenge_id=result.challenge_id,
            impact_token=result.impact_token,
            expected_input_revision=result.expected_input_revision,
            expires_at=result.expires_at,
        )

    @router.post(
        "/projects/{project_id}/conversation/confirm",
        operation_id="conversation_confirm",
        response_model=ConfirmResponse,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            404: {"model": ErrorEnvelope, "description": "Project or challenge not found."},
            409: {"model": ErrorEnvelope, "description": "Token already consumed."},
            410: {"model": ErrorEnvelope, "description": "Challenge expired."},
        },
    )
    def confirm(
        request: Request,
        body: ConfirmRequest,
        project_id: str = Path(..., alias="project_id"),
        actor: ActorContext = Depends(get_actor),
    ) -> ConfirmResponse:
        result = conversation_service.confirm(
            project_id=project_id,
            actor_id=actor.actor_id,
            actor_role=UserRole(actor.role),
            challenge_id=body.challenge_id,
            impact_token=body.impact_token,
            expected_input_revision=body.expected_input_revision,
            canonical_payload=body.canonical_payload,
            stage=ConversationStage(body.stage),
            question_key=body.question_key,
            field_path=body.field_path,
            canonical_value=body.canonical_value,
            unit=body.unit,
            rule_version=body.rule_version,
            request_id=getattr(request.state, "request_id", ""),
        )
        return ConfirmResponse(
            presentation_state=result.presentation_state,
            new_input_revision=result.new_input_revision,
            confirmation_message_id=result.confirmation_message_id,
            warning_challenge_id=result.warning_challenge_id,
        )

    return router
