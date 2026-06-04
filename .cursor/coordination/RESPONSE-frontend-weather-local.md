# [공조 회신] PWA 홈 실외 날씨 API — 백엔드 검토·구현

**대상**: 프론트팀  
**일자**: 2026-06-04  
**repo**: home-assistant-back-end (iot-api)

---

## 1. 체크리스트 회신

| 항목 | 회신 |
|------|------|
| `GET /api/v1/weather/local` | **구현 완료** (v1.6.0). NAS·로컬 `.env`에 `KMA_SERVICE_KEY` 반영됨 |
| 공공데이터 API | **초단기실황(`getUltraSrtNcst`)** 우선 → SKY·결측 시 **초단기예보(`getUltraSrtFcst`)** 보완 |
| 가산동 위치 | **금천구 가산동** 확정 (사용자·기획 확인). 격자 **nx=58, ny=125** (37.4780, 126.8875) |
| serviceKey 환경 변수 | **`KMA_SERVICE_KEY`** (로컬·NAS `.env`, GHA Secret 아님) |
| `weather_outdoor` 문서화 | OpenAPI `Field` description 반영 — HA `weather.forecast_jib`, 기상청 아님 |
| rename (`weather_ac_outdoor` 등) | **당장 보류** (breaking). 문서로 구분. rename 필요 시 프론트 일정 맞춰 별도 PR |
| OpenAPI | `/docs`, `/openapi.json`에 `WeatherLocalResponse`·`/weather/local` 반영됨 |
| SSE·status 통합 | **v1 범위 외** (별도 REST + 서버 캐시로 충분) |

---

## 2. API 스펙 (확정)

```
GET /api/v1/weather/local
X-API-Key: (기존과 동일)
```

응답 예시:

```json
{
  "location_label": "서울 금천구 가산동",
  "location_short_label": "가산동",
  "temperature": 28.0,
  "humidity": 54,
  "condition": "구름많음",
  "condition_code": "3",
  "observed_at": "2026-06-04T11:00:00+09:00",
  "source": "kma",
  "source_detail": "초단기실황+초단기예보"
}
```

- **캐시**: 서버 메모리, TTL 기본 **900초(15분)** — `WEATHER_CACHE_TTL_SECONDS`
- **에러**: 503, `{"detail":"...", "code":"weather_unavailable"}`
- **KMA API**: `VilageFcstInfoService_2.0` — `getUltraSrtNcst` + `getUltraSrtFcst` (공공데이터 스크린샷과 동일)
- **인증키**: Decoding(일반) 또는 Encoding(`%` 포함) 모두 지원. 401 시 포털 마이페이지 키 재복사

---

## 3. `weather_outdoor` vs `weather_local`

| 필드 / API | 출처 | 용도 |
|------------|------|------|
| `GET /status` → `weather_outdoor` | HA `weather.forecast_jib` | 에어컨 탭 — 실외기/외기 추정 |
| `GET /weather/local` | 공공데이터 기상청 | 홈 PWA 실외 날씨 |

`weather_outdoor.condition`: HA `attributes.condition` 또는 entity `state` (영문/HA 표기). **항상 반환 시도**하나 entity 없으면 `weather_outdoor` 자체가 `null`.

---

## 4. 서버 공조 (배포 전)

```text
[공조 요청] → 서버 담당

목적: 실외 날씨 API 운영
필요 정보/작업:
 - 공공데이터포털 「기상청_동네예보 조회서비스」 활용신청·인증키
 - NAS `/home/iwh/iot/api/.env` 에 `KMA_SERVICE_KEY=...` 추가
 - iot-api 이미지 pull/up (v1.6.0+)
이유: 키 없으면 `/weather/local` → 503 weather_unavailable
```

---

## 5. 프론트 후속

- Open-Meteo 제거 → `GET /api/v1/weather/local`
- mock: 위 JSON 샘플 사용 가능 (`location_short_label`: 가산동)
- API·NAS 키 반영 후 전환 PR 진행 권장

---

## 6. 선택 env (기본값으로 동작)

| 변수 | 기본 |
|------|------|
| `WEATHER_LOCAL_NX` | 58 |
| `WEATHER_LOCAL_NY` | 125 |
| `WEATHER_LOCAL_LABEL` | 서울 금천구 가산동 |
| `WEATHER_LOCAL_SHORT_LABEL` | 가산동 |
| `WEATHER_CACHE_TTL_SECONDS` | 900 |
