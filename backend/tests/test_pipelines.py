from tests.conftest import register

GRAPH = {"nodes": [{"id": "a", "type": "text", "data": {"text": "hi"}}], "edges": []}


def test_crud(client, auth):
    created = client.post(
        "/api/v1/pipelines", json={"name": "First", "graph": GRAPH}, headers=auth
    )
    assert created.status_code == 201
    pipeline_id = created.json()["id"]

    listed = client.get("/api/v1/pipelines", headers=auth).json()
    assert [p["name"] for p in listed["items"]] == ["First"]
    assert listed["next_cursor"] is None

    loaded = client.get(f"/api/v1/pipelines/{pipeline_id}", headers=auth).json()
    assert loaded["graph"]["nodes"][0]["data"] == {"text": "hi"}

    renamed = client.patch(
        f"/api/v1/pipelines/{pipeline_id}", json={"name": "Renamed"}, headers=auth
    )
    assert renamed.json()["name"] == "Renamed"

    assert client.delete(f"/api/v1/pipelines/{pipeline_id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/pipelines/{pipeline_id}", headers=auth).status_code == 404


def test_users_cannot_see_each_others_pipelines(client, auth):
    pipeline_id = client.post(
        "/api/v1/pipelines", json={"name": "Private", "graph": GRAPH}, headers=auth
    ).json()["id"]

    other = register(client, "other@example.com")
    assert client.get("/api/v1/pipelines", headers=other).json()["items"] == []
    assert client.get(f"/api/v1/pipelines/{pipeline_id}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/pipelines/{pipeline_id}", headers=other).status_code == 404


def test_pipeline_list_pages(client, auth):
    for i in range(3):
        client.post("/api/v1/pipelines", json={"name": f"P{i}", "graph": GRAPH}, headers=auth)
    first = client.get("/api/v1/pipelines?limit=2", headers=auth).json()
    second = client.get(
        f"/api/v1/pipelines?limit=2&cursor={first['next_cursor']}", headers=auth
    ).json()
    names = [p["name"] for p in first["items"] + second["items"]]
    assert sorted(names) == ["P0", "P1", "P2"]
    assert second["next_cursor"] is None


def test_deleting_a_pipeline_keeps_its_runs(client, auth):
    pipeline_id = client.post(
        "/api/v1/pipelines", json={"name": "P", "graph": GRAPH}, headers=auth
    ).json()["id"]
    run_id = client.post(
        "/api/v1/runs", json={"pipeline_id": pipeline_id}, headers=auth
    ).json()["id"]
    client.delete(f"/api/v1/pipelines/{pipeline_id}", headers=auth)
    # Foreign keys are enforced (also on SQLite): the run survives with pipeline_id NULL.
    assert client.get(f"/api/v1/runs/{run_id}", headers=auth).json()["pipeline_id"] is None
