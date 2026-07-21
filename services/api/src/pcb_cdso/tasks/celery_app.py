from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from pcb_cdso.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "pcb_cdso",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["pcb_cdso.tasks.smoke"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    enable_utc=True,
    timezone="UTC",
    task_track_started=True,
    task_soft_time_limit=25,
    task_time_limit=30,
)
