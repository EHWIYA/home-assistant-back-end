import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_schedule_service
from app.main import create_app

SAMPLE_ID = str(uuid.uuid4())


@pytest.fixture
def schedules_client():
    mock_service = MagicMock()
    sample = {
        "id": SAMPLE_ID,
        "name": "아침 콘센트",
        "enabled": True,
        "action_type": "channel",
        "channel_number": 1,
        "channel_on": True,
        "preset_name": None,
        "time_kst": "08:00",
        "days_of_week": [0, 1, 2, 3, 4],
        "recurrence_type": "weekly",
        "specific_dates": [],
        "exclude_dates": [],
        "holiday_mode": "ignore",
        "include_substitute": True,
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }
    mock_service.list_schedules = AsyncMock(return_value=[sample])
    mock_service.preview_schedules = AsyncMock(
        return_value=[
            {
                "schedule_id": SAMPLE_ID,
                "schedule_name": "아침 콘센트",
                "at_kst": "2026-06-18T08:00:00+09:00",
                "channel_number": 1,
                "action_type": "channel",
            }
        ]
    )
    mock_service.create_schedule = AsyncMock(return_value=sample)
    mock_service.get_schedule = AsyncMock(return_value=sample)
    mock_service.update_schedule = AsyncMock(return_value=sample)
    mock_service.delete_schedule = AsyncMock(return_value=None)
    mock_service.list_runs = AsyncMock(
        return_value=[
            {
                "id": str(uuid.uuid4()),
                "schedule_id": SAMPLE_ID,
                "scheduled_at": "2026-06-18T08:00:00+09:00",
                "status": "success",
                "executed_at": "2026-06-18T08:00:00+09:00",
                "success": True,
                "detail": None,
                "created_at": "2026-06-18T08:00:01+09:00",
            }
        ]
    )

    app = create_app()
    app.dependency_overrides[get_schedule_service] = lambda: mock_service
    client = TestClient(app)
    yield client, mock_service
    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().iot_api_key}


def test_list_schedules(schedules_client):
    client, mock = schedules_client
    resp = client.get("/api/v1/schedules", headers=_headers())
    assert resp.status_code == 200
    assert len(resp.json()["schedules"]) == 1
    mock.list_schedules.assert_awaited_once_with(channel=None)


def test_list_schedules_channel_filter(schedules_client):
    client, mock = schedules_client
    resp = client.get("/api/v1/schedules?channel=1", headers=_headers())
    assert resp.status_code == 200
    mock.list_schedules.assert_awaited_once_with(channel=1)


def test_preview_schedules(schedules_client):
    client, mock = schedules_client
    resp = client.get(
        "/api/v1/schedules/preview",
        headers=_headers(),
        params={"from": "2026-06-01", "to": "2026-06-30", "channel": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["slots"]) == 1
    mock.preview_schedules.assert_awaited_once()


def test_create_schedule(schedules_client):
    client, mock = schedules_client
    resp = client.post(
        "/api/v1/schedules",
        headers=_headers(),
        json={
            "name": "아침",
            "action_type": "channel",
            "channel_number": 1,
            "channel_on": True,
            "time_kst": "08:00",
            "days_of_week": [0, 1, 2, 3, 4],
            "holiday_mode": "skip",
        },
    )
    assert resp.status_code == 201
    mock.create_schedule.assert_awaited_once()


def test_create_schedule_invalid_time(schedules_client):
    client, _ = schedules_client
    resp = client.post(
        "/api/v1/schedules",
        headers=_headers(),
        json={
            "name": "bad",
            "action_type": "channel",
            "channel_number": 1,
            "channel_on": True,
            "time_kst": "25:99",
        },
    )
    assert resp.status_code == 422


def test_list_schedule_runs_has_executed_fields(schedules_client):
    client, _ = schedules_client
    resp = client.get(f"/api/v1/schedules/{SAMPLE_ID}/runs", headers=_headers())
    assert resp.status_code == 200
    run = resp.json()["runs"][0]
    assert run["executed_at"] == run["scheduled_at"]
    assert run["success"] is True
