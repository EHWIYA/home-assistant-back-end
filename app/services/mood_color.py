"""무드등 색상 변환 — light.mudeudeung(GKW-MD082)은 HA에서 hs 모드만 지원."""

from __future__ import annotations

# 프리셋 → hs_color (hue 0–360, saturation 0–100). warm/cool/rainbow는 GH 전용.
PRESET_HS_COLOR: dict[str, tuple[float, float]] = {
    "red": (0.0, 100.0),
    "blue": (240.0, 100.0),
    "green": (120.0, 100.0),
    "yellow": (60.0, 100.0),
    "purple": (300.0, 100.0),
    "white": (0.0, 0.0),
}

GH_ONLY_PRESET_COLORS = frozenset({"warm", "cool", "rainbow"})


def rgb_to_hs(r: int, g: int, b: int) -> tuple[float, float]:
    """RGB 0–255 → HA hs_color (hue 0–360, saturation 0–100)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx = max(rf, gf, bf)
    mn = min(rf, gf, bf)
    diff = mx - mn
    if diff == 0:
        hue = 0.0
    elif mx == rf:
        hue = (60.0 * ((gf - bf) / diff) + 360.0) % 360.0
    elif mx == gf:
        hue = (60.0 * ((bf - rf) / diff) + 120.0) % 360.0
    else:
        hue = (60.0 * ((rf - gf) / diff) + 240.0) % 360.0
    saturation = 0.0 if mx == 0.0 else (diff / mx) * 100.0
    return round(hue, 1), round(saturation, 1)
