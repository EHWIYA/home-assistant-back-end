import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.deps import ApiKeyDep, ApiKeyHeaderOrQueryDep, SettingsDep
from app.models.schemas import StatusResponse
from app.services.ha_ws_cache import get_ha_state_cache
from app.services.status_service import fetch_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["status"])

SSE_KEEPALIVE_SECONDS = 30


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> StatusResponse:
    return await fetch_status(settings)


@router.get(
    "/status/stream",
    responses={
        200: {
            "description": (
                "Server-Sent Events stream of StatusResponse. "
                "Initial `snapshot` event, then `status` on changes. "
                "SSE comment keep-alive every 30s. "
                "Auth: X-API-Key or ?api_key= (EventSource)."
            ),
            "content": {"text/event-stream": {}},
        }
    },
)
async def status_stream(
    request: Request,
    _key: ApiKeyHeaderOrQueryDep,
    settings: SettingsDep,
) -> StreamingResponse:
    cache = get_ha_state_cache()

    async def event_generator():
        snapshot = await fetch_status(settings)
        yield _sse_event("snapshot", snapshot.model_dump_json())

        queue = cache.subscribe()
        try:
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(
                        queue.get(),
                        timeout=SSE_KEEPALIVE_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                if payload is None:
                    continue
                yield _sse_event("status", payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("status stream ended: %s", exc)
        finally:
            cache.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
