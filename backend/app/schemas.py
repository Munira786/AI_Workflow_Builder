from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.config import get_settings


class Node(BaseModel):
    """A React Flow node. Unknown fields (position, width, selected, ...) are kept as-is."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=200)
    type: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    sourceHandle: str | None = None
    targetHandle: str | None = None


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_graph(self) -> "Graph":
        settings = get_settings()
        if len(self.nodes) > settings.max_nodes:
            raise ValueError(f"A pipeline can have at most {settings.max_nodes} nodes")
        if len(self.edges) > settings.max_edges:
            raise ValueError(f"A pipeline can have at most {settings.max_edges} edges")

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node ids must be unique")

        known = set(node_ids)
        for edge in self.edges:
            missing = [end for end in (edge.source, edge.target) if end not in known]
            if missing:
                raise ValueError(f"Edge references unknown node(s): {', '.join(missing)}")
        return self


class ParseResult(BaseModel):
    num_nodes: int
    num_edges: int
    is_dag: bool


# ---- Auth ----

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Pipelines ----

class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    graph: Graph


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    graph: Graph | None = None


class PipelineSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class PipelineOut(PipelineSummary):
    graph: Graph


# ---- Runs ----

class RunCreate(BaseModel):
    """Run a saved pipeline (pipeline_id), an editor graph (graph), or both.

    With both, the given graph is executed (e.g. unsaved edits) and the run is linked to the
    saved pipeline for history.
    """

    pipeline_id: str | None = None
    graph: Graph | None = None
    inputs: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def has_source(self) -> "RunCreate":
        if self.pipeline_id is None and self.graph is None:
            raise ValueError("Provide pipeline_id, graph, or both")
        return self


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pipeline_id: str | None
    status: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    node_states: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
