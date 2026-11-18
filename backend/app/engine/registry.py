"""The one list of node types the backend knows about.

Adding a node type = one NodeSpec here (plus, only if it needs custom UI, one entry in the
frontend's src/nodes/registry.js). The editor reads this catalogue from GET /node-types, so
labels, handles, naming rules, the template regex and which nodes can run are defined once.
"""

import re
from dataclasses import dataclass, field

from app.engine.nodes import (
    DEFAULT_TEMPLATE,
    TEMPLATE_VAR,
    Handler,
    run_input,
    run_llm,
    run_output,
    run_text,
)
from app.schemas import Node

INPUT, OUTPUT, TEXT, LLM = "customInput", "customOutput", "text", "llm"


@dataclass(frozen=True)
class NodeSpec:
    type: str
    label: str
    description: str
    handler: Handler | None  # None: shown in the editor, not executable yet
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    dynamic_inputs: bool = False  # inputs come from {{variables}} in the node's text
    name_field: str | None = None  # data field holding a user-facing name (input/output)
    name_prefix: str | None = None  # default name = prefix + numeric suffix of the node id
    default_data: dict = field(default_factory=dict)  # data a new node starts with

    @property
    def executable(self) -> bool:
        return self.handler is not None


NODE_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec(
        INPUT, "Input", "A value you type in when starting a run.", run_input,
        outputs=("value",), name_field="inputName", name_prefix="input_",
    ),
    NodeSpec(
        LLM, "LLM", "Calls Claude with a prompt and optional system prompt.", run_llm,
        inputs=("system", "prompt"), outputs=("response",),
    ),
    NodeSpec(
        OUTPUT, "Output", "Collects a value as a named run result.", run_output,
        inputs=("value",), name_field="outputName", name_prefix="output_",
    ),
    NodeSpec(
        TEXT, "Text", "A template; each {{variable}} becomes an input.", run_text,
        outputs=("output",), dynamic_inputs=True, default_data={"text": DEFAULT_TEMPLATE},
    ),
    NodeSpec("api", "API", "HTTP request.", None, inputs=("input",), outputs=("output",)),
    NodeSpec("database", "Database", "Database query.", None,
             inputs=("query",), outputs=("result",)),
    NodeSpec("email", "Email", "Send an email.", None, inputs=("message",), outputs=("sent",)),
    NodeSpec("filter", "Filter", "Filter data.", None, inputs=("input",), outputs=("output",)),
    NodeSpec("math", "Math", "Math operation.", None, inputs=("input",), outputs=("result",)),
)

REGISTRY: dict[str, NodeSpec] = {spec.type: spec for spec in NODE_SPECS}

_TRAILING_NUMBER = re.compile(r"(\d+)$")


def default_name(spec: NodeSpec, node_id: str) -> str:
    """input_3 for node 'customInput-3'. Mirrored by defaultName() in the frontend."""
    match = _TRAILING_NUMBER.search(node_id)
    return f"{spec.name_prefix}{match.group(1) if match else node_id}"


def node_name(node: Node) -> str:
    """The effective name of an input/output node: its own name, or the default if blank."""
    spec = REGISTRY[node.type]
    value = node.data.get(spec.name_field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default_name(spec, node.id)


def catalog(default_model: str, allowed_models: list[str]) -> dict:
    return {
        "template_variable_pattern": TEMPLATE_VAR.pattern,
        "default_model": default_model,
        "allowed_models": allowed_models,
        "node_types": [
            {
                "type": spec.type,
                "label": spec.label,
                "description": spec.description,
                "executable": spec.executable,
                "inputs": list(spec.inputs),
                "outputs": list(spec.outputs),
                "dynamic_inputs": spec.dynamic_inputs,
                "name_field": spec.name_field,
                "name_prefix": spec.name_prefix,
                "default_data": dict(spec.default_data),
            }
            for spec in NODE_SPECS
        ],
    }
