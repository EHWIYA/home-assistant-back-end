# Strip API v1

Base: `https://iot-api.iwhya.kr` (로컬 `http://127.0.0.1:8002`)  
인증: `X-API-Key: <IOT_API_KEY>`

## GET `/api/v1/strip/state`

```json
{
  "device_id": "57102628e8db84f19f56",
  "online": true,
  "channels": [
    { "channel": 1, "on": true, "label": null },
    { "channel": 2, "on": false, "label": null },
    { "channel": 3, "on": null, "label": null },
    { "channel": 4, "on": false, "label": null }
  ],
  "updated_at": "2026-05-20T12:00:00+00:00"
}
```

## POST `/api/v1/strip/channels/{channel}`

- `channel`: 1–4 · Body: `{ "on": true }` · Response: `StripStateResponse`

## POST `/api/v1/strip/presets/{name}`

- DB `strip_presets` 행 필요
- `channels` 예: `{"1": true, "2": false, "3": false, "4": true}`

## GET `/health`

```json
{ "status": "ok", "ha_reachable": true, "db_reachable": true }
```

`db_reachable`는 `DATABASE_URL` 미설정 시 `null`.

## 오류

`{ "detail": "...", "code": "..." }` — `strip_not_configured` (503), `hejhome_*`, `unauthorized` (401)

## Schedules (Phase 2)

`days_of_week`: **0=월 … 6=일**. 시간 **KST `HH:MM`**.

| Method | Path |
|--------|------|
| GET/POST | `/api/v1/schedules` |
| GET/PATCH/DELETE | `/api/v1/schedules/{id}` |
| GET | `/api/v1/schedules/{id}/runs?limit=50` |

### POST 예 (채널 ON)

```json
{
  "name": "아침 콘센트",
  "enabled": true,
  "action_type": "channel",
  "channel_number": 1,
  "channel_on": true,
  "time_kst": "08:00",
  "days_of_week": [0, 1, 2, 3, 4]
}
```

### POST 예 (프리셋)

```json
{
  "name": "취침 모드",
  "action_type": "preset",
  "preset_name": "sleep",
  "time_kst": "23:30",
  "days_of_week": [0, 1, 2, 3, 4, 5, 6]
}
```

## 워커 (NAS systemd)

```bash
docker exec iot-api python -m app.cli.scheduler
```

stdout: `executed`, `skipped_duplicate`, `results[]`.  
timer 설정: [strip/scheduler.md](../strip/scheduler.md)
