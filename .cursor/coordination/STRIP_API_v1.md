# Strip API v1 — PWA / 서버 합의용 초안

Base: `https://iot-api.iwhya.kr` (로컬 `http://127.0.0.1:8002`)  
인증: 헤더 `X-API-Key: <IOT_API_KEY>`

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

- `channel`: 1–4
- Body: `{ "on": true }`
- Response: 동일 `StripStateResponse`

## POST `/api/v1/strip/presets/{name}`

- DB `strip_presets` 행 필요 (서버/백엔드에서 시드)
- `channels` JSON 예: `{"1": true, "2": false, "3": false, "4": true}`

## GET `/health`

```json
{
  "status": "ok",
  "ha_reachable": true,
  "db_reachable": true
}
```

`db_reachable`는 `DATABASE_URL` 미설정 시 `null`.

## 오류

`{ "detail": "...", "code": "..." }` — `strip_not_configured` (503), `hejhome_*`, `unauthorized` (401)

## Schedules (Phase 2)

인증: `X-API-Key`. `days_of_week`: **0=월 … 6=일** (Python `weekday()`). 시간은 **KST `HH:MM`**.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/schedules` | 목록 |
| POST | `/api/v1/schedules` | 생성 (201) |
| GET | `/api/v1/schedules/{id}` | 단건 |
| PATCH | `/api/v1/schedules/{id}` | 수정 |
| DELETE | `/api/v1/schedules/{id}` | 삭제 (204) |
| GET | `/api/v1/schedules/{id}/runs?limit=50` | 실행 이력 |

### POST body 예 (채널 ON)

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

### POST body 예 (프리셋)

```json
{
  "name": "취침 모드",
  "action_type": "preset",
  "preset_name": "sleep",
  "time_kst": "23:30",
  "days_of_week": [0, 1, 2, 3, 4, 5, 6]
}
```

## 스케줄 워커 (NAS systemd)

1분마다 1회 due 실행:

```bash
docker exec iot-api python -m app.cli.scheduler
```

stdout JSON: `executed`, `skipped_duplicate`, `results[]`.
