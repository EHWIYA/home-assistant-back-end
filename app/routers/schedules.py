import uuid

from fastapi import APIRouter, Query

from app.deps import ApiKeyDep, ScheduleServiceDep
from app.models.schemas import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleRunListResponse,
    ScheduleRunResponse,
    ScheduleUpdateRequest,
)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
) -> ScheduleListResponse:
    items = await service.list_schedules()
    return ScheduleListResponse(schedules=[ScheduleResponse(**item) for item in items])


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest,
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
) -> ScheduleResponse:
    data = await service.create_schedule(body.model_dump(exclude_none=True))
    return ScheduleResponse(**data)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
) -> ScheduleResponse:
    data = await service.get_schedule(schedule_id)
    return ScheduleResponse(**data)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdateRequest,
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
) -> ScheduleResponse:
    data = await service.update_schedule(
        schedule_id,
        body.model_dump(exclude_none=True),
    )
    return ScheduleResponse(**data)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: uuid.UUID,
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
) -> None:
    await service.delete_schedule(schedule_id)


@router.get("/{schedule_id}/runs", response_model=ScheduleRunListResponse)
async def list_schedule_runs(
    schedule_id: uuid.UUID,
    _key: ApiKeyDep,
    service: ScheduleServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> ScheduleRunListResponse:
    items = await service.list_runs(schedule_id, limit=limit)
    return ScheduleRunListResponse(runs=[ScheduleRunResponse(**item) for item in items])
