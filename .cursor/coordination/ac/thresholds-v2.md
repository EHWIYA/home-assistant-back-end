# AC 임계값 v2 · 3모드 mutex — 서버 회신

**대상:** 서버  
**일자:** 2026-06-04 · OpenAPI `1.7.0`

---

## 백엔드 조치

| 항목 | 내용 |
|------|------|
| `ac_operating_mode` | `manual` \| `auto` \| `away` — status/ac/state/SSE |
| 파생 | away ON → away; else auto ON → auto; else manual |
| `POST /ac` | `operating_mode` 추가; auto+away 동시 ON → away 우선 |
| `POST /ac/auto` | `enabled=true` 시 away OFF 선행 |
| `GET /ac/thresholds` | HA automation v2 임계값 안내 |

기존 필드·엔드포인트 유지.

---

## 프론트 공조

```text
[공조 요청] → 프론트 담당

목적: AC 3모드 단일 UI
필요: types.ts ac_operating_mode, POST /ac { operating_mode }
```

---

## NAS 검증

```bash
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/status | jq .ac_operating_mode
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/ac/thresholds
```
