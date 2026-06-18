#!/usr/bin/env bash
# 대한민국 공휴일 JSON 갱신 (NAS 캐시 디렉터리)
# 공공데이터포털 특일정보 API 키가 있으면 fetch, 없으면 이미지 bundled 연도만 유지
#
# Usage:
#   DATA_SPCD_SERVICE_KEY=... ./scripts/refresh-kr-holidays.sh 2027
#   KR_HOLIDAYS_DATA_DIR=/home/iwh/iot/api/data ./scripts/refresh-kr-holidays.sh
#
set -euo pipefail

YEAR="${1:-$(date +%Y)}"
OUT_DIR="${KR_HOLIDAYS_DATA_DIR:-./data}"
KEY="${DATA_SPCD_SERVICE_KEY:-${KMA_SERVICE_KEY:-}}"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/kr-holidays-${YEAR}.json"

if [[ -z "${KEY}" ]]; then
  echo "No DATA_SPCD_SERVICE_KEY — skip API fetch for ${YEAR}" >&2
  echo "Set KR_HOLIDAYS_DATA_DIR on iot-api .env to use ${OUT_DIR}" >&2
  exit 0
fi

# 공공데이터포털 한국천문연구원 특일정보 (getRestDeInfo)
BASE="https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
URL="${BASE}?serviceKey=${KEY}&solYear=${YEAR}&numOfRows=100&_type=json"

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

curl -fsS "${URL}" -o "${tmp}"

python3 - <<'PY' "${tmp}" "${OUT_FILE}" "${YEAR}"
import json, sys
from pathlib import Path

src, out, year = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
payload = json.loads(src.read_text(encoding="utf-8"))
items = payload.get("response", {}).get("body", {}).get("items", {}).get("item", [])
if isinstance(items, dict):
    items = [items]
dates = sorted(
    {
        f"{it['locdate'][:4]}-{it['locdate'][4:6]}-{it['locdate'][6:8]}"
        for it in items
        if it.get("locdate")
    }
)
out.write_text(
    json.dumps({"year": year, "source": "api", "dates": dates}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Wrote {len(dates)} dates -> {out}")
PY

echo "Restart iot-api or wait for next deploy to pick up KR_HOLIDAYS_DATA_DIR"
