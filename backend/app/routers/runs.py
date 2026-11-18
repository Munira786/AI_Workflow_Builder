from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.graph import is_dag
from app.jobs import enqueue_run
from app.models import Run, User
from app.routers.pipelines import get_owned_pipeline
from app.schemas import Graph, RunCreate, RunOut
from app.security import get_current_user

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Run:
    """Queue a run and return immediately; poll GET /runs/{id} for live status."""
    graph = body.graph
    if body.pipeline_id:
        pipeline = get_owned_pipeline(body.pipeline_id, user, db)
        if graph is None:
            graph = Graph.model_validate(pipeline.graph)

    if not graph.nodes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The pipeline is empty")
    if not is_dag(graph):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The pipeline contains a cycle"
        )

    run = Run(
        owner_id=user.id,
        pipeline_id=body.pipeline_id,
        graph=graph.model_dump(),
        inputs=body.inputs,
    )
    db.add(run)
    db.commit()
    enqueue_run(run.id, background_tasks)
    return run


@router.get("", response_model=list[RunOut])
def list_runs(
    pipeline_id: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Run]:
    query = select(Run).where(Run.owner_id == user.id)
    if pipeline_id:
        query = query.where(Run.pipeline_id == pipeline_id)
    query = query.order_by(Run.created_at.desc()).limit(min(max(limit, 1), 100))
    return list(db.scalars(query))


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run
