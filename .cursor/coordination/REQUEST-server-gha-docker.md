# 공조 요청 — 서버 담당 (GHA → NAS Docker 배포 준비)

**상태:** 대기 (push 전 확인)

---

```text
[공조 요청] → 서버 담당

목적: main push 시 GitHub Actions가 GHCR 이미지 빌드 후 NAS에서 iot-api 컨테이너를 pull/up 하는 환경이 갖춰졌는지 확인

배경 (백엔드 repo):
- push main → GHA job 1: Docker build → ghcr.io/<github-org>/<repo-name>:latest
- GHA job 2: SSH NAS → cd /home/iwh/iot-api && docker compose pull && docker compose up -d
- NAS .env 는 GHA가 덮어쓰지 않음 (이미지만 갱신)

확인·준비 요청 사항:

1) NAS 디렉터리
   - /home/iwh/iot-api/ 존재 여부
   - docker-compose.yml 배치 (image: ghcr.io/<실제-org>/home-assistant-back-end:latest 등 repo명에 맞게)
   - .env 수동 1회 (HA_TOKEN, IOT_API_KEY, HA_BASE_URL, CORS_ORIGINS 등)

2) Docker / Compose
   - NAS에 docker, docker compose(v2) 사용 가능
   - 수동 테스트: docker compose pull && docker compose up -d 성공 여부

3) GHCR pull
   - ghcr.io 비공개 패키지면 NAS에서 docker login ghcr.io (PAT) 필요 — 계정/토큰 누가 관리하는지
   - 공개 패키지면 login 없이 pull 가능한지

4) HA ↔ 컨테이너 네트워크
   - HA가 host network면: iot-api도 network_mode: host 또는 HA_BASE_URL=http://192.168.0.19:8123 등 확정값
   - 컨테이너에서 HA /api/ ping 가능 여부

5) 포트
   - 호스트 127.0.0.1:8002 바인딩 (nginx → proxy_pass 용)
   - ss -tlnp | grep 8002 충돌 없음

6) GitHub (백엔드 repo Secrets — 서버 담당이 값 제공·등록 협조)
   - NAS_HOST (예: 100.88.40.125 Tailscale 또는 LAN, GHA runner가 SSH 가능한 주소)
   - NAS_SSH_USER
   - NAS_SSH_KEY (deploy용 private key, NAS authorized_keys 등록됨)
   ※ Secrets 등록은 백엔드 repo 관리자(GitHub) 화면에서 함 — 값만 서버 쪽에서 전달

7) nginx (이번 단계 포함 여부)
   - iot-api.iwhya.kr → 127.0.0.1:8002 이미 있는지 / push 후 별도 작업인지

8) 방화벽 / SSH
   - GitHub Actions runner IP 대역에서 NAS SSH 허용 여부 (또는 Tailscale SSH만 등)

답변 형식 (짧게):
- [ ] 1~8 항목 준비됨 / [ ] 미준비 (항목 번호)
- compose image 실제 경로:
- HA_BASE_URL (컨테이너 기준):
- push 전에 백엔드가 해야 할 일 (있다면):

범위 밖: iot-web 프론트 배포, HA 장기 토큰 재발급(로컬 dev는 완료)

이유:
- push 후 deploy job 실패 시 원인이 NAS 미구성 vs GitHub Secrets vs GHCR 권한인지 나누기 어려움
- push 전에 서버 측 1회 수동 compose up 성공이 있으면 GHA만 남음
```
