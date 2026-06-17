from fastapi import APIRouter

from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import (
    MoodActionResponse,
    MoodBrightnessRequest,
    MoodCapabilitiesResponse,
    MoodColorRequest,
    MoodColorRgbRequest,
    MoodColorHsRequest,
    MoodColorTemperatureRequest,
    MoodCommandRequest,
    MoodMetaResponse,
    MoodPowerRequest,
    MoodStateResponse,
)
from app.services.mood_service import MoodService

router = APIRouter(prefix="/api/v1/mood", tags=["mood"])


@router.get("/capabilities", response_model=MoodCapabilitiesResponse)
async def mood_capabilities(_key: ApiKeyDep, settings: SettingsDep) -> MoodCapabilitiesResponse:
    return MoodService(settings).capabilities()


@router.get("/meta", response_model=MoodMetaResponse)
async def mood_meta(_key: ApiKeyDep, settings: SettingsDep) -> MoodMetaResponse:
    return MoodService(settings).meta()


@router.get("/state", response_model=MoodStateResponse)
async def mood_state(_key: ApiKeyDep, settings: SettingsDep) -> MoodStateResponse:
    return await MoodService(settings).get_state()


@router.post("/power", response_model=MoodActionResponse)
async def mood_power(
    body: MoodPowerRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_power(body.on)


@router.post("/brightness", response_model=MoodActionResponse)
async def mood_brightness(
    body: MoodBrightnessRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_brightness(body.percent)


@router.post("/color", response_model=MoodActionResponse)
async def mood_color(
    body: MoodColorRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_color(body.name)


@router.post("/color-rgb", response_model=MoodActionResponse)
async def mood_color_rgb(
    body: MoodColorRgbRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    r, g, b = body.resolved_rgb()
    return await MoodService(settings).send_color_rgb(r, g, b)


@router.post("/color-hs", response_model=MoodActionResponse)
async def mood_color_hs(
    body: MoodColorHsRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_color_hs(body.hue, body.saturation)


@router.post("/color-temperature", response_model=MoodActionResponse)
async def mood_color_temperature(
    body: MoodColorTemperatureRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_color(body.mode)


@router.post("/command", response_model=MoodActionResponse)
async def mood_command(
    body: MoodCommandRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    return await MoodService(settings).send_raw_command(body.command)
