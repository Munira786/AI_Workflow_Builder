from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.config import get_settings


def _assume_utc(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; without an offset, browsers would read them as
    # local time. Everything is stored in UTC, so say so explicitly in the JSON.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


UTCDateTime = Annotated[datetime, AfterValidator(_assume_utc)]

# bcrypt only uses the first 72 BYTES of a password (and bcrypt>=5 raises beyond that).
# Multi-byte characters count several times, so the limit is checked on the UTF-8 encoding.
MAX_PASSWORD_BYTES = 72


class Node(BaseModel):
    """A React Flow node. Unknown fields (position, width, selected, ...) are kept as-is."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=200)
    type: str | None = Field(default=None, max_length=100)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def limit_field_sizes(cls, data: dict[str, Any]) -> dict[str, Any]:
        limit = get_settings().max_field_chars
        for key, value in data.items():
            if isinstance(value, str) and len(value) > limit:
                raise ValueError(f"Node field '{key}' is longer than {limit} characters")
        return data


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


# ---- Node type catalogue (single source of truth for the editor) ----

class NodeTypeOut(BaseModel):
    type: str
    label: str
    description: str
    executable: bool
    inputs: list[str]
    outputs: list[str]
    dynamic_inputs: bool
    name_field: str | None
    name_prefix: str | None
    default_data: dict[str, Any]


class NodeCatalogOut(BaseModel):
    template_variable_pattern: str
    default_model: str
    allowed_models: list[str]
    node_types: list[NodeTypeOut]


# ---- Auth ----

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password is too long (at most {MAX_PASSWORD_BYTES} bytes; "
                "accented letters and emoji count as several)"
            )
        return password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: UTCDateTime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Pagination ----

class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


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
    created_at: UTCDateTime
    updated_at: UTCDateTime


class PipelineOut(PipelineSummary):
    graph: Graph


# ---- Runs ----

class RunCreate(BaseModel):
    """Run a saved pipeline (pipeline_id), an editor graph (graph), or both.

    With both, the given graph is executed (e.g. unsaved edits) and the run is linked to the
    saved pipeline for history.
    """

    pipeline_id: str | None = Field(default=None, min_length=1, max_length=36)
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
    pipeline_name: str | None = None  # None when unsaved or the pipeline was deleted
    status: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    node_states: dict[str, Any]
    error: str | None
    input_tokens: int
    output_tokens: int
    created_at: UTCDateTime
    started_at: UTCDateTime | None
    finished_at: UTCDateTime | None
