import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.engine.executor import PipelineError, check_runnable
from app.jobs import EnqueueError, enqueue_run
from app.models import Run, RunStatus, User
from app.pagination import paginate
from app.rate_limit import rate_limit_per_user
from app.routers.pipelines import get_owned_pipeline
from app.schemas import Graph, Page, RunCreate, RunOut
from app.security import get_current_user

router = APIRouter(prefix="/runs", tags=["runs"])
logger = logging.getLogger(__name__)

ENQUEUE_FAILED_ERROR = "The run could not be queued (job queue unavailable). Please retry."


def enforce_quotas(user: User, db: Session) -> None:
    settings = get_settings()

    if settings.max_active_runs_per_user:
        active = db.scalar(
            select(func.count()).select_from(Run).where(
                Run.owner_id == user.id, Run.status.in_(RunStatus.ACTIVE)
            )
        )
        if active >= settings.max_active_runs_per_user:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"You already have {active} runs in progress; wait for one to finish",
            )

    if settings.daily_token_budget_per_user:
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        used = db.scalar(
            select(func.coalesce(func.sum(Run.input_tokens + Run.output_tokens), 0)).where(
                Run.owner_id == user.id, Run.created_at >= day_start
            )
        )
        if used >= settings.daily_token_budget_per_user:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Daily LLM token budget used up; it resets at midnight UTC",
            )


@router.post(
    "",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit_per_user("runs", "rate_limit_runs"))],
)
def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Run:
    """Queue a run and return immediately; poll GET /runs/{id} for live status."""
    graph = body.graph
    if body.pipeline_id is not None:
        pipeline = get_owned_pipeline(body.pipeline_id, user, db)
        if graph is None:
            graph = Graph.model_validate(pipeline.graph)

    if not graph.nodes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The pipeline is empty")
    try:
        problems = check_runnable(graph, get_settings().max_llm_nodes_per_run)
    except PipelineError as exc:  # cycle
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(problems))

    enforce_quotas(user, db)

    run = Run(
        owner_id=user.id,
        pipeline_id=body.pipeline_id,
        graph=graph.model_dump(),
        inputs=body.inputs,
    )
    db.add(run)
    db.commit()

    try:
        enqueue_run(run.id, background_tasks)
    except EnqueueError as exc:
        logger.exception("Could not enqueue run %s", run.id)
        run.status = RunStatus.FAILED
        run.error = ENQUEUE_FAILED_ERROR
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, ENQUEUE_FAILED_ERROR) from exc
    return run


@router.get("", response_model=Page[RunOut])
def list_runs(
    pipeline_id: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Newest first. Pass `next_cursor` back as `cursor` for the next page."""
    query = select(Run).where(Run.owner_id == user.id)
    if pipeline_id:
        query = query.where(Run.pipeline_id == pipeline_id)
    items, next_cursor = paginate(db, query, Run.created_at, Run.id, limit, cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run
