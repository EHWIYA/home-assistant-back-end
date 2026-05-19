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
