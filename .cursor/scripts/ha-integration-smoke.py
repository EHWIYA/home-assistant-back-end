"""로컬 .env 기준 HA ping + status DTO 빌드 (uvicorn 불필요)."""

from __future__ import annotations

import asyncio
import json
import sys

from app.config import get_settings
from app.constants import STATUS_ENTITY_IDS
from app.services.ha_client import HAClient
from app.services.status_builder import build_status_from_states


async def main() -> int:
    settings = get_settings()
    ha = HAClient(settings)
    reachable = await ha.ping()
    print(f"ha_reachable={reachable}")
    if not reachable:
        return 1
    by_id: dict[str, dict] = {}
    for eid in STATUS_ENTITY_IDS:
        by_id[eid] = await ha.get_state(eid)
    dto = build_status_from_states(
        by_id,
        ac_power_threshold_w=settings.ac_power_threshold_w,
        pc_power_threshold_w=settings.pc_power_threshold_w,
        estimate_rate_won_per_kwh=settings.estimate_rate_won_per_kwh,
    )
    print(json.dumps(dto.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
