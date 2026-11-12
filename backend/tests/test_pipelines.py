from tests.conftest import register

GRAPH = {"nodes": [{"id": "a", "type": "text", "data": {"text": "hi"}}], "edges": []}


def test_crud(client, auth):
    created = client.post(
        "/api/v1/pipelines", json={"name": "First", "graph": GRAPH}, headers=auth
    )
    assert created.status_code == 201
    pipeline_id = created.json()["id"]

    listed = client.get("/api/v1/pipelines", headers=auth).json()
    assert [p["name"] for p in listed] == ["First"]

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
    assert client.get("/api/v1/pipelines", headers=other).json() == []
    assert client.get(f"/api/v1/pipelines/{pipeline_id}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/pipelines/{pipeline_id}", headers=other).status_code == 404
