"""거리·방위 계산."""
from __future__ import annotations

import math

EARTH_KM = 6371.0088
KM_PER_NM = 1.852

# 구룡포수협 위판장(E-UM S07_003). 기동 시 API 값으로 덮어쓴다.
AUCTION_PLACE = (35.989544, 129.555828)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """점1에서 점2를 바라보는 방위각(0=북, 시계방향)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    """두 방위의 차(0~180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d
