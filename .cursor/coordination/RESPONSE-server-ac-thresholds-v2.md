# [공조 회신] AC 임계값 v2 · 3모드 mutex — 백엔드 조치

**대상**: 서버팀  
**일자**: 2026-06-04  
**repo**: home-assistant-back-end (iot-api)  
**OpenAPI**: `1.7.0`

---

## 1. 수신 요약

NAS HA에 임계값 v2 + 수동/자동/외출 3모드 mutex 배포 확인. 기존 `ac_auto_enabled` / `ac_away_enabled` / `POST /ac` 는 그대로 동작. PWA UX용 권장 API 확장을 반영했습니다.

---

## 2. 백엔드 조치 (이번)

| 항목 | 내용 |
|------|------|
| `ac_operating_mode` | `manual` \| `auto` \| `away` — `GET /status`, `GET /ac/state`, SSE `snapshot`/`status` (StatusResponse 필드) |
| 파생 규칙 | away ON → `away`; else auto ON → `auto`; else 둘 다 OFF → `manual` |
| `POST /api/v1/ac` | `operating_mode` 추가; `auto_enabled`+`away_enabled` 동시 ON 요청 시 **away 우선**으로 선처리 |
| `POST /api/v1/ac/auto` | `enabled=true` 시 away OFF 선행 (mutex) |
| `GET /api/v1/ac/thresholds` | HA automation v2 임계값 안내 (정본은 HA) |
| pytest | `derive`/`resolve` mutex, `operating_mode` POST, thresholds |

기존 필드·엔드포인트 **유지**: `ac_mode`, `ac_last_run_mode`, `ac_auto_state`, IR `cool`/`dry`/`off`/`auto`.

---

## 3. 프론트 공조 (권장)

```text
[공조 요청] → 프론트 담당

목적: AC 3모드 단일 UI (v2 임계값 안내)
필요:
 - types.ts: ac_operating_mode, AcActionRequest.operating_mode, AcStateResponse.operating_mode
 - 모드 전환: POST /ac { mode, operating_mode: "manual"|"auto"|"away" } (또는 기존 boolean 병행)
 - 안내 문구: GET /ac/thresholds 또는 OpenAPI description
이유: iot-api 1.7.0 스키마 확정 (백엔드 배포 후 GHCR/NAS pull)
```

---

## 4. NAS 검증 (서버)

배포 후:

```bash
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/status | jq .ac_operating_mode
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/ac/thresholds
```

---

## 5. 참고

- HA mutex 정본: `input_boolean.hwiya_ac_auto_enabled` / `hwiya_ac_away_enabled`
- API mutex는 클라이언트 실수·레이스 완화용; HA automation이 최종 권한
