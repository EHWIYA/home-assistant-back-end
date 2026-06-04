from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.weather_service import (
    WeatherService,
    _condition_from_codes,
    _nearest_fcst_items,
    _parse_items,
    reset_weather_cache_for_tests,
)


def _ncst_payload(t1h: str = "28.0", reh: str = "54", pty: str = "0") -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
            "body": {
                "items": {
                    "item": [
                        {
                            "baseDate": "20260604",
                            "baseTime": "1100",
                            "category": "PTY",
                            "obsrValue": pty,
                        },
                        {
                            "baseDate": "20260604",
                            "baseTime": "1100",
                            "category": "REH",
                            "obsrValue": reh,
                        },
                        {
                            "baseDate": "20260604",
                            "baseTime": "1100",
                            "category": "T1H",
                            "obsrValue": t1h,
                        },
                    ]
                }
            },
        }
    }


def _fcst_payload(sky: str = "3") -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
            "body": {
                "items": {
                    "item": [
                        {
                            "fcstDate": "20260604",
                            "fcstTime": "1200",
                            "category": "SKY",
                            "fcstValue": sky,
                        },
                        {
                            "fcstDate": "20260604",
                            "fcstTime": "1300",
                            "category": "SKY",
                            "fcstValue": "4",
                        },
                    ]
                }
            },
        }
    }


@pytest.fixture(autouse=True)
def clear_weather_cache():
    reset_weather_cache_for_tests()
    yield
    reset_weather_cache_for_tests()


def test_parse_items_no_data():
    payload = {
        "response": {
            "header": {"resultCode": "03", "resultMsg": "NO_DATA"},
            "body": {"items": {"item": []}},
        }
    }
    assert _parse_items(payload, allow_no_data=True) == []


def test_condition_from_codes_sky():
    assert _condition_from_codes("0", "3") == ("구름많음", "3")


def test_condition_from_codes_pty():
    assert _condition_from_codes("1", "3") == ("비", "1")


def test_nearest_fcst_items():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    items = _fcst_payload()["response"]["body"]["items"]["item"]
    now = datetime(2026, 6, 4, 12, 10, tzinfo=ZoneInfo("Asia/Seoul"))
    nearest = _nearest_fcst_items(items, now)
    assert nearest["SKY"] == "3"


@pytest.mark.asyncio
async def test_weather_service_parses_ncst_and_fcst():
    settings = Settings(
        KMA_SERVICE_KEY="test-key",
        WEATHER_LOCAL_NX=58,
        WEATHER_LOCAL_NY=125,
    )
    service = WeatherService(settings)

    async def fake_ncst(nx, ny, base_date, base_time):
        return _ncst_payload()["response"]["body"]["items"]["item"]

    async def fake_fcst(operation, **kwargs):
        if operation == "getUltraSrtFcst":
            return _fcst_payload()["response"]["body"]["items"]["item"]
        raise AssertionError(operation)

    with (
        patch.object(service, "_fetch_ncst", side_effect=fake_ncst),
        patch.object(service, "_call_kma", side_effect=fake_fcst),
    ):
        result = await service.get_local_weather()

    assert result.temperature == 28.0
    assert result.humidity == 54
    assert result.condition == "구름많음"
    assert result.condition_code == "3"
    assert result.source == "kma"
    assert result.location_short_label == "가산동"


def test_weather_local_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/weather/local")
    assert resp.status_code == 401


def test_weather_local_missing_kma_key():
    from app.config import get_settings

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        IOT_API_KEY="test-key",
        KMA_SERVICE_KEY="",
    )
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/weather/local", headers={"X-API-Key": "test-key"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "weather_unavailable"


def test_weather_local_ok():
    from app.config import get_settings
    from app.models.schemas import WeatherLocalResponse

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        IOT_API_KEY="test-key",
        KMA_SERVICE_KEY="k",
    )

    with patch("app.routers.weather.WeatherService") as mock_cls:
        mock_cls.return_value.get_local_weather = AsyncMock(
            return_value=WeatherLocalResponse(
                location_label="서울 금천구 가산동",
                location_short_label="가산동",
                temperature=28.0,
                humidity=54,
                condition="구름많음",
                condition_code="3",
                observed_at="2026-06-04T11:00:00+09:00",
                source="kma",
                source_detail="초단기실황",
            )
        )
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/weather/local", headers={"X-API-Key": "test-key"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["temperature"] == 28.0
    assert data["condition"] == "구름많음"


def test_kma_grid_geumcheon_gasan():
    from app.services.kma_grid import lat_lon_to_grid

    nx, ny = lat_lon_to_grid(37.4780, 126.8875)
    assert nx == 58
    assert ny == 125
