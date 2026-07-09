# 공조 — 로컬 HA 연동

**대상:** 서버  
**상태:** 완료 (2026-05-19) — `HA_BASE_URL`·`HA_TOKEN` 반영, `/health`·`/api/v1/status` 로컬 성공.

---

```text
[공조 요청] → 서버 담당

목적: 개발 PC에서 iot-api(백엔드) → Home Assistant 연동 여부 확인 (로컬 테스트)

필요 정보 (답변을 그대로 전달해 주세요):

1) HA_BASE_URL
   - 제 PC에서 iot-api가 호출할 HA REST 주소 (끝에 / 없이)
   - 예: http://100.88.40.125:8123 (Tailscale) 또는 http://192.168.0.19:8123 (LAN)

2) HA_TOKEN
   - 위 URL로 접속 가능한 계정 기준, HA 장기 액세스 토큰 1개
   - 생성: HA UI → 프로필 → 보안 → 장기 액세스 토큰 생성

3) 접속 조건 (짧게)
   - Tailscale ON 필요 여부
   - 집 LAN / Tailscale IP
   - UFW :8123 허용 여부

4) (선택) entity 확인
   - switch.hwiya_home, sensor.hwiya_home_power 등 Handoff entity 존재 여부

이유:
- 백엔드 .env에 HA_BASE_URL + HA_TOKEN 만 채우면 로컬 연동 완료 가능.
```

---

## 받은 뒤 (백엔드)

1. `.env`의 `HA_BASE_URL=`, `HA_TOKEN=` 에만 붙여넣기
2. `.\.cursor\scripts\dev-test.ps1` → uvicorn → `/health`, `/api/v1/status` 확인

`IOT_API_KEY`는 로컬용 기본값 유지. 프론트와 맞출 때만 변경.
