# 공조 요청 — 서버 담당 (NAS iot-api → HA 연결)

**상태: 완료** (2026-05-19)

## 해결 (서버 3차 회신)

- NAS `iot-api`: **`network_mode: host`**
- NAS `.env`: **`HA_BASE_URL=http://127.0.0.1:8123`**
- `GET /health` → **`ha_reachable: true`**
- `GET /api/v1/status` → **응답 확인됨** (NAS 호스트 기준)

**원인 요약:** bridge 컨테이너 → host network HA(:8123) + UFW. host network + loopback URL로 해소.

---

## 백엔드 연동 테스트

| 항목 | 결과 |
|------|------|
| `pytest` (`.cursor/scripts/dev-test.ps1`) | 5 passed |
| 로컬 `http://127.0.0.1:8002/health` | `ha_reachable: true` |
| 로컬 `/api/v1/status` + `X-API-Key` | 스모크 스크립트 OK (plug·person 필드) |
| `https://iot-api.iwhya.kr/health` (개발 PC) | nginx **401** — Tailscale/LAN·인증 정책 확인 필요 (서버) |

### NAS·nginx 재검증 (선택)

```powershell
$env:IOT_API_BASE_URL = "https://iot-api.iwhya.kr"   # 또는 Tailscale 터널 후 http://127.0.0.1:8002
$env:IOT_API_KEY = "<NAS .env 와 동일>"
.\.venv\Scripts\python .\.cursor\scripts\nas-integration-smoke.py
```

로컬 HA만: `.\.venv\Scripts\python .\.cursor\scripts\ha-integration-smoke.py`

---

## 프론트 공조 (다음)

```text
[공조 요청] → 프론트 담당

목적: iot-web 실 API 연동 (NAS BFF 준비 완료)

필요:
- VITE_API_BASE_URL=https://iot-api.iwhya.kr (또는 팀이 정한 URL)
- VITE_API_KEY = NAS /home/iwh/iot/api/.env 의 IOT_API_KEY 와 동일
- mock 제거 후 /api/v1/status 호출

확인:
- 브라우저에서 상태 카드(플러그·전력·person·날씨) 표시
- CORS: NAS .env CORS_ORIGINS 에 https://iot.iwhya.kr 포함 여부
```

---

## 참고

- repo `docker-compose.yml`: NAS 운영 패턴(`network_mode: host`) 반영
- `/health` 는 앱에서 키 불필요; nginx 앞단 401 은 인프라 이슈
