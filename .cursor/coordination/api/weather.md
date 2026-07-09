# 실외 날씨 API — 프론트 회신

**대상:** 프론트  
**일자:** 2026-06-04

---

## 체크리스트

| 항목 | 회신 |
|------|------|
| `GET /api/v1/weather/local` | 구현 완료 (v1.6.0) |
| 공공데이터 | 초단기실황 → SKY·결측 시 초단기예보 |
| 위치 | 금천구 가산동 nx=58, ny=125 |
| env | `KMA_SERVICE_KEY` (NAS `.env`) |
| SSE·status 통합 | v1 범위 외 |

---

## API

```
GET /api/v1/weather/local
X-API-Key: (기존과 동일)
```

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

캐시 TTL 기본 900초. 에러 503 `weather_unavailable`.

---

## `weather_outdoor` vs `weather_local`

| | 출처 | 용도 |
|---|------|------|
| `/status` → `weather_outdoor` | HA `weather.forecast_jib` | 에어컨 탭 |
| `/weather/local` | 기상청 | 홈 PWA 실외 날씨 |

---

## 프론트 후속

Open-Meteo 제거 → `GET /api/v1/weather/local`
