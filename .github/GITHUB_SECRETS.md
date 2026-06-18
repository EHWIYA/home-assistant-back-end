# GitHub Actions Secrets (iot-api)

**Settings → Secrets and variables → Actions → Repository secrets**

NAS `.env`는 **NAS `/home/iwh/iot/api/.env`만** (서버 관리). Actions Secret 아님.

---

## deploy-nas job (4개)

| Secret | 설명 |
|--------|------|
| `TS_AUTH_KEY` | Tailscale auth key (Reusable + Ephemeral). **~90일 만료** → 아래 갱신 절차 |
| `NAS_HOST` | `100.88.40.125` (Tailscale IP). 공인 IP만 쓰면 hosted runner에서 timeout |
| `NAS_SSH_USER` | `iwh` |
| `NAS_SSH_KEY` | `github_actions_deploy` **private key** 전체 |

**순서:** workflow에서 **Tailscale connect → SSH**. `tailscale up` 없이 `100.x:22` SSH 시 timeout.

---

## TS_AUTH_KEY 만료 관리

| 시점 | 작업 |
|------|------|
| **발급일** | 캘린더에 **+75일** 알림 (만료 15일 전) |
| **만료 15일 전** | Tailscale Admin → Keys → Reusable key 재발급 |
| **갱신** | GitHub `TS_AUTH_KEY` Secret 덮어쓰기 → `workflow_dispatch` 로 deploy 테스트 |
| **실패 징후** | GHA `Tailscale connect` 또는 SSH 단계 fail |

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
