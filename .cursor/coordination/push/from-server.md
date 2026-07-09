# Push API — 서버 회신

**발신:** 서버 (NAS)  
**수신:** 백엔드  
**일자:** 2026-07-09  
**상태:** **배포 완료**

---

## 요약

- 서비스: `iot-ac-push-svc` (`127.0.0.1:18765` → nginx `iot.iwhya.kr/api/push/`)
- **iot-api 추가 개발·Docker 이미지 갱신 불필요**
- 인증: `Authorization: Bearer <IOT_API_KEY>` (iot-api `.env`와 동일 키)

## 구현 현황

| 항목 | 상태 |
|------|------|
| `OPTIONS /api/push/*` CORS | 200 (`Origin: https://iot.iwhya.kr`) |
| `GET /api/push/status` | 완료 (`enabled`, `lastSentAt`, `nextAllowedAt`) |
| `POST /api/push/test` | 완료 (12시간 제한 **제외**) |
| `GET /api/push/tokens` | 완료 |
| `GET /api/push/history` | 완료 |
| `register` / `unregister` | 기존 동작 유지 |

## 백엔드 후속

- 코드·배포 작업 **없음**
- `IOT_API_KEY` 값 동기화만 운영 시 유지

## 프론트 후속

- 설정·알림함·서버 동기화 UI 활성화 가능
- 상세 스펙: [to-frontend.md](to-frontend.md)
