# GitHub Actions Secrets (iot-api)

**Settings → Secrets and variables → Actions → Repository secrets**

NAS `.env`는 **NAS `/home/iwh/apps/iot/api/.env`만** (서버 관리). Actions Secret 아님.

---

## deploy-nas job

| Secret | 설명 |
|--------|------|
| `NAS_HOST` | `100.88.40.125` (Tailscale IP). 공인 IP만 쓰면 hosted runner에서 timeout |
| `NAS_SSH_USER` | `iwh` |
| `NAS_SSH_KEY` | `github_actions_deploy` **private key** 전체 |

**순서:** workflow에서 **Tailscale connect → SSH**. `tailscale up` 없이 `100.x:22` SSH 시 timeout.

Repository variable `NAS_SSH_HOST_KEYS`에는 NAS에서 별도 확인한 SSH host 공개 키를
`nas-iot-approved <algorithm> <public-key>` 형식으로 등록한다. 여러 알고리즘은 줄로 구분한다.
private key를 이 변수에 넣지 않는다. CI는 HostKeyAlias와 StrictHostKeyChecking으로 이를
대조하며 누락/불일치 시 배포를 거부한다. 전용 배포 키의 forced command는 NAS 공통
로그 보존·정비 gate를 실행하므로 임의 셸/Compose 스크립트를 전달하지 않는다.

---

## Tailscale OIDC 인증

Repository variables `TS_OIDC_CLIENT_ID`, `TS_OIDC_AUDIENCE`는 공개 식별자이며 비밀 키가 아니다.
GitHub 실행별 단기 OIDC 증명을 Tailscale이 검증한다. 90일 auth key의 수동 갱신은 필요하지 않다.
`deploy-nas` job에만 `id-token: write`를 부여하고 Tailscale Action은 검증한 v4 커밋에 고정한다.

신뢰 조건은 이 저장소의 고정 ID·소유자 ID, main 브랜치 subject와
`.github/workflows/deploy.yml@refs/heads/main`이다. credential은 Auth Keys Write와
`tag:iot-ci`만 허용한다. CI 태그는 NAS TCP 22만 접근하며 기존 사용자 장치의 접근과
Tailscale SSH·Funnel 규칙은 유지한다. 태그를 다른 장치에 추가하지 않는다.

`.github/scripts/check-tailscale-oidc.py`는 실제 claims와 정상 토큰 교환 및 잘못된 audience의
거부를 확인한다. JWT·access token을 출력하거나 보관하지 않는다. OIDC/Tailscale 장애 때
auth key로 자동 우회하거나 권한을 확대하지 않는다. 복구는 배포 Runbook을 따른다.

2026-11-17 후속 점검에서 기존 키의 발급·등록 기록, 다른 저장소의 secret 갱신 시각,
현재 workflow와 NAS 자동화 참조를 확인한 뒤 이 저장소의 `TS_AUTH_KEY`를 삭제하고
해당 Tailscale auth key를 폐기했다. 다른 저장소의 동명 secret은 별개의 이전 키라 보존했다.
폐기된 키를 복구 수단으로 사용하지 않는다. OIDC credential과 공개 식별자는 유지한다.

---

## 자동 (등록 불필요)

| 이름 | 용도 |
|------|------|
| `GITHUB_TOKEN` | GHCR build·push (`packages: write`) |

---

## GHCR (공개)

```text
ghcr.io/ehwiya/home-assistant-back-end:latest
ghcr.io/ehwiya/home-assistant-back-end:sha-XXXXXXX   # 운영 pin (deploy 시 NAS .deploy-image)
```

롤백: `.github/DEPLOY_RUNBOOK.md`

---

## HA_BASE_URL (환경별)

| 환경 | HA_BASE_URL |
|------|-------------|
| 개발 PC (Tailscale) | `http://100.88.40.125:8123` |
| NAS Docker | `http://127.0.0.1:8123` (host network) |

로컬 `.env`를 NAS에 그대로 복사하지 않음.
