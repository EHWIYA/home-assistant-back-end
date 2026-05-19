from typing import Annotated

from fastapi import Depends, Header

from app.config import Settings, get_settings
from app.exceptions import UnauthorizedError


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.iot_api_key:
        raise UnauthorizedError("API key not configured on server")
    if not x_api_key or x_api_key != settings.iot_api_key:
        raise UnauthorizedError()


SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[None, Depends(verify_api_key)]
