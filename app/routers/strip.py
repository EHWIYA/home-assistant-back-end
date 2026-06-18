from fastapi import APIRouter, Path

from app.deps import ApiKeyDep, StripServiceDep
from app.models.schemas import (
    StripChannelActionRequest,
    StripPresetApplyResponse,
    StripPresetCreateRequest,
    StripPresetListResponse,
    StripPresetResponse,
    StripPresetUpdateRequest,
    StripStateResponse,
)

router = APIRouter(prefix="/api/v1/strip", tags=["strip"])


@router.get("/state", response_model=StripStateResponse)
async def strip_state(
    _key: ApiKeyDep,
    service: StripServiceDep,
) -> StripStateResponse:
    data = await service.get_state()
    return StripStateResponse(**data)


@router.post("/channels/{channel}", response_model=StripStateResponse)
async def strip_channel_control(
    body: StripChannelActionRequest,
    _key: ApiKeyDep,
    service: StripServiceDep,
    channel: int = Path(ge=1, le=4),
) -> StripStateResponse:
    data = await service.set_channel(channel, on=body.on)
    return StripStateResponse(**data)


@router.get("/presets", response_model=StripPresetListResponse)
async def strip_list_presets(
    _key: ApiKeyDep,
    service: StripServiceDep,
) -> StripPresetListResponse:
    items = await service.list_presets()
    return StripPresetListResponse(presets=[StripPresetResponse(**item) for item in items])


@router.post("/presets", response_model=StripPresetResponse, status_code=201)
async def strip_create_preset(
    body: StripPresetCreateRequest,
    _key: ApiKeyDep,
    service: StripServiceDep,
) -> StripPresetResponse:
    data = await service.create_preset(body.name, body.channels)
    return StripPresetResponse(**data)


@router.patch("/presets/{name}", response_model=StripPresetResponse)
async def strip_update_preset(
    body: StripPresetUpdateRequest,
    _key: ApiKeyDep,
    service: StripServiceDep,
    name: str,
) -> StripPresetResponse:
    data = await service.update_preset(name, body.channels)
    return StripPresetResponse(**data)


@router.delete("/presets/{name}", status_code=204)
async def strip_delete_preset(
    _key: ApiKeyDep,
    service: StripServiceDep,
    name: str,
) -> None:
    await service.delete_preset(name)


@router.post("/presets/{name}", response_model=StripPresetApplyResponse)
async def strip_apply_preset(
    _key: ApiKeyDep,
    service: StripServiceDep,
    name: str,
) -> StripPresetApplyResponse:
    data = await service.apply_preset(name)
    state = StripStateResponse(**data)
    return StripPresetApplyResponse(ok=True, state=state)
