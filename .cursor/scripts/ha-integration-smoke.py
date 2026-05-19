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
    states = []
    for eid in STATUS_ENTITY_IDS:
        states.append(await ha.get_state(eid))
    dto = build_status_from_states(states, settings.ac_power_threshold_w)
    print(json.dumps(dto.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
