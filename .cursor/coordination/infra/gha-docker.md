# 공조 — GHA → NAS Docker 배포

**대상:** 서버  
**상태:** 대기 (push 전 확인)

---

```text
[공조 요청] → 서버 담당

목적: main push 시 GHA가 GHCR 빌드 후 NAS에서 iot-api pull/up 가능한지 확인

확인·준비 요청:

1) /home/iwh/iot-api/ — compose.yml, .env (GHA가 .env 덮어쓰지 않음)
2) docker compose pull && up -d 수동 성공
3) GHCR pull (비공개면 docker login ghcr.io)
4) HA ↔ 컨테이너: network_mode: host 또는 HA_BASE_URL 확정
5) 127.0.0.1:8002 바인딩, 포트 충돌 없음
6) GitHub Secrets: NAS_HOST, NAS_SSH_USER, NAS_SSH_KEY
7) nginx iot-api.iwhya.kr → 127.0.0.1:8002
8) GHA runner → NAS SSH 허용

답변: 1~8 준비 여부, compose image 경로, HA_BASE_URL (컨테이너 기준)
```
