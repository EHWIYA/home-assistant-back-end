# 공휴일 JSON 자동 갱신 (NAS)

iot-api는 `KR_HOLIDAYS_DATA_DIR`(예: `/home/iwh/iot/api/data`) 아래 `kr-holidays-YYYY.json` 을 우선 로드합니다.

## 연 1회 cron (권장: 1월 1일 03:00 KST)

```bash
# /etc/cron.d/iot-kr-holidays (root)
0 3 1 1 * iwh DATA_SPCD_SERVICE_KEY=<공공데이터 특일 API 키> KR_HOLIDAYS_DATA_DIR=/home/iwh/iot/api/data /home/iwh/iot/api/scripts/refresh-kr-holidays.sh >> /var/log/iot-kr-holidays.log 2>&1
```

`DATA_SPCD_SERVICE_KEY` 가 없으면 스크립트는 skip (이미지 bundled JSON 사용).

## 수동

```bash
cd /home/iwh/iot/api
export KR_HOLIDAYS_DATA_DIR=/home/iwh/iot/api/data
export DATA_SPCD_SERVICE_KEY=...
bash scripts/refresh-kr-holidays.sh 2027
```

## iot-api `.env`

```env
KR_HOLIDAYS_DATA_DIR=/home/iwh/iot/api/data
```

NAS `docker-compose.yml` 에 data 볼륨 마운트가 필요하면 서버 담당이 추가:

```yaml
volumes:
  - ./data:/app/data:ro
```

(현재 기본은 이미지 bundled — 캐시 디렉터리는 env 경로를 앱이 읽음)
