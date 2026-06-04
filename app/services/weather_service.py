"""공공데이터포털 기상청 동네예보 — 실외 날씨 프록시·캐시."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.exceptions import WeatherUnavailableError
from app.models.schemas import WeatherLocalResponse

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
KMA_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

PTY_LABELS: dict[str, str] = {
    "0": "",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울/눈날림",
    "7": "눈날림",
}

SKY_LABELS: dict[str, str] = {
    "1": "맑음",
    "3": "구름많음",
    "4": "흐림",
}

_cache: WeatherLocalResponse | None = None
_cache_expires_at: float = 0.0
_cache_lock = asyncio.Lock()


def _ncst_base(now: datetime) -> tuple[str, str]:
    """초단기실황 base_date/base_time (매시 40분 생성, 45분부터 제공)."""
    if now.minute < 45:
        base = now - timedelta(hours=1)
    else:
        base = now
    return base.strftime("%Y%m%d"), base.strftime("%H00")


def _fcst_base(now: datetime) -> tuple[str, str]:
    """초단기예보 base_date/base_time (매시 30분 발표)."""
    if now.minute < 45:
        base = now - timedelta(hours=1)
    else:
        base = now
    return base.strftime("%Y%m%d"), f"{base.hour:02d}30"


def _parse_items(payload: dict[str, Any], *, allow_no_data: bool = False) -> list[dict[str, Any]]:
    header = payload.get("response", {}).get("header", {})
    result_code = header.get("resultCode", "")
    if result_code == "03" and allow_no_data:
        return []
    if result_code != "00":
        msg = header.get("resultMsg", "KMA API error")
        raise WeatherUnavailableError(f"기상청 API 오류({result_code}): {msg}")

    items = payload.get("response", {}).get("body", {}).get("items", {}).get("item")
    if not items:
        return []
    if isinstance(items, dict):
        return [items]
    return list(items)


def _value(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        num = float(text)
        if abs(num) >= 900:
            return None
    except ValueError:
        pass
    return text


def _observed_at_kst(base_date: str, base_time: str) -> str:
    dt = datetime.strptime(f"{base_date}{base_time}", "%Y%m%d%H%M").replace(tzinfo=KST)
    return dt.isoformat(timespec="seconds")


def _condition_from_codes(pty: str | None, sky: str | None) -> tuple[str, str | None]:
    if pty and pty != "0":
        label = PTY_LABELS.get(pty, "강수")
        return label, pty
    if sky:
        label = SKY_LABELS.get(sky, "알 수 없음")
        return label, sky
    return "알 수 없음", None


class WeatherService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = settings.ha_timeout_seconds

    def _require_service_key(self) -> str:
        key = self._settings.kma_service_key.strip()
        if not key:
            raise WeatherUnavailableError("기상청 API 키가 서버에 설정되지 않았습니다")
        return key

    async def get_local_weather(self) -> WeatherLocalResponse:
        global _cache, _cache_expires_at

        ttl = self._settings.weather_cache_ttl_seconds
        now_mono = time.monotonic()
        if _cache is not None and now_mono < _cache_expires_at:
            return _cache

        async with _cache_lock:
            now_mono = time.monotonic()
            if _cache is not None and now_mono < _cache_expires_at:
                return _cache

            result = await self._fetch_local_weather()
            _cache = result
            _cache_expires_at = time.monotonic() + ttl
            return result

    async def _fetch_local_weather(self) -> WeatherLocalResponse:
        now = datetime.now(KST)
        nx = self._settings.weather_local_nx
        ny = self._settings.weather_local_ny

        ncst_date, ncst_time = _ncst_base(now)
        ncst_items = await self._fetch_ncst(nx, ny, ncst_date, ncst_time)
        if not ncst_items:
            prev = datetime.strptime(f"{ncst_date}{ncst_time}", "%Y%m%d%H%M").replace(tzinfo=KST)
            prev -= timedelta(hours=1)
            ncst_date, ncst_time = prev.strftime("%Y%m%d"), prev.strftime("%H00")
            ncst_items = await self._fetch_ncst(nx, ny, ncst_date, ncst_time)

        by_cat = {item["category"]: _value(item.get("obsrValue")) for item in ncst_items}

        temp_raw = by_cat.get("T1H")
        hum_raw = by_cat.get("REH")
        pty = by_cat.get("PTY")

        sky: str | None = None
        source_detail = "초단기실황"

        if not temp_raw or not hum_raw or (pty is None):
            fcst_date, fcst_time = _fcst_base(now)
            fcst_items = await self._call_kma(
                "getUltraSrtFcst",
                base_date=fcst_date,
                base_time=fcst_time,
                nx=nx,
                ny=ny,
            )
            nearest = _nearest_fcst_items(fcst_items, now)
            if not temp_raw:
                temp_raw = nearest.get("T1H")
            if not hum_raw:
                hum_raw = nearest.get("REH")
            if pty is None:
                pty = nearest.get("PTY")
            sky = nearest.get("SKY")
            if not temp_raw and not hum_raw:
                source_detail = "초단기예보"
            elif sky:
                source_detail = "초단기실황+초단기예보"
        elif pty == "0" or pty is None:
            fcst_date, fcst_time = _fcst_base(now)
            fcst_items = await self._call_kma(
                "getUltraSrtFcst",
                base_date=fcst_date,
                base_time=fcst_time,
                nx=nx,
                ny=ny,
            )
            nearest = _nearest_fcst_items(fcst_items, now)
            sky = nearest.get("SKY")
            if sky:
                source_detail = "초단기실황+초단기예보"

        if not temp_raw or not hum_raw:
            raise WeatherUnavailableError("기상청 실황·예보 데이터가 비어 있습니다")

        condition, condition_code = _condition_from_codes(pty, sky)

        return WeatherLocalResponse(
            location_label=self._settings.weather_local_label,
            location_short_label=self._settings.weather_local_short_label,
            temperature=float(temp_raw),
            humidity=int(float(hum_raw)),
            condition=condition,
            condition_code=condition_code,
            observed_at=_observed_at_kst(ncst_date, ncst_time),
            source="kma",
            source_detail=source_detail,
        )

    async def _fetch_ncst(
        self,
        nx: int,
        ny: int,
        base_date: str,
        base_time: str,
    ) -> list[dict[str, Any]]:
        return await self._call_kma(
            "getUltraSrtNcst",
            base_date=base_date,
            base_time=base_time,
            nx=nx,
            ny=ny,
            allow_no_data=True,
        )

    async def _call_kma(
        self,
        operation: str,
        *,
        base_date: str,
        base_time: str,
        nx: int,
        ny: int,
        allow_no_data: bool = False,
    ) -> list[dict[str, Any]]:
        key = self._require_service_key()
        common = (
            f"pageNo=1&numOfRows=1000&dataType=JSON"
            f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
        )
        # Encoding 키(% 포함): 재인코딩 금지. Decoding 키: httpx params 사용.
        if "%" in key:
            url = f"{KMA_BASE_URL}/{operation}?serviceKey={key}&{common}"
            request = ("get", url, None)
        else:
            url = f"{KMA_BASE_URL}/{operation}"
            request = (
                "get",
                url,
                {
                    "serviceKey": key,
                    "pageNo": "1",
                    "numOfRows": "1000",
                    "dataType": "JSON",
                    "base_date": base_date,
                    "base_time": base_time,
                    "nx": str(nx),
                    "ny": str(ny),
                },
            )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                if request[2] is None:
                    resp = await client.get(request[1])
                else:
                    resp = await client.get(request[1], params=request[2])
        except httpx.TimeoutException:
            raise WeatherUnavailableError("기상청 API 요청 시간 초과")
        except httpx.RequestError as exc:
            logger.warning("KMA request failed: %s", exc)
            raise WeatherUnavailableError("기상청 API에 연결할 수 없습니다")

        if resp.status_code == 401:
            raise WeatherUnavailableError(
                "KMA_SERVICE_KEY 인증 실패(401). "
                "공공데이터 마이페이지에서 「일반 인증키(Decoding)」 또는 「Encoding」 키를 "
                "그대로 붙여넣었는지 확인하세요."
            )
        if resp.status_code >= 500:
            raise WeatherUnavailableError("기상청 API 서버 오류")
        if resp.status_code >= 400:
            raise WeatherUnavailableError(f"기상청 API HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as exc:
            logger.warning("KMA invalid JSON: %s", exc)
            raise WeatherUnavailableError("기상청 API 응답 형식 오류")

        return _parse_items(payload, allow_no_data=allow_no_data)


def _nearest_fcst_items(
    items: list[dict[str, Any]],
    now: datetime,
) -> dict[str, str | None]:
    """fcstDate+fcstTime이 now에 가장 가까운 항목의 category별 값."""
    target = now.strftime("%Y%m%d%H%M")
    by_time: dict[str, dict[str, str | None]] = {}

    for item in items:
        fcst_date = item.get("fcstDate")
        fcst_time = item.get("fcstTime")
        category = item.get("category")
        if not fcst_date or not fcst_time or not category:
            continue
        key = f"{fcst_date}{fcst_time}"
        by_time.setdefault(key, {})[category] = _value(item.get("fcstValue"))

    if not by_time:
        return {}

    nearest_key = min(by_time.keys(), key=lambda k: abs(int(k) - int(target)))
    return by_time[nearest_key]


def reset_weather_cache_for_tests() -> None:
    global _cache, _cache_expires_at
    _cache = None
    _cache_expires_at = 0.0
