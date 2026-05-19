from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    app = create_app()
    with patch("app.routers.health.HAClient") as mock_cls:
        mock_cls.return_value.ping = AsyncMock(return_value=True)
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ha_reachable"] is True


def test_status_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/status")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"
