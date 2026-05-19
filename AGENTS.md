# iot-api — Cursor Agent

이 저장소에서 작업하는 에이전트는 **iot-api BFF** 전담입니다. 프론트(iot-web)와 API 계약·`X-API-Key`·JSON 스키마를 맞춥니다.

## 3파트 구조 (항상 인지)

| 파트 | 범위 |
|------|------|
| **프론트** | `iot-web` — UI, `VITE_API_*` |
| **백엔드** | **이 repo** — FastAPI BFF, HA 연동 |
| **서버** | NAS — HA, Docker, nginx, Tailscale |

본인 파트 밖(프론트 설정·NAS 인프라 등)은 추측하지 않고 **공조 요청**한다. 형식·예시: `.cursor/rules/three-part-collaboration.mdc`.

## 역할

- Home Assistant REST만 호출 (`app/services/ha_client.py`)
- `/health`, `/api/v1/status`, `/api/v1/plug`, (v1.1) `/api/v1/history/power`
- Docker / GHA → GHCR → NAS 배포 보조
- SmartThings·DB·LLM·WebSocket v1 비목표

## 규칙 (자동 적용)

| 파일 | 내용 |
|------|------|
| `.cursor/rules/iot-api.mdc` | 아키텍처·API·레이어 |
| `.cursor/rules/windows-shell-utf8.mdc` | PowerShell UTF-8, `&&` 금지 |

새 채팅에서 Handoff 문서를 붙여 넣으면 도메인·NAS 맥락을 보강할 수 있습니다.

## 로컬 명령 (Windows)

**IDE 터미널 (전역)**: `%USERPROFILE%\.cursor\ensure-utf8.ps1` + Cursor User `settings.json` — 모든 워크스페이스에서 `PowerShell (UTF-8)` 기본.

**한글 깨짐 방지** — 아래 스크립트만 사용하거나, 다른 명령 전에 `ensure-utf8.ps1`을 dot-source 합니다.

```powershell
# 의존성 + pytest (권장)
.\.cursor\scripts\dev-test.ps1

# 서버
.\.cursor\scripts\ensure-utf8.ps1
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

에이전트가 Shell 도구로 실행할 때:

- `&&` 사용하지 않음 → `;` 또는 호출 분리
- `pip` / `pytest` / `python` 전: `. .\.cursor\scripts\ensure-utf8.ps1`

## 환경 변수

- **로컬 `.env`**: 에이전트 전담 (`.cursor/rules/env.mdc`). `.env.example` 없음.
- 로컬 HA: 서버 담당이 `HA_BASE_URL`, `HA_TOKEN` 전달 → `.env` 「서버 수신」만 붙여넣기.
- 공조 템플릿: `.cursor/coordination/REQUEST-server-ha-local.md`
- NAS `/home/iwh/iot-api/.env`는 서버 전용, GHA가 덮어쓰지 않음.

## Entity (HA)

`app/constants.py`: `switch.hwiya_home`, `sensor.hwiya_home_power`, `sensor.hwiya_home_energy`, `person.hwiya_ha`, `weather.forecast_jib`

AC 추정: `power_w >= AC_POWER_THRESHOLD_W` (기본 50)

## 배포 요약

- 이미지: GHCR, NAS `/home/iwh/iot-api/`, `127.0.0.1:8002`
- nginx: Tailscale + LAN only (`iot-api.iwhya.kr`)
- HA: `http://127.0.0.1:8123` (host network 시 compose `network_mode: host` 검토)

## 체크리스트 (운영)

- [ ] NAS `.env` + `docker compose up`
- [ ] nginx + SSL
- [ ] GHA Secrets (`NAS_HOST`, `NAS_SSH_USER`, `NAS_SSH_KEY`)
- [ ] 프론트 `VITE_API_BASE_URL` / `VITE_API_KEY` 연동
