# iot-api (Home Assistant BFF)

FastAPI BFF for [iot-web](https://iot.iwhya.kr). Home Assistant is the only data source.

- Production: `https://iot-api.iwhya.kr` (Tailscale + LAN via nginx)
- Local: `http://127.0.0.1:8002`

## Quick start (local)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# .env: HA_TOKEN, IOT_API_KEY (에이전트/로컬에서 관리, git 제외)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

```bash
curl http://127.0.0.1:8002/health
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8002/api/v1/status
```

## API (v1)

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | none |
| GET | `/api/v1/status` | `X-API-Key` |
| POST | `/api/v1/plug` | `X-API-Key` |
| POST | `/api/v1/ac` | `X-API-Key` |
| GET | `/api/v1/history/power?hours=24` | `X-API-Key` |
| GET | `/api/v1/strip/state` | `X-API-Key` (DB + Hejhome 설정 필요) |
| POST | `/api/v1/strip/channels/{1-4}` body `{"on": true}` | `X-API-Key` |
| POST | `/api/v1/strip/presets/{name}` | `X-API-Key` |
| GET/POST/PATCH/DELETE | `/api/v1/schedules` … | `X-API-Key` (DB + Hejhome) |

### Strip (Hejhome PowerStrip2)

- `DATABASE_URL`, `HEJHOME_EMAIL`, `HEJHOME_PASSWORD`, `HEJHOME_STRIP_ID`, `HEJHOME_FAMILY_ID` 필요
- 컨테이너 기동 시 `alembic upgrade head` 자동 실행 (`scripts/docker-entrypoint.sh`)
- NAS PostgreSQL: `127.0.0.1:5433/iot_db` (서버 담당 compose)

```bash
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8002/api/v1/strip/state
curl -X POST -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"on":true}' http://127.0.0.1:8002/api/v1/strip/channels/1
```

### Schedules (KST)

```bash
docker exec iot-api python -m app.cli.scheduler
```

상세: `.cursor/coordination/STRIP_API_v1.md`

## NAS deploy

1. Copy `docker-compose.yml` to NAS deploy dir (e.g. `/home/iwh/iot/api/`)
2. Create `.env` on NAS (not in git): `HA_TOKEN`, `IOT_API_KEY`, `HA_BASE_URL=http://127.0.0.1:8123`, `CORS_ORIGINS`
3. Set `image:` in compose to your GHCR path
4. **HA on host network (운영 확정):** iot-api `network_mode: host` + `HA_BASE_URL=http://127.0.0.1:8123` — bridge + `host.docker.internal` 는 UFW 에서 막힐 수 있음

GitHub Actions (`deploy.yml`) builds to GHCR and SSHs to NAS for `COMPOSE_PROJECT_NAME=iot-api docker compose pull && up -d` (NAS 운영 프로젝트명과 동일).

### Secrets (GitHub)

- `NAS_HOST`, `NAS_SSH_USER`, `NAS_SSH_KEY`
- NAS `.env` is managed manually on the server (not overwritten by CI)

## Tests

Windows (UTF-8·한글 깨짐 방지):

```powershell
.\.cursor\scripts\dev-test.ps1
```

Linux/macOS:

```bash
pytest
```

Cursor 에이전트 규칙: `AGENTS.md`, `.cursor/rules/`.

IDE 터미널 UTF-8은 **Cursor 전역** User 설정 + `%USERPROFILE%\.cursor\ensure-utf8.ps1` (모든 프로젝트 공통). 적용 후 **새 터미널**을 열어 주세요.

## Architecture

```
iot-web → X-API-Key → iot-api → Bearer HA_TOKEN → Home Assistant
```

SmartThings / DB / WebSocket are out of scope for v1.
