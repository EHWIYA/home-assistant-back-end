# 공조 문서 인덱스

3파트(프론트 · 백엔드 · 서버) 협업용. 복사 블록·스펙·회신 기록.

## 인프라 · 배포

| 문서 | 대상 | 상태 |
|------|------|------|
| [infra/ha-local.md](infra/ha-local.md) | 서버 | **완료** — 로컬 HA 연동 |
| [infra/nas-ha.md](infra/nas-ha.md) | 서버 | **완료** — NAS host network |
| [infra/gha-docker.md](infra/gha-docker.md) | 서버 | 대기 — GHA→NAS 배포 |

## Push API (`iot.iwhya.kr`)

iot-api와 **별도** NAS 서비스 (`iot-ac-push-svc`, `:18765`).

| 문서 | 대상 | 상태 |
|------|------|------|
| [push/spec.md](push/spec.md) | 서버 | **완료** — REST 4종 + CORS |
| [push/from-server.md](push/from-server.md) | 백엔드 | **완료** — 서버 회신 요약 |
| [push/to-frontend.md](push/to-frontend.md) | 프론트 | **완료** — 스펙 합의·배포 안내 |
| [push/mail.md](push/mail.md) | 서버 | 발송 완료 (참고용) |

## AC · API 스펙

| 문서 | 대상 | 상태 |
|------|------|------|
| [ac/auto-check.md](ac/auto-check.md) | 서버 | 회신 — IR·running_source |
| [ac/thresholds-v2.md](ac/thresholds-v2.md) | 서버 | 회신 — 3모드 mutex |
| [ac/thresholds-v4-stale.md](ac/thresholds-v4-stale.md) | 서버·프론트 | 회신 — freshness·v4 thresholds |
| [api/strip.md](api/strip.md) | 프론트·서버 | Strip + Schedules 스펙 |
| [api/weather.md](api/weather.md) | 프론트 | 회신 — `/weather/local` |
| [strip/scheduler.md](strip/scheduler.md) | 서버 | Phase 2 timer 활성화 |

## 빠른 참조

| 서비스 | Base URL | 인증 |
|--------|----------|------|
| iot-api (이 repo) | `iot-api.iwhya.kr` | `X-API-Key` |
| Push API | `iot.iwhya.kr/api/push/*` | `Authorization: Bearer` |

공조 블록 형식: `.cursor/rules/three-part-collaboration.mdc`
