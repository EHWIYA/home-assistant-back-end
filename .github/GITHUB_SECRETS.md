# GitHub Actions Secrets (iot-api)

등록 위치: **Repository → Settings → Secrets and variables → Actions → New repository secret**

NAS `.env`(HA_TOKEN 등)는 **여기 넣지 않음** — NAS `/home/iwh/iot-api/.env` 에만 둠.

---

## 필수 (deploy-nas job)

| Secret 이름 | 설명 | 예시 / 비고 |
|-------------|------|-------------|
| `NAS_HOST` | NAS SSH 접속 주소 | `100.88.40.125` (Tailscale). GHA runner가 이 IP로 SSH 가능해야 함 |
| `NAS_SSH_USER` | SSH 로그인 사용자 | 서버 담당 확인 (예: `iwh`) |
| `NAS_SSH_KEY` | deploy용 **private key** 전체 | `-----BEGIN OPENSSH PRIVATE KEY-----` … 서버 `authorized_keys`에 public key 등록됨 (`github_actions_deploy` 등) |

서버 회신에 `NAS_SERVER_USER` / `NAS_SERVER_SSH_KEY` 로 적힌 경우 → **값은 동일**, workflow 에서 쓰는 이름은 위 표기준.

---

## 자동 (등록 불필요)

| 이름 | 용도 |
|------|------|
| `GITHUB_TOKEN` | `build-and-push` job 이 GHCR login·push (workflow `packages: write`) |

---

## GHCR 이미지 경로 (참고)

push 성공 후:

```text
ghcr.io/<GitHub-owner>/<repo-name>:latest
ghcr.io/<GitHub-owner>/<repo-name>:sha-<commit>
```

`<repo-name>` = 이 repository 이름 (예: `home-assistant-back-end`).

패키지 **공개/비공개**는 GitHub Packages 설정 — 비공개면 NAS에서 `docker login ghcr.io` 1회 필요.

---

## 등록 순서 (권장)

1. `main` push → GHCR 이미지 1회 생성 확인  
2. 서버 NAS 수동 `docker compose up` + `curl /health` 성공  
3. 위 Secrets 3개 등록  
4. `workflow_dispatch` 또는 `main` push 로 deploy-nas 재실행
