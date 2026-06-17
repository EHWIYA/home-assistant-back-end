from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AcMode = Literal["off", "auto", "cool", "dry"]
AcLastRunMode = Literal["cool", "dry"]
AcOperatingMode = Literal["manual", "auto", "away"]


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
    """HA 실외기/외기 센서 추정 (`weather.forecast_jib`). 기상청 실외 날씨 아님."""

    temperature: float | None = Field(
        default=None,
        description="HA weather entity attributes.temperature (°C)",
    )
    humidity: float | int | None = Field(
        default=None,
        description="HA weather entity attributes.humidity (%)",
    )
    condition: str | None = Field(
        default=None,
        description="HA attributes.condition 또는 entity state (영문/HA 표기). 홈 실외 날씨용 아님.",
    )


class WeatherLocalResponse(BaseModel):
    """공공데이터·기상청 기반 실외 날씨 (홈 PWA). HA weather_outdoor 와 별개."""

    location_label: str = Field(
        examples=["서울 금천구 가산동"],
        description="UI 전체 지명",
    )
    location_short_label: str = Field(
        examples=["가산동"],
        description="UI 짧은 표기",
    )
    temperature: float = Field(examples=[28.0], description="기온 (°C)")
    humidity: int = Field(examples=[54], description="습도 (%)")
    condition: str = Field(examples=["구름많음"], description="한글 날씨 상태")
    condition_code: str | None = Field(
        default=None,
        examples=["3"],
        description="기상청 SKY(맑음=1) 또는 PTY(강수) 코드",
    )
    observed_at: str = Field(
        examples=["2026-06-04T11:00:00+09:00"],
        description="관측·발표 기준 시각 (KST ISO8601)",
    )
    source: str | None = Field(default="kma", examples=["kma"])
    source_detail: str | None = Field(
        default=None,
        examples=["초단기실황"],
        description="사용 API (초단기실황, 초단기예보 등)",
    )


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
    ac_operating_mode: AcOperatingMode | None = Field(
        default=None,
        description=(
            "HA 3모드 상호 배타 파생: away ON→away, else auto ON→auto, else 둘 다 OFF→manual. "
            "input_boolean.hwiya_ac_auto_enabled / hwiya_ac_away_enabled 기준."
        ),
    )
    ac_mode: AcMode = "off"
    ac_last_run_mode: AcLastRunMode | None = None
    ac_auto_state: AcAutoState | None = None
    indoor: IndoorClimate | None = Field(
        default=None,
        description="Broadlink 실내 센서 (sensor.hwiya_sensor_*)",
    )
    weather_outdoor: WeatherOutdoor | None = Field(
        default=None,
        description=(
            "HA `weather.forecast_jib` — 실외기/외기 온습도 추정. "
            "에어컨 탭용. 기상청 실외 날씨는 GET /api/v1/weather/local."
        ),
    )
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
    operating_mode: AcOperatingMode | None = Field(
        default=None,
        description=(
            "3모드 일괄 설정(manual/auto/away). 지정 시 auto_enabled·away_enabled보다 우선하며 "
            "away↔auto 동시 ON을 API에서 선차단한다."
        ),
    )


class AcActionResponse(BaseModel):
    ok: bool = True
    request_id: str | None = None
    applied_mode: AcMode | None = None
    power: Literal["on", "off"] | None = None
    auto_enabled: bool | None = None
    away_enabled: bool | None = None
    operating_mode: AcOperatingMode | None = None


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
    operating_mode: AcOperatingMode | None = None
    last_run_mode: AcLastRunMode | None = None
    state_consistent: bool
    state_source: str
    last_control_at: str | None = None
    last_control_result: Literal["success", "failed"] | None = None
    temperature_c: float | None = None
    humidity: float | None = None


class AcThresholdRule(BaseModel):
    """HA automation 임계값 v3.0 요약 (ON≥26·OFF·재가동·스마트 ON). 실제 판정은 HA에서 수행."""

    on: str
    off: str
    notes: str | None = None


class AcThresholdsResponse(BaseModel):
    version: str = Field(default="v3.0", examples=["v3.0"])
    home_auto: AcThresholdRule
    away: AcThresholdRule
    mutex: str = Field(
        default="manual(auto·away OFF) | auto(auto ON) | away(away ON) — HA input_boolean 상호 배타",
    )


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


MoodColorName = Literal[
    "red",
    "blue",
    "green",
    "yellow",
    "purple",
    "white",
    "warm",
    "cool",
    "rainbow",
]
MoodColorTemperatureMode = Literal["warm", "cool"]
MoodControlPath = Literal["google_assistant_sdk", "home_assistant"]


class MoodPowerRequest(BaseModel):
    on: bool


class MoodBrightnessRequest(BaseModel):
    percent: int = Field(ge=1, le=100)


class MoodColorRequest(BaseModel):
    name: MoodColorName


class MoodColorRgbRequest(BaseModel):
    r: int | None = Field(default=None, ge=0, le=255)
    g: int | None = Field(default=None, ge=0, le=255)
    b: int | None = Field(default=None, ge=0, le=255)
    hex: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="RGB hex (#RRGGBB). r/g/b 와 동시 지정 불가.",
    )

    @field_validator("hex")
    @classmethod
    def normalize_hex(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.lower()

    @model_validator(mode="after")
    def validate_rgb_or_hex(self) -> MoodColorRgbRequest:
        has_hex = self.hex is not None
        has_rgb = self.r is not None or self.g is not None or self.b is not None
        has_full_rgb = self.r is not None and self.g is not None and self.b is not None
        if has_hex and has_rgb:
            raise ValueError("provide either r,g,b or hex, not both")
        if not has_hex and has_rgb and not has_full_rgb:
            raise ValueError("r, g, b must all be provided")
        if not has_hex and not has_full_rgb:
            raise ValueError("provide r,g,b or hex")
        return self

    def resolved_rgb(self) -> tuple[int, int, int]:
        if self.hex:
            h = self.hex.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        assert self.r is not None and self.g is not None and self.b is not None
        return self.r, self.g, self.b


class MoodColorTemperatureRequest(BaseModel):
    mode: MoodColorTemperatureMode


class MoodColorHsRequest(BaseModel):
    hue: float = Field(ge=0, le=360, description="색상 0–360°")
    saturation: float = Field(ge=0, le=100, description="채도 0–100%")


class MoodHsRange(BaseModel):
    hue: list[int] = Field(default_factory=lambda: [0, 360])
    saturation: list[int] = Field(default_factory=lambda: [0, 100])


class MoodCommandRequest(BaseModel):
    command: str = Field(min_length=1, description="한국어 전체 음성 명령 (escape hatch)")


class MoodActionResponse(BaseModel):
    ok: bool = True
    command: str | None = None
    control_path: MoodControlPath | None = None


class MoodCapabilitiesResponse(BaseModel):
    actions: list[str]
    colors: list[str]
    brightness_range: list[int] = Field(default_factory=lambda: [1, 100])
    color_modes: list[str] = Field(default_factory=lambda: ["named"])
    color_mode: str | None = None
    hs_range: MoodHsRange | None = None
    rgb_range: list[int] | None = None
    color_temperature: bool | None = None
    supports_rgb: bool = False
    supports_hex: bool = False
    supports_hs: bool = False
    supports_state: bool = False


class MoodMetaResponse(BaseModel):
    room: str
    device: str
    path: MoodControlPath = "google_assistant_sdk"
    control_paths: list[MoodControlPath] = Field(default_factory=lambda: ["google_assistant_sdk"])
    entity_id: str | None = None
    state_readable: bool = False


class MoodStateResponse(BaseModel):
    on: bool | None = None
    brightness: int | None = None
    color: str | None = None
    rgb: list[int] | None = None
    hs: list[float] | None = None
    state_readable: bool = False
    note: str | None = "Google Home 경유 — 상태 읽기 미지원"
