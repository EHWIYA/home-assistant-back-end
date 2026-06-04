from fastapi import APIRouter

from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import WeatherLocalResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/api/v1", tags=["weather"])


@router.get(
    "/weather/local",
    response_model=WeatherLocalResponse,
    responses={
        503: {
            "description": "기상청 API 오류 또는 키 미설정 (`code`: `weather_unavailable`)",
        },
    },
    summary="실외 날씨 (공공데이터·기상청)",
    description=(
        "홈 PWA 실외 날씨용. 공공데이터포털 기상청 **초단기실황**을 우선 사용하고, "
        "필요 시 **초단기예보**로 보완합니다. "
        "서버 메모리 캐시(TTL 기본 15분). "
        "`GET /api/v1/status`의 `weather_outdoor`(HA `weather.forecast_jib`)와 **별개**입니다."
    ),
)
async def get_local_weather(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> WeatherLocalResponse:
    service = WeatherService(settings)
    return await service.get_local_weather()
