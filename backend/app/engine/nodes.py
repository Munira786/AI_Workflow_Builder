"""Handlers that execute a single node.

Each handler receives the node, the values arriving on its input handles, and the run inputs,
and returns the node's output value (a string). Raise NodeError for user-facing failures.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

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


Handler = Callable[[NodeContext], str]

TEMPLATE_VAR = re.compile(r"{{\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*}}")


def default_input_name(node: Node) -> str:
    return node.id.replace("customInput-", "input_")


def default_output_name(node: Node) -> str:
    return node.id.replace("customOutput-", "output_")


def run_input(ctx: NodeContext) -> str:
    name = ctx.node.data.get("inputName") or default_input_name(ctx.node)
    if name not in ctx.run_inputs:
        raise NodeError(f"No value provided for input '{name}'")
    return ctx.run_inputs[name]


def run_output(ctx: NodeContext) -> str:
    if "value" not in ctx.inputs:
        raise NodeError("Output node has nothing connected to it")
    return ctx.inputs["value"]


def run_text(ctx: NodeContext) -> str:
    template = ctx.node.data.get("text", "{{input}}")

    def substitute(match: re.Match) -> str:
        variable = match.group(1)
        if variable not in ctx.inputs:
            raise NodeError(f"Variable '{variable}' is not connected to anything")
        return ctx.inputs[variable]

    return TEMPLATE_VAR.sub(substitute, template)


_llm_client: anthropic.Anthropic | None = None


def get_llm_client() -> anthropic.Anthropic:
    """Lazily build one shared client. The SDK reads ANTHROPIC_API_KEY from the environment."""
    global _llm_client
    if _llm_client is None:
        settings = get_settings()
        _llm_client = anthropic.Anthropic(timeout=settings.llm_timeout_seconds, max_retries=2)
    return _llm_client


def run_llm(ctx: NodeContext) -> str:
    settings = get_settings()
    prompt = ctx.inputs.get("prompt", "").strip()
    if not prompt:
        raise NodeError("LLM node needs a prompt connected to its 'prompt' input")

    request: dict = {
        "model": ctx.node.data.get("model") or settings.llm_model,
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

    try:
        response = get_llm_client().beta.messages.create(**request)
    except anthropic.AuthenticationError as exc:
        raise NodeError("LLM call failed: the Anthropic API key is missing or invalid") from exc
    except anthropic.RateLimitError as exc:
        raise NodeError("LLM call failed: rate limited by the Anthropic API, try again") from exc
    except anthropic.BadRequestError as exc:
        raise NodeError(f"LLM call rejected: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise NodeError(f"LLM call failed with status {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        raise NodeError("LLM call failed: could not reach the Anthropic API") from exc
    except (anthropic.CredentialsError, TypeError) as exc:
        # No credentials at all: the SDK raises TypeError ("Could not resolve authentication
        # method"); a configured-but-missing profile raises CredentialsError.
        raise NodeError("LLM call failed: ANTHROPIC_API_KEY is not configured") from exc
    except anthropic.AnthropicError as exc:
        raise NodeError(f"LLM call failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise NodeError("The model declined to answer this prompt")

    text = "".join(block.text for block in response.content if block.type == "text")
    if response.stop_reason == "max_tokens":
        text += "\n\n[truncated: response hit the max_tokens limit]"
    return text


HANDLERS: dict[str, Handler] = {
    "customInput": run_input,
    "customOutput": run_output,
    "text": run_text,
    "llm": run_llm,
}
