"""NAS/원격 iot-api 연동 스모크 (로컬 .env 또는 환경변수).

Usage (PowerShell):
  $env:IOT_API_BASE_URL = "https://iot-api.iwhya.kr"
  $env:IOT_API_KEY = "<NAS .env IOT_API_KEY>"
  python .cursor/scripts/nas-integration-smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("IOT_API_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
API_KEY = os.environ.get("IOT_API_KEY", "")


def get(path: str, api_key: bool = False) -> tuple[int, dict | str]:
    req = urllib.request.Request(f"{BASE}{path}")
    if api_key:
        if not API_KEY:
            return 0, "IOT_API_KEY not set"
        req.add_header("X-API-Key", API_KEY)
    ctx = None
    if BASE.startswith("https://"):
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def main() -> int:
    print(f"BASE={BASE}")
    code, health = get("/health")
    print(f"/health -> {code}: {json.dumps(health, ensure_ascii=False)}")
    if code != 200:
        return 1
    if isinstance(health, dict) and not health.get("ha_reachable"):
        print("FAIL: ha_reachable is false")
        return 1

    code, status = get("/api/v1/status", api_key=True)
    print(f"/api/v1/status -> {code}")
    if code != 200:
        print(status)
        return 1
    if isinstance(status, dict):
        plug = status.get("plug", {})
        print(
            "OK plug.switch=%s power_w=%s ac_estimated=%s person=%s"
            % (
                plug.get("switch"),
                plug.get("power_w"),
                status.get("ac_estimated_running"),
                (status.get("person") or {}).get("state"),
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
