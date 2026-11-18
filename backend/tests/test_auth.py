from tests.conftest import register


def test_register_login_me(client):
    register(client, "Alice@Example.com")
    response = client.post(
        "/api/v1/auth/login", data={"username": "alice@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "alice@example.com"


def test_duplicate_email(client):
    register(client)
    response = client.post(
        "/api/v1/auth/register", json={"email": "user@example.com", "password": "password123"}
    )
    assert response.status_code == 409


def test_wrong_password(client):
    register(client)
    response = client.post(
        "/api/v1/auth/login", data={"username": "user@example.com", "password": "nope-nope"}
    )
    assert response.status_code == 401


def test_short_password(client):
    response = client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "short"})
    assert response.status_code == 422


def test_protected_routes_need_token(client):
    assert client.get("/api/v1/pipelines").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/v1/pipelines", headers=bad).status_code == 401
