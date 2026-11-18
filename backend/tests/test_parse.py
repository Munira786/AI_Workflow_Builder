def test_parse_dag(client):
    body = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}]}
    response = client.post("/api/v1/pipelines/parse", json=body)
    assert response.json() == {"num_nodes": 2, "num_edges": 1, "is_dag": True}


def test_parse_cycle(client):
    body = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    assert client.post("/api/v1/pipelines/parse", json=body).json()["is_dag"] is False


def test_edge_to_unknown_node_is_422_not_500(client):
    body = {"nodes": [{"id": "a"}], "edges": [{"source": "a", "target": "ghost"}]}
    response = client.post("/api/v1/pipelines/parse", json=body)
    assert response.status_code == 422
    assert "ghost" in response.text


def test_duplicate_node_ids_rejected(client):
    body = {"nodes": [{"id": "a"}, {"id": "a"}], "edges": []}
    assert client.post("/api/v1/pipelines/parse", json=body).status_code == 422


def test_node_limit(client):
    body = {"nodes": [{"id": str(i)} for i in range(201)], "edges": []}
    assert client.post("/api/v1/pipelines/parse", json=body).status_code == 422


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_health_is_503_when_the_database_is_down(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "check_dependencies", lambda: {"database": "error"})
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_oversized_field_is_rejected(client):
    body = {"nodes": [{"id": "a", "data": {"text": "x" * 50_001}}], "edges": []}
    response = client.post("/api/v1/pipelines/parse", json=body)
    assert response.status_code == 422
    assert "longer than" in response.text


def test_oversized_body_is_413(client):
    body = {"nodes": [{"id": "a", "data": {"text": "x" * 1_100_000}}], "edges": []}
    response = client.post("/api/v1/pipelines/parse", json=body)
    assert response.status_code == 413


def test_request_id_is_echoed_and_security_headers_set(client):
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    # A malformed id is replaced, not reflected.
    bad = client.get("/health", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"


def test_node_types_catalogue(client):
    catalog = client.get("/api/v1/node-types").json()
    by_type = {node["type"]: node for node in catalog["node_types"]}
    assert by_type["llm"]["inputs"] == ["system", "prompt"]
    assert by_type["customInput"]["name_prefix"] == "input_"
    assert by_type["text"]["dynamic_inputs"] is True
    assert by_type["email"]["executable"] is False
    assert catalog["default_model"] in catalog["allowed_models"]
    assert "{{" in catalog["template_variable_pattern"]
