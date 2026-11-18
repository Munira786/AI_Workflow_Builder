from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.graph import is_dag
from app.models import Pipeline, User
from app.schemas import (
    Graph,
    ParseResult,
    PipelineCreate,
    PipelineOut,
    PipelineSummary,
    PipelineUpdate,
)
from app.security import get_current_user

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("/parse", response_model=ParseResult)
def parse_pipeline(graph: Graph) -> ParseResult:
    return ParseResult(num_nodes=len(graph.nodes), num_edges=len(graph.edges), is_dag=is_dag(graph))


def get_owned_pipeline(pipeline_id: str, user: User, db: Session) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    # 404 (not 403) for other users' pipelines, so ids can't be probed.
    if pipeline is None or pipeline.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pipeline not found")
    return pipeline


@router.get("", response_model=list[PipelineSummary])
def list_pipelines(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Pipeline]:
    query = (
        select(Pipeline).where(Pipeline.owner_id == user.id).order_by(Pipeline.updated_at.desc())
    )
    return list(db.scalars(query))


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    body: PipelineCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Pipeline:
    pipeline = Pipeline(owner_id=user.id, name=body.name, graph=body.graph.model_dump())
    db.add(pipeline)
    db.commit()
    return pipeline


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Pipeline:
    return get_owned_pipeline(pipeline_id, user, db)


@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pipeline:
    pipeline = get_owned_pipeline(pipeline_id, user, db)
    if body.name is not None:
        pipeline.name = body.name
    if body.graph is not None:
        pipeline.graph = body.graph.model_dump()
    db.commit()
    return pipeline


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    pipeline_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    db.delete(get_owned_pipeline(pipeline_id, user, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
