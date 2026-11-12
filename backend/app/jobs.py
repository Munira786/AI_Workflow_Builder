"""Background execution of pipeline runs.

With REDIS_URL set, runs are pushed onto an RQ queue and executed by `rq worker` processes,
so the API stays responsive and workers can be scaled independently. Without Redis (local dev,
tests), runs execute in-process via FastAPI background tasks.
"""

import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from rq.timeouts import JobTimeoutException

from app.config import get_settings
from app.db import SessionLocal
from app.engine.executor import PipelineError, execute_pipeline
from app.maintenance import fail_unfinished_nodes
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

        outputs: dict = {}
        error: str | None = None
        try:
            result = execute_pipeline(Graph.model_validate(run.graph), run.inputs, on_state)
            outputs = result.outputs
        except PipelineError as exc:
            error = str(exc)
        except JobTimeoutException:
            # RQ interrupts the job when it exceeds run_job_timeout_seconds.
            error = f"The run timed out after {get_settings().run_job_timeout_seconds} seconds"
        except Exception:
            logger.exception("Run %s crashed", run_id)
            error = "Internal error while executing the pipeline"

        # Re-read the row: if the reaper (app/maintenance.py) already gave up on this run,
        # keep its verdict instead of overwriting it with a late result.
        db.refresh(run)
        if run.status != RunStatus.RUNNING:
            logger.warning("Run %s was already %s; discarding late result", run_id, run.status)
            return

        if error is None:
            run.status = RunStatus.SUCCEEDED
            run.outputs = outputs
        else:
            run.status = RunStatus.FAILED
            run.error = error
            run.node_states = fail_unfinished_nodes(run.node_states, error)
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
