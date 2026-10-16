from fastapi.testclient import TestClient

from platform_api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }


def test_root_health_endpoints() -> None:
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert res1.json() == {"status": "ok"}

    res2 = client.get("/api/health")
    assert res2.status_code == 200
    assert res2.json() == {"status": "ok"}
