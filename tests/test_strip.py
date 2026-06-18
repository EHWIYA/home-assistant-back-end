from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.deps import get_strip_service
from app.main import create_app
from tests.conftest import api_key_headers


@pytest.fixture
def strip_client():
    mock_service = MagicMock()
    mock_service.get_state = AsyncMock(
        return_value={
            "device_id": "strip-1",
            "online": True,
            "channels": [
                {"channel": 1, "on": True, "label": None},
                {"channel": 2, "on": False, "label": None},
                {"channel": 3, "on": None, "label": None},
                {"channel": 4, "on": False, "label": None},
            ],
            "updated_at": "2026-05-20T00:00:00+00:00",
        }
    )
    mock_service.set_channel = AsyncMock(return_value=mock_service.get_state.return_value)

    app = create_app()
    app.dependency_overrides[get_strip_service] = lambda: mock_service
    client = TestClient(app)
    yield client, mock_service
    app.dependency_overrides.clear()


def test_strip_state_requires_api_key(strip_client):
    client, _ = strip_client
    resp = client.get("/api/v1/strip/state")
    assert resp.status_code == 401


def _api_headers() -> dict[str, str]:
    return api_key_headers()


def test_strip_state_ok(strip_client):
    client, mock_service = strip_client
    resp = client.get("/api/v1/strip/state", headers=_api_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "strip-1"
    assert len(data["channels"]) == 4
    mock_service.get_state.assert_awaited_once()


def test_strip_channel_control(strip_client):
    client, mock_service = strip_client
    resp = client.post(
        "/api/v1/strip/channels/2",
        headers=_api_headers(),
        json={"on": True},
    )
    assert resp.status_code == 200
    mock_service.set_channel.assert_awaited_once_with(2, on=True)


def test_strip_channel_invalid_number(strip_client):
    client, _ = strip_client
    resp = client.post(
        "/api/v1/strip/channels/9",
        headers=_api_headers(),
        json={"on": True},
    )
    assert resp.status_code == 422
