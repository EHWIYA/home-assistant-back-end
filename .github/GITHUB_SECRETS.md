# GitHub Actions Secrets (iot-api)

**Settings → Secrets and variables → Actions → Repository secrets**

NAS `.env`는 **NAS `/home/iwh/iot/api/.env`만** (서버 관리). Actions Secret 아님.

---

## deploy-nas job (4개)

| Secret | 설명 |
|--------|------|
| `TS_AUTH_KEY` | Tailscale auth key (Reusable + Ephemeral). **~90일 만료** → 만료 전 재발급·갱신 |
| `NAS_HOST` | `100.88.40.125` (Tailscale IP). 공인 IP만 쓰면 hosted runner에서 timeout |
| `NAS_SSH_USER` | `iwh` |
| `NAS_SSH_KEY` | `github_actions_deploy` **private key** 전체 |

**순서:** workflow에서 **Tailscale connect → SSH**. `tailscale up` 없이 `100.x:22` SSH 시 timeout.

---

## 자동 (등록 불필요)

| 이름 | 용도 |
|------|------|
| `GITHUB_TOKEN` | GHCR build·push (`packages: write`) |

---

## GHCR (공개)

```text
ghcr.io/ehwiya/home-assistant-back-end:latest
```

---

## HA_BASE_URL (환경별)

| 환경 | HA_BASE_URL |
|------|-------------|
| 개발 PC (Tailscale) | `http://100.88.40.125:8123` |
| NAS Docker | `http://host.docker.internal:8123` + compose `extra_hosts` |

로컬 `.env`를 NAS에 그대로 복사하지 않음.
