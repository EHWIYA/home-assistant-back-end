# iot-api 배포·롤백 Runbook

## 자동 배포 (정상)

`main` push → **CI pytest** → GHCR `:sha-XXXXXXX` + `:latest` → NAS SSH:

1. `.deploy-image` 에 pin 된 `IOT_API_IMAGE` 기록
2. `docker compose pull && up -d`
3. `/health` 확인

NAS compose (`docker-compose.yml`):

```yaml
image: ${IOT_API_IMAGE:-ghcr.io/ehwiya/home-assistant-back-end:latest}
```

## 수동 롤백 (이전 sha)

NAS에서:

```bash
cd /home/iwh/iot/api
export COMPOSE_PROJECT_NAME=iot-api

# 직전 배포 이미지 확인
cat .deploy-image
tail -5 .deploy-history.log

# 예: 이전 sha로 롤백
export IOT_API_IMAGE=ghcr.io/ehwiya/home-assistant-back-end:sha-abc1234
echo "$IOT_API_IMAGE" > .deploy-image
docker compose pull
docker compose up -d
curl -sf http://127.0.0.1:8002/health
```

`latest` 로 되돌리려면 `IOT_API_IMAGE` unset 후 pull:

```bash
unset IOT_API_IMAGE
docker compose pull
docker compose up -d
```

## 배포 실패 시

- GHA `deploy-nas` 가 fail → NAS 컨테이너는 이미 교체됐을 수 있음 → 로그 확인 후 위 롤백
- `alembic upgrade` 실패 → 컨테이너 로그 `docker compose logs iot-api`, DB 백업 후 수동 마이그레이션

## 이미지 태그 규칙

| 태그 | 용도 |
|------|------|
| `sha-XXXXXXX` | **운영 pin** (7자리 git short sha) |
| `latest` | 개발·수동 pull fallback |

## 관련

- Secrets·TS 키: `.github/GITHUB_SECRETS.md`
- 스케줄 timer: `infra/systemd/`
- 공휴일 갱신: `infra/docs/kr-holidays-cron.md`
