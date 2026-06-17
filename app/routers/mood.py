from fastapi import APIRouter

from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import (
    MoodActionResponse,
    MoodBrightnessRequest,
    MoodCapabilitiesResponse,
    MoodColorRequest,
    MoodColorTemperatureRequest,
    MoodCommandRequest,
    MoodMetaResponse,
    MoodPowerRequest,
    MoodStateResponse,
)
from app.services.mood_client import MOOD_ACTIONS, MOOD_COLORS, MoodClient

router = APIRouter(prefix="/api/v1/mood", tags=["mood"])


@router.get("/capabilities", response_model=MoodCapabilitiesResponse)
async def mood_capabilities(_key: ApiKeyDep) -> MoodCapabilitiesResponse:
    return MoodCapabilitiesResponse(
        actions=list(MOOD_ACTIONS),
        colors=list(MOOD_COLORS),
    )


@router.get("/meta", response_model=MoodMetaResponse)
async def mood_meta(_key: ApiKeyDep, settings: SettingsDep) -> MoodMetaResponse:
    return MoodMetaResponse(
        room=settings.mood_gh_room,
        device=settings.mood_gh_device,
    )


@router.get("/state", response_model=MoodStateResponse)
async def mood_state(_key: ApiKeyDep) -> MoodStateResponse:
    return MoodStateResponse()


@router.post("/power", response_model=MoodActionResponse)
async def mood_power(
    body: MoodPowerRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    client = MoodClient(settings)
    command = await client.send_power(body.on)
    return MoodActionResponse(command=command)


@router.post("/brightness", response_model=MoodActionResponse)
async def mood_brightness(
    body: MoodBrightnessRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    client = MoodClient(settings)
    command = await client.send_brightness(body.percent)
    return MoodActionResponse(command=command)


@router.post("/color", response_model=MoodActionResponse)
async def mood_color(
    body: MoodColorRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    client = MoodClient(settings)
    command = await client.send_color(body.name)
    return MoodActionResponse(command=command)


@router.post("/color-temperature", response_model=MoodActionResponse)
async def mood_color_temperature(
    body: MoodColorTemperatureRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    client = MoodClient(settings)
    command = await client.send_color(body.mode)
    return MoodActionResponse(command=command)


@router.post("/command", response_model=MoodActionResponse)
async def mood_command(
    body: MoodCommandRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> MoodActionResponse:
    client = MoodClient(settings)
    command = await client.send_raw_command(body.command)
    return MoodActionResponse(command=command)
