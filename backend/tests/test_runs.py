from types import SimpleNamespace

import pytest

from app.engine import nodes as node_handlers
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


class FakeClaude:
    def __init__(self, stop_reason="end_turn"):
        self.calls = []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text="Autumn moonlight falls"),
            ],
        )


@pytest.fixture
def fake_claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(node_handlers, "get_llm_client", lambda: fake)
    return fake


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


def test_run_saved_pipeline(client, auth, fake_claude):
    pipeline_id = client.post(
        "/api/v1/pipelines", json={"name": "Haiku", "graph": text_llm_graph()}, headers=auth
    ).json()["id"]
    run = start_run(client, auth, pipeline_id=pipeline_id, inputs={"topic": "rain"})
    assert run["status"] == "succeeded"
    assert run["pipeline_id"] == pipeline_id

    history = client.get(f"/api/v1/runs?pipeline_id={pipeline_id}", headers=auth).json()
    assert [r["id"] for r in history] == [run["id"]]


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


def test_refusal_is_reported(client, auth, monkeypatch):
    monkeypatch.setattr(node_handlers, "get_llm_client", lambda: FakeClaude("refusal"))
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    assert run["status"] == "failed"
    assert "declined" in run["node_states"]["llm-1"]["error"]


def test_missing_api_key_is_a_clear_node_error(client, auth, monkeypatch):
    def no_credentials(**kwargs):
        raise TypeError("Could not resolve authentication method.")

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=no_credentials)))
    monkeypatch.setattr(node_handlers, "get_llm_client", lambda: fake)
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    assert run["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in run["node_states"]["llm-1"]["error"]


def test_unsupported_node_type(client, auth):
    graph = {"nodes": [{"id": "email-1", "type": "email"}], "edges": []}
    run = start_run(client, auth, graph=graph)
    assert run["status"] == "failed"
    assert "email" in run["error"]


def test_cycle_rejected_upfront(client, auth):
    graph = {
        "nodes": [{"id": "a", "type": "text"}, {"id": "b", "type": "text"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    response = client.post("/api/v1/runs", json={"graph": graph}, headers=auth)
    assert response.status_code == 422


def test_runs_are_private(client, auth, fake_claude):
    run = start_run(client, auth, graph=text_llm_graph(), inputs={"topic": "x"})
    other = register(client, "other@example.com")
    assert client.get(f"/api/v1/runs/{run['id']}", headers=other).status_code == 404
