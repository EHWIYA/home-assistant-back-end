# 공조 요청 — 서버 담당 (로컬 HA 연동)

**상태: 완료** (2026-05-19) — `HA_BASE_URL`·`HA_TOKEN` 반영, `/health`·`/api/v1/status` 로컬 성공.

아래 블록을 그대로 복사해 서버 담당에게 전달하세요.

---

```text
[공조 요청] → 서버 담당

목적: 개발 PC에서 iot-api(백엔드) → Home Assistant 연동 여부 확인 (로컬 테스트)

필요 정보 (답변을 그대로 전달해 주세요):

1) HA_BASE_URL
   - 제 PC에서 iot-api가 호출할 HA REST 주소 (끝에 / 없이)
   - 예: http://100.88.40.125:8123 (Tailscale) 또는 http://192.168.0.19:8123 (LAN)
   - 확인: 해당 URL로 브라우저에서 HA 로그인 화면이 열리는지

2) HA_TOKEN
   - 위 URL로 접속 가능한 계정 기준, HA 장기 액세스 토큰 1개
   - 생성: HA UI → 프로필 → 보안 → 장기 액세스 토큰 생성
   - (보안) 채팅/메일 말고 1:1·비밀번호 관리자 등 안전한 경로로 전달해 주세요

3) 접속 조건 (짧게)
   - Tailscale ON 필요 여부 (예/아니오)
   - 집 LAN에만 되는지 / Tailscale IP로만 되는지
   - UFW 등으로 :8123 이 막혀 있으면 개발 PC IP 허용 필요 여부

4) (선택) entity 확인
   - switch.hwiya_home, sensor.hwiya_home_power 등 Handoff entity가 HA에 존재하는지

이유:
- 백엔드 .env에 HA_BASE_URL + HA_TOKEN 만 채우면
  curl /health → ha_reachable
  curl /api/v1/status → plug·전력 JSON
  로 로컬 연동 완료 가능합니다.

프론트(iot-web) / NAS iot-api Docker 배포 / nginx 는 이 단계 범위 밖입니다.
```

---

## 받은 뒤 (백엔드)

1. `.env`의 `HA_BASE_URL=`, `HA_TOKEN=` 에만 붙여넣기
2. 터미널:

```powershell
.\.cursor\scripts\dev-test.ps1
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
curl http://127.0.0.1:8002/health
curl -H "X-API-Key: (see .env IOT_API_KEY)" http://127.0.0.1:8002/api/v1/status
```

`IOT_API_KEY`는 이미 로컬용으로 채워 둠. 프론트 담당과 맞출 때만 변경.
