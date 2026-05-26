import pytest

from app.config import Settings
from app.exceptions import UnauthorizedError
from app.deps import verify_api_key_header_or_query


def _settings() -> Settings:
    return Settings.model_construct(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="t",
        iot_api_key="test-key",
    )


def test_api_key_header_or_query_accepts_header():
    verify_api_key_header_or_query(
        x_api_key="test-key",
        api_key=None,
        settings=_settings(),
    )


def test_api_key_header_or_query_accepts_query():
    verify_api_key_header_or_query(
        x_api_key=None,
        api_key="test-key",
        settings=_settings(),
    )


def test_api_key_header_prefers_header_over_query():
    with pytest.raises(UnauthorizedError):
        verify_api_key_header_or_query(
            x_api_key="wrong",
            api_key="test-key",
            settings=_settings(),
        )
