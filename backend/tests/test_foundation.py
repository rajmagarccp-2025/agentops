from fastapi.testclient import TestClient

from platform_api.database import get_db
from platform_api.main import app
from platform_api.redis_client import get_redis


class FakeDatabase:
    def execute(self, statement: object) -> None:
        return None


class FakeRedis:
    async def ping(self) -> bool:
        return True


async def fake_redis() -> FakeRedis:
    return FakeRedis()


def fake_database() -> FakeDatabase:
    return FakeDatabase()


client = TestClient(app)


def test_health_preserves_request_id() -> None:
    response = client.get("/api/v1/health", headers={"x-request-id": "test-request"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request"


def test_readiness_checks_dependencies() -> None:
    app.dependency_overrides[get_db] = fake_database
    app.dependency_overrides[get_redis] = fake_redis
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "database": "ok",
            "redis": "ok",
            "workflow_worker": "unavailable",
        },
    }
