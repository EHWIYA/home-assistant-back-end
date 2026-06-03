# [공조 회신] Hwiya 에어컨 자동제어 점검 — 백엔드 확인·조치

**대상**: 서버팀  
**일자**: 2026-06-03  
**repo**: home-assistant-back-end (iot-api)

---

## 1. IR 명령 정합성

| 항목 | 결과 |
|------|------|
| `ac_on` 참조 | **없음** (`app/constants.py`: `ac_preset_cool_17`, `ac_preset_dry_17`, `ac_off`만 사용) |
| NAS 이미지 버전 | 백엔드 로컬에서 NAS 컨테이너 직접 확인 불가. **서버에서** `docker inspect iot-api --format '{{.Image}}'` 또는 `curl -s http://127.0.0.1:8002/health` 후 최근 `main` push·GHA deploy 시각과 대조 권장 |

---

## 2. `ac_estimated_running` vs HA 논리 상태 — **조치함**

**문제**: 제습·저전력 구간에서 `sensor.hwiya_ac_auto_state=on`인데 플러그 &lt;50W → API `power=off`, `state_consistent=false`.

**조치** (이번 커밋):

- `/api/v1/status`의 `ac_estimated_running`: **플러그 W ≥ 임계값 OR `ac_auto_state.state == on`**
- `GET /api/v1/ac/state`: 동일 합성으로 `power` 계산, **`running_source`**: `plug` \| `logical` 추가
- `state_source` 문자열: `composed(plug_w,ac_auto_state,ha_input_select)`

프론트는 `/ac/state`의 `running_source`로 UI 표기(“추정/논리”) 분기 가능.

---

## 3. `POST /api/v1/ac/auto` — 콘센트 동기화 — **조치함**

**제품 판단**: 자동제어 OFF 시 `switch.hwiya_home`까지 끄는 것은 **비의도**로 보임 (전력·`ac_auto_state`·실내 센서 경로 유지 필요).

**변경**:

- `enabled=true`: 기존과 동일 — `input_boolean` ON + 콘센트 ON
- `enabled=false`: **`input_boolean`만 OFF**, 콘센트는 **건드리지 않음** (현재 스위치 상태만 응답에 반영)

---

## 4. `STATUS_ENTITY_IDS` / SSE 2차 — **부분 조치**

**이번에 목록 추가** (WS 캐시·REST 폴링 공통):

- `input_datetime.hwiya_ac_last_on` / `hwiya_ac_last_off`
- `binary_sensor.hwiya_ac_plug_active`

**Phase 2**: `COORD-BACKEND-PHASE2.md`는 이 repo에 없음. SSE/WS 2차 범위 문서화 시 위 엔티티 포함을 **백엔드 기본안**으로 제안. 프론트 구독 필드 변경은 별도 공조.

---

## 5. NAS 검증 (서버 실행)

배포 반영 후:

```bash
curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/ac/state
# 기대: 제습 저전력 + ac_auto_state=on → power=on, running_source=logical

curl -s -H "X-API-Key: …" http://127.0.0.1:8002/api/v1/status
# 기대: ac_estimated_running=true (동일 조건)
```

자동제어 OFF 후 콘센트가 **그대로 on**인지:

```bash
curl -s -X POST -H "X-API-Key: …" -H "Content-Type: application/json" \
  -d '{"enabled":false}' http://127.0.0.1:8002/api/v1/ac/auto
```

---

## 6. 프론트 공조 (필요 시)

`AcStateResponse`에 `running_source` 필드 추가 → iot-web `types.ts`·AC 카드 반영 여부는 프론트 담당과 협의.
