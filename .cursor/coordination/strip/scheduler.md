# Strip 스케줄 — Phase 2 timer

**대상:** 서버  
**목적:** `002_schedules` 마이그레이션 후 1분 주기 스케줄 실행

전제: Phase 1 스모크 완료 (`db_reachable`, `strip/state` OK).

---

## 1. 배포

```bash
cd /home/iwh/iot/api
docker compose pull && docker compose up -d
```

alembic `002_schedules` 성공 확인.

## 2. 스모크

```bash
curl -s http://127.0.0.1:8002/health
curl -s -H "X-API-Key: <KEY>" http://127.0.0.1:8002/api/v1/schedules
```

## 3. 워커 CLI

```bash
docker exec iot-api python -m app.cli.scheduler
```

## 4. systemd timer

`/home/iwh/iot/api/infra/systemd/iot-scheduler.*.example` 참고.

```bash
sudo systemctl enable --now iot-scheduler.timer
systemctl list-timers iot-scheduler.timer
```

## 5. 프리셋 시드

`strip_presets` 0건 — PWA 기획 확정 후 INSERT.

API 스펙: [api/strip.md](../api/strip.md)
