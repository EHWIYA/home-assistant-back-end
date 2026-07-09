# Push API — 프론트 회신

**대상:** 프론트  
**일자:** 2026-07-09 (NAS 배포 완료 반영)  
**구현 주체:** NAS Push 서비스 (iot-api 아님)

---

## 1. 범위

| 구분 | Base URL | 인증 | 담당 |
|------|----------|------|------|
| iot-api | `iot-api.iwhya.kr` | `X-API-Key` | 이 repo `/api/v1/*` |
| Push API | `iot.iwhya.kr` | `Authorization: Bearer` | NAS `/api/push/*` |

- `VITE_API_KEY` = Push·iot-api 공통 `IOT_API_KEY` (헤더 형식만 다름)
- iot-api repo에 Push/Firebase 코드 없음

---

## 2. 프로덕션 현황

**2026-07-09 NAS 배포 완료** — 전 항목 구현됨. fallback UI → 실 API 전환 가능.

| API | 상태 |
|-----|------|
| `OPTIONS /api/push/*` | 200 (CORS) |
| `GET /api/push/status` | OK |
| `POST /api/push/test` | OK |
| `GET /api/push/tokens` | OK |
| `GET /api/push/history` | OK |

---

## 3. API 스펙 (합의)

### P1

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/push/status` | `{ ok, enabled?, lastSentAt?, nextAllowedAt? }` |
| POST | `/api/push/test` | `{ ok: true }` — 12h 제한 제외 |

### P2

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/push/tokens` | `{ ok, tokens: [...] }` |
| GET | `/api/push/history?limit=30` | `{ ok, alerts: [...] }` |

- `label`: `iphone` \| `ipad` \| `android` \| `web`
- 원격 해제: `DELETE /api/push/unregister` `{ token }`

---

## 4. 합의 사항

| 항목 | 결정 |
|------|------|
| 12시간 제한 | 운영 알림만. `POST /test` 제외 |
| 히스토리 | 서버 `GET /history` 정본, `readAt` 로컬 |
| dedup | FCM `data.fingerprint` |
| CORS | `Origin: https://iot.iwhya.kr`, OPTIONS 200 |

---

## 5. 프론트 후속

- `Authorization: Bearer ${VITE_API_KEY}` (`X-API-Key`와 혼동 주의)
- env override (`VITE_PUSH_*_URL`) — 기본 URL이면 그대로 사용
- 설정·동기화 UI 활성화·실기기 검증 권장

---

## 6. 백엔드

- iot-api(`/api/v1/*`) 변경 없음
- 서버 회신: [from-server.md](from-server.md)
