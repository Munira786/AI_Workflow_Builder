"""Background execution of pipeline runs.

With REDIS_URL set, runs are pushed onto an RQ queue and executed by `rq worker` processes,
so the API stays responsive and workers can be scaled independently. Without Redis (local dev,
tests), runs execute in-process via FastAPI background tasks.
"""

import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks

from app.config import get_settings
from app.db import SessionLocal
from app.engine.executor import PipelineError, execute_pipeline
from app.models import Run, RunStatus
from app.schemas import Graph

logger = logging.getLogger(__name__)


def process_run(run_id: str) -> None:
    """Execute a run and persist status updates as each node progresses. Safe to call from RQ."""
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None or run.status in RunStatus.TERMINAL:
            return

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        db.commit()

        def on_state(node_id: str, state: dict) -> None:
            # Reassign a new dict so SQLAlchemy detects the change on the JSON column.
            run.node_states = {**run.node_states, node_id: state}
            db.commit()

        try:
            result = execute_pipeline(Graph.model_validate(run.graph), run.inputs, on_state)
        except PipelineError as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
        except Exception:
            logger.exception("Run %s crashed", run_id)
            run.status = RunStatus.FAILED
            run.error = "Internal error while executing the pipeline"
        else:
            run.status = RunStatus.SUCCEEDED
            run.outputs = result.outputs

        run.finished_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()


def enqueue_run(run_id: str, background_tasks: BackgroundTasks) -> None:
    settings = get_settings()
    if settings.redis_url:
        from redis import Redis
        from rq import Queue

        queue = Queue(settings.run_queue_name, connection=Redis.from_url(settings.redis_url))
        queue.enqueue(process_run, run_id, job_timeout=settings.run_job_timeout_seconds)
    else:
        background_tasks.add_task(process_run, run_id)
