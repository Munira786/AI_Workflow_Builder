"""Runs a whole pipeline: nodes execute in topological order, outputs flow along edges."""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.engine.nodes import NodeContext, NodeError
from app.engine.registry import INPUT, LLM, OUTPUT, REGISTRY, node_name
from app.graph import topological_order
from app.schemas import Graph, Node

MAX_STORED_OUTPUT_CHARS = 20_000
HANDLE_SEPARATOR = "-"  # React Flow handle ids are '<node id>-<handle name>'

# Called with (node_id, state) whenever a node changes status.
StateCallback = Callable[[str, dict], None]


class PipelineError(Exception):
    pass


@dataclass
class ExecutionResult:
    outputs: dict[str, str] = field(default_factory=dict)
    node_states: dict[str, dict] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    order: list[str]  # every node, topologically sorted
    to_run: set[str]  # the nodes that will actually execute


def handle_name(node_id: str, handle: str | None, fallback: str) -> str:
    """Strip the '<node id>-' prefix from a React Flow handle id."""
    if not handle:
        return fallback
    prefix = f"{node_id}{HANDLE_SEPARATOR}"
    return handle[len(prefix):] if handle.startswith(prefix) else handle


def _preview(value: str) -> str:
    if len(value) <= MAX_STORED_OUTPUT_CHARS:
        return value
    return value[:MAX_STORED_OUTPUT_CHARS] + "… [truncated]"


def plan_execution(graph: Graph) -> ExecutionPlan:
    """Decide what runs.

    With Output nodes present, only the nodes that feed an Output run: a stray node left on the
    canvas (an unconnected Text or LLM node) is skipped instead of failing the run or spending
    tokens. Without any Output node, everything runs, so a pipeline can still be tried out.
    """
    order = topological_order(graph)
    if order is None:
        raise PipelineError("The pipeline contains a cycle, so it cannot be executed")

    outputs = [node.id for node in graph.nodes if node.type == OUTPUT]
    if not outputs:
        return ExecutionPlan(order, set(order))

    parents: dict[str, list[str]] = {}
    for edge in graph.edges:
        parents.setdefault(edge.target, []).append(edge.source)
    needed: set[str] = set()
    stack = list(outputs)
    while stack:
        node_id = stack.pop()
        if node_id not in needed:
            needed.add(node_id)
            stack.extend(parents.get(node_id, []))
    return ExecutionPlan(order, needed)


def check_runnable(graph: Graph, max_llm_nodes: int = 0) -> list[str]:
    """Problems that make a pipeline impossible to run, found before anything executes."""
    plan = plan_execution(graph)
    nodes = [node for node in graph.nodes if node.id in plan.to_run]
    problems: list[str] = []

    unsupported = sorted({
        n.type or "unknown" for n in nodes
        if n.type not in REGISTRY or not REGISTRY[n.type].executable
    })
    if unsupported:
        problems.append("These node types cannot be executed yet: " + ", ".join(unsupported))

    for node_type, kind in ((INPUT, "input"), (OUTPUT, "output")):
        names = [node_name(n) for n in nodes if n.type == node_type]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            problems.append(f"Two or more {kind} nodes share the name: {', '.join(duplicates)}")

    llm_count = sum(1 for n in nodes if n.type == LLM)
    if max_llm_nodes and llm_count > max_llm_nodes:
        problems.append(
            f"A run can use at most {max_llm_nodes} LLM nodes (this one has {llm_count})"
        )
    return problems


def execute_pipeline(
    graph: Graph,
    run_inputs: dict[str, str],
    on_state: StateCallback | None = None,
) -> ExecutionResult:
    plan = plan_execution(graph)
    problems = check_runnable(graph)
    if problems:
        raise PipelineError("; ".join(problems))

    nodes: dict[str, Node] = {node.id: node for node in graph.nodes}
    result = ExecutionResult()

    def set_state(node_id: str, state: dict) -> None:
        result.node_states[node_id] = state
        if on_state:
            on_state(node_id, state)

    for node_id in plan.order:
        set_state(node_id, {"status": "pending" if node_id in plan.to_run else "skipped"})

    values: dict[str, str] = {}  # node id -> output value

    for node_id in plan.order:
        if node_id not in plan.to_run:
            continue
        node = nodes[node_id]
        spec = REGISTRY[node.type]
        inputs: dict[str, list[str]] = {}
        for edge in graph.edges:
            if edge.target == node_id and edge.source in values:
                name = handle_name(node_id, edge.targetHandle, "input")
                inputs.setdefault(name, []).append(values[edge.source])

        set_state(node_id, {"status": "running"})
        ctx = NodeContext(
            node=node,
            inputs={name: "\n".join(parts) for name, parts in inputs.items()},
            run_inputs=run_inputs,
            name=node_name(node) if spec.name_field else None,
        )
        try:
            value = spec.handler(ctx)
        except NodeError as exc:
            state = {"status": "failed", "error": str(exc)}
            if ctx.usage:
                state["usage"] = ctx.usage
            set_state(node_id, state)
            raise PipelineError(f"Node '{node_id}' failed: {exc}") from exc

        values[node_id] = value
        state = {"status": "succeeded", "output": _preview(value)}
        if ctx.usage:
            state["usage"] = ctx.usage
        set_state(node_id, state)

        if node.type == OUTPUT:
            result.outputs[ctx.name] = value

    return result


def total_usage(node_states: dict) -> tuple[int, int]:
    """Sum the token usage recorded on node states: (input_tokens, output_tokens)."""
    input_tokens = output_tokens = 0
    for state in (node_states or {}).values():
        usage = state.get("usage") or {}
        input_tokens += int(usage.get("input_tokens", 0))
        output_tokens += int(usage.get("output_tokens", 0))
    return input_tokens, output_tokens
