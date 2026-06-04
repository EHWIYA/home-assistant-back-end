from typing import Literal

from pydantic import BaseModel, Field, field_validator

AcMode = Literal["off", "auto", "cool", "dry"]
AcLastRunMode = Literal["cool", "dry"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    ha_reachable: bool
    db_reachable: bool | None = None


class PlugStatus(BaseModel):
    switch: Literal["on", "off", "unavailable", "unknown"]
    power_w: float | None = None
    energy_kwh: float | None = None
    estimated_cost_won: int | None = None


class PcStatus(BaseModel):
    switch: Literal["on", "off", "unavailable", "unknown"]
    power_w: float | None = None
    energy_today_kwh: float | None = None
    energy_month_kwh: float | None = None
    estimated_cost_today_won: int | None = None
    estimated_cost_month_won: int | None = None
    online: bool
    wifi_signal_level: int | None = None
    overload: bool
    estimated_running: bool


class WeatherOutdoor(BaseModel):
    temperature: float | None = None
    humidity: float | int | None = None
    condition: str | None = None


class IndoorClimate(BaseModel):
    temperature: float
    humidity: float


class AcAutoState(BaseModel):
    state: Literal["on", "off", "unknown", "unavailable"] = "unknown"
    last_on: str | None = None
    last_off: str | None = None
    last_transition: str | None = None
    last_run_mode: AcLastRunMode | None = None


class ElectricityInfo(BaseModel):
    rate_won_per_kwh: float


class StatusResponse(BaseModel):
    plug: PlugStatus
    pc: PcStatus
    electricity: ElectricityInfo
    ac_estimated_running: bool
    ac_auto_enabled: bool | None = None
    ac_away_enabled: bool | None = None
    ac_mode: AcMode = "off"
    ac_last_run_mode: AcLastRunMode | None = None
    ac_auto_state: AcAutoState | None = None
    indoor: IndoorClimate | None = None
    weather_outdoor: WeatherOutdoor | None = None
    updated_at: str


class PlugActionRequest(BaseModel):
    action: Literal["on", "off"]


class PlugActionResponse(BaseModel):
    ok: bool = True
    switch: Literal["on", "off", "unavailable", "unknown"]


class PcActionRequest(BaseModel):
    action: Literal["on", "off"]


class PcActionResponse(BaseModel):
    ok: bool = True
    switch: Literal["on", "off", "unavailable", "unknown"]


class AcActionRequest(BaseModel):
    mode: AcMode
    auto_enabled: bool | None = None
    away_enabled: bool | None = None


class AcActionResponse(BaseModel):
    ok: bool = True
    request_id: str | None = None
    applied_mode: AcMode | None = None
    power: Literal["on", "off"] | None = None
    auto_enabled: bool | None = None
    away_enabled: bool | None = None


class AcAutoToggleRequest(BaseModel):
    enabled: bool


class AcAutoToggleResponse(BaseModel):
    ok: bool = True
    request_id: str | None = None
    auto_enabled: bool
    plug_switch: Literal["on", "off", "unavailable", "unknown"]


class AcStateResponse(BaseModel):
    power: Literal["on", "off"]
    running_source: Literal["plug", "logical"]
    mode: AcMode
    auto_enabled: bool
    away_enabled: bool
    last_run_mode: AcLastRunMode | None = None
    state_consistent: bool
    state_source: str
    last_control_at: str | None = None
    last_control_result: Literal["success", "failed"] | None = None
    temperature_c: float | None = None
    humidity: float | None = None


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


ScheduleActionType = Literal["channel", "preset"]


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    action_type: ScheduleActionType
    channel_number: int | None = Field(default=None, ge=1, le=4)
    channel_on: bool | None = None
    preset_name: str | None = Field(default=None, max_length=64)
    time_kst: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days_of_week: list[int] = Field(default_factory=lambda: list(range(7)))

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("days_of_week must not be empty")
        for day in value:
            if day < 0 or day > 6:
                raise ValueError("days_of_week must be 0-6 (Mon-Sun)")
        return sorted(set(value))


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    action_type: ScheduleActionType | None = None
    channel_number: int | None = Field(default=None, ge=1, le=4)
    channel_on: bool | None = None
    preset_name: str | None = Field(default=None, max_length=64)
    time_kst: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days_of_week: list[int] | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("days_of_week must not be empty")
        for day in value:
            if day < 0 or day > 6:
                raise ValueError("days_of_week must be 0-6 (Mon-Sun)")
        return sorted(set(value))


class ScheduleResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    action_type: ScheduleActionType
    channel_number: int | None = None
    channel_on: bool | None = None
    preset_name: str | None = None
    time_kst: str
    days_of_week: list[int]
    created_at: str
    updated_at: str


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]


class ScheduleRunResponse(BaseModel):
    id: str
    schedule_id: str
    scheduled_at: str
    status: Literal["pending", "success", "failed"]
    detail: str | None = None
    created_at: str


class ScheduleRunListResponse(BaseModel):
    runs: list[ScheduleRunResponse]
