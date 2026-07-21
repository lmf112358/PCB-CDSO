from __future__ import annotations

from pcb_cdso.tasks.celery_app import celery_app


@celery_app.task(name="pcb_cdso.tasks.smoke", ignore_result=False)  # type: ignore[untyped-decorator]
def smoke(request_id: str) -> dict[str, str]:
    return {"status": "ok", "request_id": request_id}
