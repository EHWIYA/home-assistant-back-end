from fastapi import APIRouter, Path

from app.deps import ApiKeyDep, StripServiceDep
from app.models.schemas import (
    StripChannelActionRequest,
    StripPresetApplyResponse,
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


@router.post("/presets/{name}", response_model=StripPresetApplyResponse)
async def strip_apply_preset(
    _key: ApiKeyDep,
    service: StripServiceDep,
    name: str,
) -> StripPresetApplyResponse:
    data = await service.apply_preset(name)
    state = StripStateResponse(**data)
    return StripPresetApplyResponse(ok=True, state=state)
