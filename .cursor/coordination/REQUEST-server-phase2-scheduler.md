# [공조 요청] → 서버 담당 — Phase 2 스케줄·워커

**목적:** `002_schedules` 마이그레이션 배포 후, 1분 주기 스케줄 실행(timer) 활성화

**전제:** Phase 1 스모크 완료 (`db_reachable`, `strip/state` OK). 동일 `.env`·`iot-api` 컨테이너.

---

## 1. 배포 (백엔드 이미지 갱신 후)

```bash
cd /home/iwh/iot/api
docker compose pull
docker compose up -d
```

컨테이너 로그에서 `alembic upgrade head` → **`002_schedules`** 까지 성공 확인.

## 2. 스모크 (API)

```bash
curl -s http://127.0.0.1:8002/health
curl -s -H "X-API-Key: <IOT_API_KEY>" http://127.0.0.1:8002/api/v1/schedules
```

스케줄 등록 예 (채널 1, 평일 08:00 KST ON):

```bash
curl -s -X POST -H "X-API-Key: <IOT_API_KEY>" -H "Content-Type: application/json" \
  -d '{"name":"test-ch1-on","action_type":"channel","channel_number":1,"channel_on":true,"time_kst":"08:00","days_of_week":[0,1,2,3,4]}' \
  http://127.0.0.1:8002/api/v1/schedules
```

## 3. 워커 CLI (1회 due 실행)

```bash
docker exec iot-api python -m app.cli.scheduler
```

- exit 0, stdout JSON: `executed`, `skipped_duplicate`, `results`
- strip 미설정 시 exit 1, `{"error":"strip_not_configured"}`

## 4. systemd timer (권장)

기존 `/home/iwh/iot/api/infra/systemd/iot-scheduler.*.example` 를 참고해 아래로 활성화.

**`iot-scheduler.service`** (요지):

```ini
[Unit]
Description=IoT API strip schedule runner (one shot)
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/home/iwh/iot/api
ExecStart=/usr/bin/docker exec iot-api python -m app.cli.scheduler
```

**`iot-scheduler.timer`** (요지):

```ini
[Unit]
Description=Run IoT strip schedules every minute

[Timer]
OnCalendar=*:*:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now iot-scheduler.timer
systemctl list-timers iot-scheduler.timer
```

## 5. 프리셋 시드

`strip_presets` 0건 — **PWA/기획에서 이름·채널 조합 확정 후** 백엔드 또는 서버에서 INSERT.  
예시 SQL은 요청 시 제공.

## 6. 백엔드 → 서버 회신 불필요 항목

- Phase 1: 추가 포트/nginx 변경 없음 확인 — 동의
- PWA: Phase 1 `strip/state`·채널 POST 계약으로 연동 착수 가능 (문서: `STRIP_API_v1.md`)
