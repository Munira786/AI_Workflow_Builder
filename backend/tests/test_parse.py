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
    assert client.get("/health").json() == {"status": "ok"}
