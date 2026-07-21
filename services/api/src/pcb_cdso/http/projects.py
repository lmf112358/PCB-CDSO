"""POST /projects HTTP adapter over ProjectService.

The body intentionally excludes actorId and idempotencyKey fields; those
come from the Authorization-derived ActorContext and the Idempotency-Key
header respectively. A request body carrying actorId is silently ignored
and recorded (M1 feature spec line 45).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, Field

from pcb_cdso.domain.projects import CreateProjectCommand, ProjectService
from pcb_cdso.http.auth import ActorContext
from pcb_cdso.http.errors import ErrorEnvelope


class CreateProjectRequest(BaseModel):
    """CreateProject command body. actorId is intentionally absent."""

    name: str = Field(min_length=1, max_length=120)
    templateVersionId: str = Field(min_length=1)
    countryCode: str = Field(pattern=r"^[A-Z]{2}$")
    adminArea: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1)


class ProjectSummary(BaseModel):
    id: str
    name: str
    owner_id: str
    template_version_id: str
    country_code: str
    admin_area: str
    city: str
    timezone: str
    status: str
    created_at: str


class CreateProjectResponse(BaseModel):
    project: ProjectSummary
    inputRevision: int
    snapshotIds: list[str]
    weatherTaskId: str


def build_projects_router(
    project_service: ProjectService,
    get_actor: callable,  # type: ignore[type-arg]
) -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])

    @router.post(
        "",
        operation_id="project_create",
        response_model=CreateProjectResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            200: {"model": CreateProjectResponse, "description": "Idempotent replay"},
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            403: {"model": ErrorEnvelope, "description": "Role not ENGINEER/ADMIN."},
            404: {"model": ErrorEnvelope, "description": "templateVersionId not found/visible."},
            409: {"model": ErrorEnvelope, "description": "Idempotency-Key bound to different hash."},
            422: {"description": "Validation Error"},
            503: {"model": ErrorEnvelope, "description": "Transaction failed; retry with same key."},
        },
    )
    def create_project(
        request: Request,
        body: CreateProjectRequest,
        idempotency_key: str = Header(..., min_length=1, max_length=128),
        actor: ActorContext = Depends(get_actor),
    ) -> Response:
        cmd = CreateProjectCommand.from_raw(
            name=body.name,
            template_version_id=body.templateVersionId,
            country_code=body.countryCode,
            admin_area=body.adminArea,
            city=body.city,
            timezone=body.timezone,
            actor_id=actor.actor_id,
            idempotency_key=idempotency_key,
        )
        result = project_service.create_project(cmd, actor_role=actor.role)
        response_body = CreateProjectResponse(
            project=ProjectSummary(
                id=result.project_id,
                name=result.name,
                owner_id=result.owner_id,
                template_version_id=result.template_version_id,
                country_code=result.country_code,
                admin_area=result.admin_area,
                city=result.city,
                timezone=result.timezone,
                status="ACTIVE",
                created_at="",
            ),
            inputRevision=result.input_revision,
            snapshotIds=result.snapshot_ids,
            weatherTaskId=result.weather_task_id,
        )
        # 200 for replay, 201 for first creation.
        status_code = status.HTTP_200_OK if result.is_replay else status.HTTP_201_CREATED
        return Response(
            content=response_body.model_dump_json(),
            media_type="application/json",
            status_code=status_code,
        )

    return router
