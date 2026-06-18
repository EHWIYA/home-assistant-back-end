from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_strip_service
from app.main import create_app


@pytest.fixture
def meta_client():
    app = create_app()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def presets_client():
    mock_service = MagicMock()
    sample = {
        "name": "취침",
        "channels": {"1": False, "2": True},
        "created_at": "2026-06-18T00:00:00+00:00",
    }
    mock_service.list_presets = AsyncMock(return_value=[sample])
    mock_service.create_preset = AsyncMock(return_value=sample)
    mock_service.update_preset = AsyncMock(return_value=sample)
    mock_service.delete_preset = AsyncMock(return_value=None)
    mock_service.apply_preset = AsyncMock(
        return_value={
            "device_id": "dev1",
            "online": True,
            "channels": [{"channel": 1, "on": False, "label": None}],
            "updated_at": "2026-06-18T00:00:00+00:00",
        }
    )

    app = create_app()
    app.dependency_overrides[get_strip_service] = lambda: mock_service
    client = TestClient(app)
    yield client, mock_service
    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().iot_api_key}


def test_holidays_meta(meta_client):
    resp = meta_client.get("/api/v1/meta/holidays?year=2026", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2026
    assert "2026-01-01" in body["dates"]
    assert body["source"] in {"bundled", "cache", "missing"}


def test_list_presets(presets_client):
    client, mock = presets_client
    resp = client.get("/api/v1/strip/presets", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["presets"][0]["name"] == "취침"
    mock.list_presets.assert_awaited_once()


def test_create_preset(presets_client):
    client, mock = presets_client
    resp = client.post(
        "/api/v1/strip/presets",
        headers=_headers(),
        json={"name": "취침", "channels": {"1": False, "2": True}},
    )
    assert resp.status_code == 201
    mock.create_preset.assert_awaited_once()


def test_delete_preset(presets_client):
    client, mock = presets_client
    resp = client.delete("/api/v1/strip/presets/취침", headers=_headers())
    assert resp.status_code == 204
    mock.delete_preset.assert_awaited_once_with("취침")
