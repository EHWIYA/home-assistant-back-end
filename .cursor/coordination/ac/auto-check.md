# AC 자동제어 점검 — 서버 회신

**대상:** 서버  
**일자:** 2026-06-03

---

## 1. IR 명령

| 항목 | 결과 |
|------|------|
| `ac_on` 참조 | 없음 (`ac_preset_cool_17`, `ac_preset_dry_17`, `ac_off`만) |
| NAS 이미지 | 70892cb — GHA deploy 실패 시 수동 `compose pull/up` |

---

## 2. `ac_estimated_running` — 조치함

제습·저전력 + `ac_auto_state=on` → 플러그 &lt;50W 문제 해소:

- `ac_estimated_running`: 플러그 W ≥ 임계값 **OR** `ac_auto_state.state == on`
- `GET /ac/state`: `running_source`: `plug` \| `logical`

---

## 3. `POST /ac/auto` — 조치함

- `enabled=true`: input_boolean ON + 콘센트 ON
- `enabled=false`: **input_boolean만 OFF**, 콘센트 유지

---

## 4. SSE entity — 부분 조치

추가: `input_datetime.hwiya_ac_last_on/off`, `binary_sensor.hwiya_ac_plug_active`

---

## 5. NAS 검증

```bash
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/ac/state
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/status
curl -s -X POST -H "X-API-Key: …" -H "Content-Type: application/json" \
  -d '{"enabled":false}' http://127.0.0.1:8002/api/v1/ac/auto
```
