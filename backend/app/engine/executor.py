"""Runs a whole pipeline: nodes execute in topological order, outputs flow along edges."""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.engine.nodes import HANDLERS, NodeContext, NodeError, default_output_name
from app.graph import topological_order
from app.schemas import Graph, Node

MAX_STORED_OUTPUT_CHARS = 20_000

# Called with (node_id, state) whenever a node changes status.
StateCallback = Callable[[str, dict], None]


class PipelineError(Exception):
    pass


@dataclass
class ExecutionResult:
    outputs: dict[str, str] = field(default_factory=dict)
    node_states: dict[str, dict] = field(default_factory=dict)


def handle_name(node_id: str, handle: str | None, fallback: str) -> str:
    """React Flow handles are named '<node id>-<handle>'; strip the node id prefix."""
    if not handle:
        return fallback
    prefix = f"{node_id}-"
    return handle[len(prefix):] if handle.startswith(prefix) else handle


def _preview(value: str) -> str:
    if len(value) <= MAX_STORED_OUTPUT_CHARS:
        return value
    return value[:MAX_STORED_OUTPUT_CHARS] + "… [truncated]"


def execute_pipeline(
    graph: Graph,
    run_inputs: dict[str, str],
    on_state: StateCallback | None = None,
) -> ExecutionResult:
    order = topological_order(graph)
    if order is None:
        raise PipelineError("The pipeline contains a cycle, so it cannot be executed")

    nodes: dict[str, Node] = {node.id: node for node in graph.nodes}
    unsupported = sorted({n.type or "unknown" for n in graph.nodes if n.type not in HANDLERS})
    if unsupported:
        raise PipelineError(
            "These node types cannot be executed yet: " + ", ".join(unsupported)
        )

    result = ExecutionResult()

    def set_state(node_id: str, state: dict) -> None:
        result.node_states[node_id] = state
        if on_state:
            on_state(node_id, state)

    for node_id in order:
        set_state(node_id, {"status": "pending"})

    values: dict[str, str] = {}  # node id -> output value

    for node_id in order:
        node = nodes[node_id]
        inputs: dict[str, list[str]] = {}
        for edge in graph.edges:
            if edge.target == node_id:
                name = handle_name(node_id, edge.targetHandle, "input")
                inputs.setdefault(name, []).append(values[edge.source])

        set_state(node_id, {"status": "running"})
        ctx = NodeContext(
            node=node,
            inputs={name: "\n".join(parts) for name, parts in inputs.items()},
            run_inputs=run_inputs,
        )
        try:
            value = HANDLERS[node.type](ctx)
        except NodeError as exc:
            set_state(node_id, {"status": "failed", "error": str(exc)})
            raise PipelineError(f"Node '{node_id}' failed: {exc}") from exc

        values[node_id] = value
        set_state(node_id, {"status": "succeeded", "output": _preview(value)})

        if node.type == "customOutput":
            name = node.data.get("outputName") or default_output_name(node)
            result.outputs[name] = value

    return result
