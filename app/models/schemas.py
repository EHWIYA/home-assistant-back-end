from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    ha_reachable: bool
    db_reachable: bool | None = None


class PlugStatus(BaseModel):
    switch: Literal["on", "off", "unavailable", "unknown"]
    power_w: float | None = None
    energy_kwh: float | None = None


class PersonStatus(BaseModel):
    state: str
    latitude: float | None = None
    longitude: float | None = None


class WeatherOutdoor(BaseModel):
    temperature: float | None = None
    humidity: float | int | None = None
    condition: str | None = None


class StatusResponse(BaseModel):
    plug: PlugStatus
    ac_estimated_running: bool
    person: PersonStatus
    indoor: None = None
    weather_outdoor: WeatherOutdoor | None = None
    updated_at: str


class PlugActionRequest(BaseModel):
    action: Literal["on", "off"]


class PlugActionResponse(BaseModel):
    ok: bool = True
    switch: Literal["on", "off", "unavailable", "unknown"]


class AcActionRequest(BaseModel):
    action: Literal["on", "off"]


class AcActionResponse(BaseModel):
    ok: bool = True


class PowerHistoryPoint(BaseModel):
    t: str
    w: float | None


class PowerHistoryResponse(BaseModel):
    points: list[PowerHistoryPoint]


class ErrorBody(BaseModel):
    detail: str
    code: str


class StripChannelState(BaseModel):
    channel: int = Field(ge=1, le=4)
    on: bool | None = None
    label: str | None = None


class StripStateResponse(BaseModel):
    device_id: str
    online: bool | None = None
    channels: list[StripChannelState]
    updated_at: str


class StripChannelActionRequest(BaseModel):
    on: bool


class StripPresetApplyResponse(BaseModel):
    ok: bool = True
    state: StripStateResponse
