"""GET /tasks and GET /tasks/{task_id}.

M2 task dock and tool cards consume these. Returns persisted Task state;
scope is enforced by actor (ENGINEER sees own; ADMIN sees all). Anti-
enumeration: cross-owner existing id and random unknown id both return
indistinguishable 404.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from pcb_cdso.db.models import Task, User, UserRole
from pcb_cdso.http.auth import ActorContext
from pcb_cdso.http.tasks import TaskEnvelope
from pcb_cdso.http.errors import ApiError, ErrorEnvelope
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class TaskList(BaseModel):
    items: list[TaskEnvelope]


def _to_envelope(task: Task) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        stage=task.stage or "",
        processed=task.processed,
        total=task.total,
        error=task.error_payload,
        retryable=task.retryable,
    )


def build_tasks_m1_router(
    session_factory: sessionmaker[Session],
    get_actor: callable,  # type: ignore[type-arg]
) -> APIRouter:
    router = APIRouter(tags=["tasks"])

    @router.get(
        "/tasks",
        operation_id="task_list",
        response_model=TaskList,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            403: {"model": ErrorEnvelope, "description": "Cross-owner denied."},
        },
    )
    def list_tasks(
        actor: ActorContext = Depends(get_actor),
        project_id: str | None = Query(default=None, alias="projectId"),
        active_only: bool = Query(default=False, alias="activeOnly"),
    ) -> TaskList:
        with session_factory() as session:
            stmt = select(Task)
            if actor.role != UserRole.ADMIN:
                # ENGINEER: restrict to tasks of own projects.
                own_project_ids = select(User.id)  # placeholder, real filter below
                # Join via project ownership.
                from pcb_cdso.db.models import Project

                stmt = stmt.join(Project, Task.project_id == Project.id).where(
                    Project.owner_id == actor.actor_id
                )
            if project_id is not None:
                # Apply project filter through ownership check first.
                from pcb_cdso.db.models import Project

                proj = session.scalar(select(Project).where(Project.id == project_id))
                if proj is not None:
                    if actor.role != UserRole.ADMIN and proj.owner_id != actor.actor_id:
                        # Treat as not-visible: return empty list (anti-enumeration
                        # for list endpoint: 200 with empty items).
                        return TaskList(items=[])
                stmt = stmt.where(Task.project_id == project_id)
            active_statuses = {"DISPATCH_PENDING", "QUEUED", "RUNNING"}
            if active_only:
                stmt = stmt.where(Task.status.in_(active_statuses))
            tasks = session.scalars(stmt.order_by(Task.created_at.desc())).all()
            return TaskList(items=[_to_envelope(t) for t in tasks])

    @router.get(
        "/tasks/{task_id}",
        operation_id="task_get",
        response_model=TaskEnvelope,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
            403: {"model": ErrorEnvelope, "description": "Within scope but role lacks."},
            404: {"model": ErrorEnvelope, "description": "Not visible or unknown."},
        },
    )
    def get_task(
        task_id: str,
        actor: ActorContext = Depends(get_actor),
    ) -> TaskEnvelope:
        with session_factory() as session:
            task = session.scalar(select(Task).where(Task.id == task_id))
            if task is None:
                raise ApiError(
                    status_code=404,
                    code="NOT_FOUND",
                    message_key="tasks.not_found",
                )
            from pcb_cdso.db.models import Project

            project = session.scalar(select(Project).where(Project.id == task.project_id))
            if project is None:
                raise ApiError(
                    status_code=404,
                    code="NOT_FOUND",
                    message_key="tasks.not_found",
                )
            if actor.role != UserRole.ADMIN and project.owner_id != actor.actor_id:
                # Cross-owner existing id and random unknown id return the
                # same 404 envelope/message (anti-enumeration, M1 spec 9).
                raise ApiError(
                    status_code=404,
                    code="NOT_FOUND",
                    message_key="tasks.not_found",
                )
            return _to_envelope(task)

    return router
