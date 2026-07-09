# Push API — 서버 구현 스펙

**대상:** 서버 (NAS Push)  
**상태:** **완료** (2026-07-09)  
**범위:** `https://iot.iwhya.kr/api/push/*` — iot-api와 **별도 서비스**

서비스: `iot-ac-push-svc` (`127.0.0.1:18765`). iot-api Docker 갱신 불필요.

---

## 인증·CORS

- `Authorization: Bearer <IOT_API_KEY>` (iot-api `.env`와 동일 키)
- `Origin: https://iot.iwhya.kr` — OPTIONS preflight 200
- `register` / `unregister` 기존 유지

---

## API

### `GET /api/push/status`

```json
{
  "ok": true,
  "enabled": true,
  "lastSentAt": "2026-07-09T06:00:00.000Z",
  "nextAllowedAt": "2026-07-09T18:00:00.000Z"
}
```

12시간 제한: NAS enforcement. 필드 없으면 생략 가능.

### `POST /api/push/test`

- Body: `{}` 또는 empty → `{ "ok": true }`
- FCM 1건 발송, **12시간 제한 제외**

### `GET /api/push/tokens`

```json
{
  "ok": true,
  "tokens": [
    {
      "token": "fcm-token-string",
      "label": "web",
      "enabled": true,
      "registeredAt": "2026-07-09T00:00:00.000Z",
      "lastSeenAt": "2026-07-09T12:00:00.000Z"
    }
  ]
}
```

### `GET /api/push/history?limit=30`

```json
{
  "ok": true,
  "alerts": [
    {
      "id": "server-uuid-or-seq",
      "fingerprint": "stable-issue-fingerprint",
      "title": "에어컨 이상",
      "body": "…",
      "receivedAt": "2026-07-09T06:00:00.000Z",
      "topic": "ac-anomaly",
      "url": "/alerts/abc123",
      "issueId": "issue-1",
      "status": "warn",
      "overall": "fail",
      "checkedAtKst": "2026-07-09 15:00 KST",
      "llmEscalate": "false",
      "summary": "[{\"name\":\"온도\",\"status\":\"fail\"}]"
    }
  ]
}
```

---

## FCM `data` 권장 필드

| 필드 | 설명 |
|------|------|
| `fingerprint` | 필수 — dedup |
| `title`, `body` | 알림 제목·본문 |
| `topic` | `ac-anomaly`, `pc-offline`, `strip` 등 |
| `url` | 앱 내 경로 |
| `summary` | active checks JSON string |

Firebase JSON: NAS 로컬만 (GitHub Secret 금지)

---

## 스모크 (NAS)

```bash
KEY="<IOT_API_KEY>"
ORIGIN="https://iot.iwhya.kr"
BASE="https://iot.iwhya.kr"

curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE/api/push/status" \
  -H "Origin: $ORIGIN" -H "Access-Control-Request-Method: GET"

curl -s -H "Authorization: Bearer $KEY" -H "Origin: $ORIGIN" "$BASE/api/push/status"
curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{}' "$BASE/api/push/test"
curl -s -H "Authorization: Bearer $KEY" "$BASE/api/push/tokens"
curl -s -H "Authorization: Bearer $KEY" "$BASE/api/push/history?limit=5"
```
