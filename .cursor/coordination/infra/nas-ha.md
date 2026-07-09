# 공조 — NAS iot-api → HA 연결

**대상:** 서버  
**상태:** 완료 (2026-05-19)

## 해결

- NAS `iot-api`: **`network_mode: host`**
- NAS `.env`: **`HA_BASE_URL=http://127.0.0.1:8123`**
- `GET /health` → **`ha_reachable: true`**
- `GET /api/v1/status` → 응답 확인됨

**원인:** bridge 컨테이너 → host network HA + UFW. host network + loopback URL로 해소.

---

## 백엔드 연동 테스트

| 항목 | 결과 |
|------|------|
| `pytest` | 5 passed |
| 로컬 `/health` | `ha_reachable: true` |
| 로컬 `/api/v1/status` | 스모크 OK |
| `https://iot-api.iwhya.kr/health` (개발 PC) | nginx 401 — Tailscale/LAN 정책 (서버) |

NAS 재검증: `.\.cursor\scripts\nas-integration-smoke.py`

---

## 프론트 공조 (다음)

```text
[공조 요청] → 프론트 담당

목적: iot-web 실 API 연동
필요:
- VITE_API_BASE_URL=https://iot-api.iwhya.kr
- VITE_API_KEY = NAS IOT_API_KEY 와 동일
- mock 제거 후 /api/v1/status 호출
```
