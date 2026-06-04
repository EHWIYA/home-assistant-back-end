"""KMA 동네예보 격자(nx, ny) — 위경도 → LCC 투영."""

from __future__ import annotations

import math


def lat_lon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위·경도(십진)를 기상청 5km 격자 좌표로 변환."""
    re = 6371.00877 / 5.0
    slat1 = math.radians(30.0)
    slat2 = math.radians(60.0)
    olon = math.radians(126.0)
    olat = math.radians(38.0)
    xo = 210.0 / 5.0
    yo = 675.0 / 5.0

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = re * sf / math.pow(math.tan(math.pi * 0.25 + olat * 0.5), sn)

    ra = math.tan(math.pi * 0.25 + math.radians(lat) * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = math.radians(lon) - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = ra * math.sin(theta) + xo
    y = ro - ra * math.cos(theta) + yo
    return int(x + 1.5), int(y + 1.5)
