"""Handlers that execute a single node.

Each handler receives the node, the values arriving on its input handles, and the run inputs,
and returns the node's output value (a string). Raise NodeError for user-facing failures.
Node metadata (labels, handles, naming) lives in app/engine/registry.py.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic

from app.config import get_settings
from app.schemas import Node


class NodeError(Exception):
    """A failure that should be shown to the user on the node that caused it."""


@dataclass
class NodeContext:
    node: Node
    inputs: dict[str, str]  # handle name -> value, e.g. {"prompt": "..."}
    run_inputs: dict[str, str]  # values supplied when the run was started, keyed by input name
    name: str | None = None  # effective name of an input/output node (see registry.node_name)
    # Filled by handlers that call a paid API: {"input_tokens": n, "output_tokens": n}.
    usage: dict[str, int] = field(default_factory=dict)


Handler = Callable[[NodeContext], str]

# Shared with the frontend through GET /node-types (it builds its RegExp from this pattern).
TEMPLATE_VAR = re.compile(r"{{\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*}}")
DEFAULT_TEMPLATE = "{{input}}"


def template_variables(template: str) -> list[str]:
    return list(dict.fromkeys(TEMPLATE_VAR.findall(template)))


def run_input(ctx: NodeContext) -> str:
    if ctx.name not in ctx.run_inputs:
        raise NodeError(f"No value provided for input '{ctx.name}'")
    return ctx.run_inputs[ctx.name]


def run_output(ctx: NodeContext) -> str:
    if "value" not in ctx.inputs:
        raise NodeError("Output node has nothing connected to it")
    return ctx.inputs["value"]


def run_text(ctx: NodeContext) -> str:
    template = ctx.node.data.get("text", DEFAULT_TEMPLATE)

    def substitute(match: re.Match) -> str:
        variable = match.group(1)
        if variable not in ctx.inputs:
            raise NodeError(f"Variable '{variable}' is not connected to anything")
        return ctx.inputs[variable]

    return TEMPLATE_VAR.sub(substitute, template)


_llm_client: anthropic.Anthropic | None = None


def get_llm_client() -> anthropic.Anthropic:
    """Build one shared client, failing clearly when no API key is configured.

    The key comes from settings, so ANTHROPIC_API_KEY works both as a real environment
    variable and from backend/.env (which the SDK alone would not read).
    """
    global _llm_client
    if _llm_client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise NodeError("LLM call failed: ANTHROPIC_API_KEY is not configured")
        _llm_client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            # With streaming, `read` bounds the wait between chunks, not the whole answer,
            # so long generations don't time out (and aren't retried and re-billed).
            timeout=anthropic.Timeout(settings.llm_timeout_seconds, connect=10.0),
            max_retries=settings.llm_max_retries,
        )
    return _llm_client


def run_llm(ctx: NodeContext) -> str:
    settings = get_settings()
    prompt = ctx.inputs.get("prompt", "").strip()
    if not prompt:
        raise NodeError("LLM node needs a prompt connected to its 'prompt' input")

    model = ctx.node.data.get("model") or settings.llm_model
    if model not in settings.allowed_models:
        raise NodeError(
            f"Model '{model}' is not allowed. Choose one of: {', '.join(settings.allowed_models)}"
        )

    request: dict = {
        "model": model,
        "max_tokens": settings.llm_max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": settings.llm_effort},
        # Server-side fallback: if the model declines, the API retries on a suitable model.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    system = ctx.inputs.get("system", "").strip()
    if system:
        request["system"] = system

    client = get_llm_client()
    try:
        with client.beta.messages.stream(**request) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise NodeError("LLM call failed: the Anthropic API key is invalid") from exc
    except anthropic.PermissionDeniedError as exc:
        raise NodeError("LLM call failed: this API key may not use that model") from exc
    except anthropic.RateLimitError as exc:
        raise NodeError("LLM call failed: rate limited by the Anthropic API, try again") from exc
    except anthropic.BadRequestError as exc:
        raise NodeError(f"LLM call rejected: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise NodeError(f"LLM call failed with status {exc.status_code}") from exc
    except anthropic.APITimeoutError as exc:  # subclass of APIConnectionError: catch it first
        raise NodeError(
            f"LLM call timed out: no data from the Anthropic API for "
            f"{settings.llm_timeout_seconds:g} seconds"
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise NodeError("LLM call failed: could not reach the Anthropic API") from exc

    usage = getattr(response, "usage", None)
    ctx.usage = {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }

    if response.stop_reason == "refusal":
        raise NodeError("The model declined to answer this prompt")

    text = "".join(block.text for block in response.content if block.type == "text")
    if response.stop_reason == "max_tokens":
        text += "\n\n[truncated: response hit the max_tokens limit]"
    return text
