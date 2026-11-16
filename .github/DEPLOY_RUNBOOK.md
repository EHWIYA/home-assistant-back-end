# iot-api 배포·롤백 Runbook

## 자동 배포 (정상)

`main` push → pytest → GHCR build/push → immutable digest → NAS 공통 배포 진입점.

1. CI는 빌드 digest·전체 commit SHA·run ID를 전용 SSH 키로 전달한다.
2. NAS의 `iot_maintenance.py ssh`는 허용 저장소 digest와 OCI revision을 대조한다. 정비 표식이 있으면 pull/기동/재생성 모두 거부한다.
3. 원래 실행 상태·승인 ID·환경·네트워크를 확인하고 HDD에서 원문 백업을 검증한다. API 정지 후 최종 로그 보관까지 검증해야 API를 교체한다.
4. API 한 개만 만들며 DB/HA·다른 서비스는 재생성하지 않는다. 새 로그 mount와 Docker 로그를 유지하고, health·후속 백업 검증 후 원래 재시작 정책을 복원한다.
5. 실패하면 영구 배포 표식과 원본 로그를 남긴다. 자동 강제 제거·재시도·정비 표식 만료 해제는 하지 않는다.

운영 경로는 `/home/iwh/apps/iot/api`, Compose project는 `api`다. 배포는 NAS 공통 도구가 수행하므로 CI에서 직접 Compose 명령을 실행하지 않는다. 동일 CI run의 검증 완료 요청은 다시 재생성하지 않는다. 전체 workflow는 concurrency로 직렬화한다.

## 현재 이미지로 경로 검증

`workflow_dispatch`의 `connect_only=true`는 pytest/build/push 이후 OIDC 토큰 교환과
Tailscale 연결·NAS SSH 포트 도달 및 HTTPS 포트 차단만 확인한다. SSH 배포 명령을
실행하지 않으며 API를 정지·재생성하지 않는다. 정상 배포는 `connect_only=false`다.

`workflow_dispatch`의 `verify_current=true`는 정상 pytest/build/push와 후보 digest 준비·revision 대조를 수행한다. 운영 API는 현재 이미지로 재생성해 로그 보존 경로를 검증한다. 후보 앱 버전을 운영에 활성화한 시험과 구분한다. 일반 main push와 기본 수동 실행은 새 후보 이미지를 배포한다.

## 복구

OIDC 장애 시 먼저 CI를 보류하고 NAS 서비스 상태를 확인한다. 원문 로그 보존·정비 gate는
변경하지 않는다. HDD snapshot `iot-ci-oidc-20261117`에 기존 workflow와 Tailscale 정책이
있다. 보존한 `TS_AUTH_KEY`가 유효한 동안에는 검토 후 인증 단계만 기존 v3/authkey로
복원할 수 있다. 기존 키는 자동 fallback으로 참조하지 않으며 검증 성공 전 삭제하지 않는다.
정책 복구가 필요하면 승인된 기존 장치 접근·Funnel 상태와 새 CI 연결 영향을 함께 확인한다.
OIDC credential의 수동 회수, 저장소/브랜치/워크플로 이동, SSH 키 또는 NAS GitHub 인증 만료는
별도 대응이 필요하다. 정상 OIDC 운영에는 90일 Tailscale auth key 갱신이 필요하지 않다.

NAS 운영자는 정비 표식·잠금과 실제 컨테이너 상태를 먼저 확인한다. generation의 `predecessor-backup.json`·`deployment-receipt.json`에 이전 이미지/최종 로그 보관 위치/CI 출처가 있다. 새 로그를 보관한 뒤 승인된 이전 로컬 이미지로 API만 명시적으로 복구한다. host 로그·HDD 백업·정비 gate는 유지하며 DB schema를 자동 역변경하지 않는다. 무조건적인 down/rm/latest fallback은 사용하지 않는다. 검증 영수증 없이 표식을 삭제하지 않는다.

NAS 운영·백업·복구 정본은 `/home/iwh/docs/codex/nas-ssl-services.md`이며 중요한 변경 전 HDD snapshot이 필요하다.

## 배포 실패 시

- GHA `deploy-nas` 실패는 준비 단계와 교체 이후를 구분한다. 이미지/백업 사전 검사 실패는 기존 API를 정지하지 않는다. 교체 이후 실패는 표식·HDD 로그·실제 상태를 대조해 복구한다.
- `alembic upgrade` 실패 → 컨테이너 로그 `docker compose logs iot-api`, DB 백업 후 수동 마이그레이션

## 이미지 태그 규칙

| 태그 | 용도 |
|------|------|
| `@sha256:...` | 운영 배포 pin, OCI revision과 전체 commit 대조 |
| `sha-XXXXXXX`, `latest` | 검색용 태그. 자동 배포/복구의 식별자로 사용하지 않음 |

## 관련

- Secrets·TS 키: `.github/GITHUB_SECRETS.md`
- 스케줄 timer: `infra/systemd/`
- 공휴일 갱신: `infra/docs/kr-holidays-cron.md`
