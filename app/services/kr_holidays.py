"""대한민국 공휴일 — 정적 JSON + 선택적 NAS 캐시 디렉터리."""

from __future__ import annotations

import json
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BUNDLED_DIR = Path(__file__).resolve().parent.parent / "data"
_DATE_RE = r"^\d{4}-\d{2}-\d{2}$"


def _load_year_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    dates = payload.get("dates", [])
    if not isinstance(dates, list):
        raise ValueError(f"invalid holidays file: {path}")
    return {
        "year": int(payload.get("year", 0)),
        "dates": sorted({str(d) for d in dates}),
        "source": str(payload.get("source", path.name)),
    }


def _resolve_year_file(year: int, data_dir: Path | None) -> tuple[Path, str]:
    filename = f"kr-holidays-{year}.json"
    if data_dir is not None:
        external = data_dir / filename
        if external.is_file():
            return external, "cache"
    bundled = _BUNDLED_DIR / filename
    if bundled.is_file():
        return bundled, "bundled"
    raise FileNotFoundError(f"holiday data not found for year {year}")


@lru_cache(maxsize=8)
def _cached_year_payload(year: int, data_dir_str: str | None) -> dict[str, Any]:
    data_dir = Path(data_dir_str) if data_dir_str else None
    path, origin = _resolve_year_file(year, data_dir)
    payload = _load_year_file(path)
    if origin == "cache":
        payload["source"] = "cache"
    return payload


def get_holidays_for_year(year: int, *, data_dir: Path | None = None) -> dict[str, Any]:
    data_dir_str = str(data_dir.resolve()) if data_dir else None
    try:
        return _cached_year_payload(year, data_dir_str)
    except FileNotFoundError:
        return {"year": year, "dates": [], "source": "missing"}


def is_public_holiday(
    target: date,
    *,
    include_substitute: bool = True,
    data_dir: Path | None = None,
) -> bool:
    """include_substitute=False 시 법정 공휴일만 — bundled JSON은 대체공휴일 포함 목록."""
    payload = get_holidays_for_year(target.year, data_dir=data_dir)
    date_str = target.isoformat()
    if date_str in payload["dates"]:
        return True
    if not include_substitute:
        return False
    return date_str in payload["dates"]
