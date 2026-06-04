from fastapi import HTTPException


class HAError(HTTPException):
    """Home Assistant call failed."""

    def __init__(self, detail: str, status_code: int = 503, code: str = "ha_unreachable"):
        super().__init__(
            status_code=status_code,
            detail={"detail": detail, "code": code},
        )


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Invalid API key"):
        super().__init__(
            status_code=401,
            detail={"detail": detail, "code": "unauthorized"},
        )


class HejhomeError(HTTPException):
    """Hejhome (square.hej.so) call failed."""

    def __init__(
        self,
        detail: str,
        status_code: int = 502,
        code: str = "hejhome_error",
    ):
        super().__init__(
            status_code=status_code,
            detail={"detail": detail, "code": code},
        )


class StripNotConfiguredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            detail={
                "detail": "Strip / database not configured on server",
                "code": "strip_not_configured",
            },
        )


class ScheduleNotFoundError(HTTPException):
    def __init__(self, schedule_id: str) -> None:
        super().__init__(
            status_code=404,
            detail={
                "detail": f"Schedule not found: {schedule_id}",
                "code": "schedule_not_found",
            },
        )


class ScheduleValidationError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=400,
            detail={"detail": detail, "code": "schedule_invalid"},
        )


class WeatherUnavailableError(HTTPException):
    """KMA / public-data weather call failed."""

    def __init__(self, detail: str = "Weather data unavailable"):
        super().__init__(
            status_code=503,
            detail={"detail": detail, "code": "weather_unavailable"},
        )
