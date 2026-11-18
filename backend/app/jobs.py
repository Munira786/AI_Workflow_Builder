"""Background execution of pipeline runs.

With REDIS_URL set, runs are pushed onto an RQ queue and executed by `rq worker` processes,
so the API stays responsive and workers can be scaled independently. Without Redis (local dev,
tests), runs execute in-process via FastAPI background tasks.
"""

import logging
import time
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import BackgroundTasks
from rq.timeouts import JobTimeoutException

from app.config import get_settings
from app.db import SessionLocal
from app.engine.executor import PipelineError, execute_pipeline, total_usage
from app.maintenance import fail_unfinished_nodes
from app.models import Run, RunStatus
from app.observability import request_id_var, setup_observability
from app.schemas import Graph

logger = logging.getLogger(__name__)


class EnqueueError(Exception):
    """The run could not be handed to the job queue."""


def process_run(run_id: str, request_id: str | None = None) -> None:
    """Execute a run and persist status updates as each node progresses. Safe to call from RQ."""
    setup_observability()  # no-op in the API process; configures logging in RQ workers
    token = request_id_var.set(request_id or f"run-{run_id}")
    started = time.perf_counter()
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
        # Tokens were spent either way, so they always count towards the user's budget.
        run.input_tokens, run.output_tokens = total_usage(run.node_states)
        if run.status != RunStatus.RUNNING:
            logger.warning("Run %s was already %s; discarding late result", run_id, run.status)
            db.commit()
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
        logger.info(
            "Run %s %s",
            run_id,
            run.status,
            extra={
                "run_id": run_id,
                "status": run.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
            },
        )
    finally:
        db.close()
        request_id_var.reset(token)


@lru_cache
def get_queue():
    """One Redis connection pool per process, reused by every enqueue."""
    from redis import Redis
    from rq import Queue

    settings = get_settings()
    connection = Redis.from_url(settings.redis_url, socket_timeout=5, socket_connect_timeout=5)
    return Queue(settings.run_queue_name, connection=connection)


def enqueue_run(run_id: str, background_tasks: BackgroundTasks) -> None:
    settings = get_settings()
    request_id = request_id_var.get()
    if settings.redis_url:
        try:
            get_queue().enqueue(
                process_run, run_id, request_id, job_timeout=settings.run_job_timeout_seconds
            )
        except Exception as exc:
            raise EnqueueError(str(exc)) from exc
    else:
        background_tasks.add_task(process_run, run_id, request_id)
