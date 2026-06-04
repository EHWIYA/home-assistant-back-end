"""로컬 .env 기준 KMA 실외 날씨 스모크 (uvicorn 불필요)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import get_settings
from app.services.weather_service import WeatherService, reset_weather_cache_for_tests


async def main() -> int:
    settings = get_settings()
    if not settings.kma_service_key.strip():
        print("kma_configured=false (KMA_SERVICE_KEY empty)")
        return 1

    reset_weather_cache_for_tests()
    service = WeatherService(settings)
    try:
        result = await service.get_local_weather()
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            print(f"weather_ok=false code={detail.get('code')} detail={detail.get('detail')}")
        else:
            print(f"weather_ok=false error={exc}")
        return 1

    print(
        "weather_ok=true",
        f"location={result.location_short_label}",
        f"temp={result.temperature}",
        f"humidity={result.humidity}",
        f"condition={result.condition}",
        f"source_detail={result.source_detail}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
