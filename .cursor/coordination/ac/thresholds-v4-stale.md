# AC freshness + thresholds v4 — 백엔드 회신

**대상:** 서버 · 프론트  
**일자:** 2026-07-14 · OpenAPI `2.1.0`

---

## 백엔드 조치

| 항목 | 내용 |
|------|------|
| `GET /status` · `GET /ac/state` | `power_updated_at`, `power_age_seconds`, `power_stale`(기본 600s), `ac_running_confidence` |
| stale 시 가동 | 플러그 W로 on 확정 안 함 → `logical`(auto_state)만; confidence=`low` |
| `GET /ac/thresholds` | HA v4.0 — home ≥27 / 26~26.5 제습 / \<26 OFF · away ≥28/\<28 · 가동 ≥15W |
| `AC_POWER_THRESHOLD_W` | 기본·문서 `15` (잔존 50 정리) |
| `AC_POWER_STALE_SECONDS` | 기본 `600` |

## 프론트 공조

```text
[공조 요청] → 프론트 담당

목적: ST 전력 미갱신 시 ‘꺼짐’ 오판 방지 + thresholds v4 UI
필요:
 - types.ts: plug.power_* · ac_running_confidence · AcStateResponse 동일 필드
 - power_stale / confidence=low 이면 꺼짐·IR OFF 확정 UI 금지
 - thresholds 카피 v4 (≥27 / <26 / away 28)
```

## NAS 검증

```bash
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/ac/thresholds | jq .
# version=v4.0, ≥27, <26, 28
~/iot/scripts/iot-stack-verify.sh   # thresholds OK 기대
```
