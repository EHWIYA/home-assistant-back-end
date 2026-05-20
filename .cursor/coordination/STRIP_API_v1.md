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

## Phase 2 (예정)

- `schedules`, `schedule_runs` CRUD
- KST 워커 CLI → NAS `iot-scheduler.timer`

## 스케줄 워커 선호안 (백엔드 제안)

**`docker exec iot-api python -m app.cli.scheduler`** (1회 due 실행) + systemd timer.

이유: 이미지·`.env`·DB·Hejhome 자격증명을 iot-api와 공유, 별도 컨테이너 불필요.
