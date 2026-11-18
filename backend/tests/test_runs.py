from types import SimpleNamespace

import pytest

from app import jobs
from app.config import get_settings
from app.engine import nodes as node_handlers
from app.models import Run
from tests.conftest import register


def edge(source, source_handle, target, target_handle):
    return {
        "source": source,
        "sourceHandle": f"{source}-{source_handle}",
        "target": target,
        "targetHandle": f"{target}-{target_handle}",
    }


def text_llm_graph():
    """input -> text template -> llm(prompt) -> output, plus a text node as the system prompt."""
    return {
        "nodes": [
            {"id": "customInput-1", "type": "customInput", "data": {"inputName": "topic"}},
            {"id": "text-1", "type": "text", "data": {"text": "Write a haiku about {{topic}}"}},
            {"id": "text-2", "type": "text", "data": {"text": "You are a poet."}},
            {"id": "llm-1", "type": "llm", "data": {}},
            {"id": "customOutput-1", "type": "customOutput", "data": {"outputName": "poem"}},
        ],
        "edges": [
            edge("customInput-1", "value", "text-1", "topic"),
            edge("text-1", "output", "llm-1", "prompt"),
            edge("text-2", "output", "llm-1", "system"),
            edge("llm-1", "response", "customOutput-1", "value"),
        ],
    }


def echo_graph(input_data=None, output_data=None):
    return {
        "nodes": [
            {"id": "customInput-1", "type": "customInput", "data": input_data or {}},
            {"id": "customOutput-1", "type": "customOutput", "data": output_data or {}},
        ],
        "edges": [edge("customInput-1", "value", "customOutput-1", "value")],
    }


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeClaude:
    """Stands in for anthropic.Anthropic: records requests, returns a canned message."""

    def __init__(self, stop_reason="end_turn", input_tokens=12, output_tokens=7):
        self.calls = []
        self.message = SimpleNamespace(
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text="Autumn moonlight falls"),
            ],
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self.message)


@pytest.fixture
def fake_claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(node_handlers, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def settings(monkeypatch):
    """The live settings object; attributes changed through it are restored after the test."""
    current = get_settings()

    class Setter:
        def __setattr__(self, name, value):
            monkeypatch.setattr(current, name, value)

    return Setter()


def start_run(client, auth, **body):
    response = client.post("/api/v1/runs", json=body, headers=auth)
    assert response.status_code == 202, response.text
    # Without Redis the run executes as a background task, which TestClient finishes
    # before returning, so the stored run is already final.
    return client.get(f"/api/v1/runs/{response.json()['id']}", headers=auth).json()


def test_text_and_llm_pipeline(client, auth, fake_claude):
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "the sea"})

    assert run["status"] == "succeeded", run
    assert run["outputs"] == {"poem": "Autumn moonlight falls"}
    assert all(state["status"] == "succeeded" for state in run["node_states"].values())
    assert run["node_states"]["text-1"]["output"] == "Write a haiku about the sea"

    call = fake_claude.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == "You are a poet."
    assert call["messages"] == [{"role": "user", "content": "Write a haiku about the sea"}]
    assert call["fallbacks"] == "default"


def test_token_usage_is_recorded(client, auth, fake_claude):
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "the sea"})
    assert (run["input_tokens"], run["output_tokens"]) == (12, 7)
    assert run["node_states"]["llm-1"]["usage"] == {"input_tokens": 12, "output_tokens": 7}


def test_refusal_still_counts_tokens(client, auth, monkeypatch):
    monkeypatch.setattr(node_handlers, "get_llm_client", lambda: FakeClaude("refusal"))
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    assert run["status"] == "failed"
    assert "declined" in run["node_states"]["llm-1"]["error"]
    assert run["input_tokens"] == 12


def test_run_saved_pipeline(client, auth, fake_claude):
    pipeline_id = client.post(
        "/api/v1/pipelines", json={"name": "Haiku", "graph": text_llm_graph()}, headers=auth
    ).json()["id"]
    run = start_run(client, auth, pipeline_id=pipeline_id, inputs={"topic": "rain"})
    assert run["status"] == "succeeded"
    assert run["pipeline_id"] == pipeline_id

    history = client.get(f"/api/v1/runs?pipeline_id={pipeline_id}", headers=auth).json()
    assert [r["id"] for r in history["items"]] == [run["id"]]
    assert history["next_cursor"] is None


def test_run_history_pagination(client, auth):
    graph = {"nodes": [{"id": "t", "type": "text", "data": {"text": "hi"}}], "edges": []}
    ids = [start_run(client, auth, graph=graph)["id"] for _ in range(5)]

    seen, cursor = [], None
    while True:
        url = "/api/v1/runs?limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = client.get(url, headers=auth).json()
        seen += [run["id"] for run in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == list(reversed(ids))  # newest first, no duplicates or gaps
    assert client.get("/api/v1/runs?cursor=garbage", headers=auth).status_code == 422


def test_missing_input_fails_on_that_node(client, auth, fake_claude):
    run = start_run(client, auth, graph=text_llm_graph(), inputs={})
    assert run["status"] == "failed"
    assert "topic" in run["error"]
    assert run["node_states"]["customInput-1"]["status"] == "failed"
    assert run["node_states"]["llm-1"]["status"] == "pending"
    assert fake_claude.calls == []


def test_unconnected_template_variable(client, auth):
    graph = {
        "nodes": [{"id": "text-1", "type": "text", "data": {"text": "Hi {{name}}"}}],
        "edges": [],
    }
    run = start_run(client, auth, graph=graph)
    assert run["status"] == "failed"
    assert "name" in run["node_states"]["text-1"]["error"]


def test_nodes_not_feeding_an_output_are_skipped(client, auth, fake_claude):
    graph = echo_graph({"inputName": "q"}, {"outputName": "a"})
    graph["nodes"] += [
        {"id": "text-9", "type": "text", "data": {}},  # freshly dropped: "{{input}}"
        {"id": "llm-9", "type": "llm", "data": {}},  # stray LLM: must not be called
        {"id": "email-1", "type": "email", "data": {}},  # placeholder, not connected
    ]
    run = start_run(client, auth, graph=graph, inputs={"q": "hi"})
    assert run["status"] == "succeeded", run
    assert run["outputs"] == {"a": "hi"}
    assert run["node_states"]["text-9"]["status"] == "skipped"
    assert run["node_states"]["email-1"]["status"] == "skipped"
    assert fake_claude.calls == []


def test_blank_names_fall_back_to_the_default(client, auth):
    graph = echo_graph({"inputName": "  "}, {"outputName": ""})
    run = start_run(client, auth, graph=graph, inputs={"input_1": "hello"})
    assert run["status"] == "succeeded", run
    assert run["outputs"] == {"output_1": "hello"}


def test_duplicate_input_names_are_rejected(client, auth):
    graph = echo_graph({"inputName": "q"}, {})
    graph["nodes"].append(
        {"id": "customInput-2", "type": "customInput", "data": {"inputName": "q"}}
    )
    graph["nodes"].append({"id": "customOutput-2", "type": "customOutput", "data": {}})
    graph["edges"].append(edge("customInput-2", "value", "customOutput-2", "value"))
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 422
    assert "share the name" in response.text


def test_missing_api_key_is_a_clear_node_error(client, auth, settings, monkeypatch):
    settings.anthropic_api_key = None
    monkeypatch.setattr(node_handlers, "_llm_client", None)
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    assert run["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in run["node_states"]["llm-1"]["error"]


def test_model_must_be_on_the_allowlist(client, auth, fake_claude):
    graph = text_llm_graph()
    graph["nodes"][3]["data"]["model"] = "some-expensive-model"
    run = start_run(client, auth, graph=graph, inputs={"topic": "x"})
    assert run["status"] == "failed"
    assert "not allowed" in run["node_states"]["llm-1"]["error"]
    assert fake_claude.calls == []


def test_too_many_llm_nodes(client, auth, settings):
    settings.max_llm_nodes_per_run = 1
    graph = text_llm_graph()
    graph["nodes"].append({"id": "llm-2", "type": "llm", "data": {}})
    graph["nodes"].append({"id": "customOutput-2", "type": "customOutput", "data": {}})
    graph["edges"].append(edge("text-1", "output", "llm-2", "prompt"))
    graph["edges"].append(edge("llm-2", "response", "customOutput-2", "value"))
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 422
    assert "at most 1 LLM" in response.text


def test_daily_token_budget(client, auth, fake_claude, settings):
    settings.daily_token_budget_per_user = 15
    start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})  # uses 19 tokens
    response = client.post(
        "/api/v1/runs", json={"graph": text_llm_graph(), "inputs": {"topic": "x"}}, headers=auth
    )
    assert response.status_code == 429
    assert "budget" in response.text


def test_active_run_limit(client, auth, settings, monkeypatch):
    settings.max_active_runs_per_user = 1
    monkeypatch.setattr(jobs, "process_run", lambda *args: None)  # leave runs queued
    graph = {"nodes": [{"id": "t", "type": "text", "data": {"text": "hi"}}], "edges": []}
    assert client.post("/api/v1/runs", json={"graph": graph}, headers=auth).status_code == 202
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 429
    assert "in progress" in response.text


def test_enqueue_failure_marks_the_run_failed(client, auth, monkeypatch):
    def broken_enqueue(run_id, background_tasks):
        raise jobs.EnqueueError("redis down")

    from app.routers import runs as runs_router

    monkeypatch.setattr(runs_router, "enqueue_run", broken_enqueue)
    graph = {"nodes": [{"id": "t", "type": "text", "data": {"text": "hi"}}], "edges": []}
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 503

    from app.db import SessionLocal

    with SessionLocal() as db:
        assert {run.status for run in db.query(Run).all()} == {"failed"}


def test_unsupported_node_type(client, auth):
    graph = {"nodes": [{"id": "email-1", "type": "email"}], "edges": []}
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 422
    assert "email" in response.text


def test_cycle_rejected_upfront(client, auth):
    graph = {
        "nodes": [{"id": "a", "type": "text"}, {"id": "b", "type": "text"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 422
    assert "cycle" in response.text


def test_empty_pipeline_id_is_rejected(client, auth):
    graph = {"nodes": [{"id": "t", "type": "text", "data": {"text": "hi"}}], "edges": []}
    response = client.post("/api/v1/runs", json={"pipeline_id": "", "graph": graph}, headers=auth)
    assert response.status_code == 422


def test_runs_are_private(client, auth, fake_claude):
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    other = register(client, "other@example.com")
    assert client.get(f"/api/v1/runs/{run['id']}", headers=other).status_code == 404
