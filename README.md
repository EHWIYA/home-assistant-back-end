# iot-api (Home Assistant BFF)

FastAPI BFF for [iot-web](https://iot.iwhya.kr). Home Assistant is the only data source.

- Production: `https://iot-api.iwhya.kr` (Tailscale + LAN via nginx)
- Local: `http://127.0.0.1:8002`
- OpenAPI version: **2.0.0**

## Quick start (local)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
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
| GET | `/api/v1/weather/local` | `X-API-Key` |
| GET | `/api/v1/strip/state` | `X-API-Key` (DB + Hejhome) |
| POST | `/api/v1/strip/channels/{1-4}` | `X-API-Key` |
| GET/POST/PATCH/DELETE | `/api/v1/strip/presets` | `X-API-Key` |
| POST | `/api/v1/strip/presets/{name}` | `X-API-Key` (적용) |
| GET | `/api/v1/schedules?channel=1` | `X-API-Key` |
| GET | `/api/v1/schedules/preview?from=&to=` | `X-API-Key` |
| GET/POST/PATCH/DELETE | `/api/v1/schedules` … | `X-API-Key` |
| GET | `/api/v1/meta/holidays?year=2026` | `X-API-Key` |

### Strip · Schedules

- `DATABASE_URL`, Hejhome env 필요 — `AGENTS.md` / `.cursor/rules/env.mdc`
- 컨테이너 기동 시 `alembic upgrade head` (`scripts/docker-entrypoint.sh`)
- 스케줄 워커: `docker exec iot-api python -m app.cli.scheduler` (NAS systemd timer)

상세: `.cursor/coordination/STRIP_API_v1.md`

## CI / 배포

| Workflow | 트리거 | 내용 |
|----------|--------|------|
| `ci.yml` | **PR만** | pytest |
| `deploy.yml` | `main` push, manual | pytest → GHCR → NAS (main당 pytest 1회) |

- 이미지 pin: `IOT_API_IMAGE=ghcr.io/...:sha-XXXXXXX` (NAS `.deploy-image`)
- 롤백: `.github/DEPLOY_RUNBOOK.md`
- Secrets·TS 키 만료: `.github/GITHUB_SECRETS.md`
- Dependabot: pip·GitHub Actions 주 1회 PR

## NAS deploy

1. `docker-compose.yml` → `/home/iwh/iot/api/`
2. `.env` on NAS (git 제외)
3. `network_mode: host` + `HA_BASE_URL=http://127.0.0.1:8123`
4. 스케줄 timer: `sudo bash scripts/nas/bin/install-iot-scheduler-systemd.sh`
5. 공휴일 cron: `infra/docs/kr-holidays-cron.md`

## Tests

```powershell
.\.cursor\scripts\dev-test.ps1
```

(`requirements-dev.txt` — prod는 `requirements.txt` 만 Docker 이미지에 포함)

## Architecture

```
iot-web → X-API-Key → iot-api → Bearer HA_TOKEN → Home Assistant
                     └→ Hejhome (strip) + PostgreSQL (schedules)
```

Cursor: `AGENTS.md`, `.cursor/rules/`.
