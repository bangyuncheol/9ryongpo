"""입항 판정(설계 §5.1). 숫자는 이 룰이 내고 LLM은 문장만 쓴다."""
from __future__ import annotations

from datetime import datetime, timedelta

from .. import geo

MAX_KM = 15.0
MIN_SPEED_KN = 2.0
MAX_HEADING_DIFF = 35.0
ARRIVED_KM = 0.5


def judge(current: list[dict], previous: list[dict], fleet: dict[int, dict], now: datetime,
          place: tuple[float, float]) -> dict[str, list[dict]]:
    """current/previous: ships_pos 형식 스냅샷. 반환: {'arriving': [...ETA순], 'arrived': [...]}"""
    prev_d = {p["ship_id"]: geo.haversine_km(p["lat"], p["lon"], *place) for p in previous}
    arriving, arrived = [], []
    for p in current:
        sid = p["ship_id"]
        info = fleet.get(sid, {})
        d = geo.haversine_km(p["lat"], p["lon"], *place)
        base = {"ship_id": sid, "name": info.get("name"), "biz": info.get("biz"), "gt": info.get("gt"),
                "d_km": round(d, 2), "lat": p["lat"], "lon": p["lon"]}
        if d <= ARRIVED_KM:
            arrived.append({**base, "status": "입항"})
            continue
        speed, course = p.get("speed") or 0.0, p.get("course")
        if d > MAX_KM or speed < MIN_SPEED_KN or course is None:
            continue
        if geo.angle_diff(float(course), geo.bearing_deg(p["lat"], p["lon"], *place)) > MAX_HEADING_DIFF:
            continue
        closing = None
        if sid in prev_d:
            closing = d < prev_d[sid]
            if not closing:
                continue
        eta = now + timedelta(hours=d / (speed * geo.KM_PER_NM))
        arriving.append({**base, "status": "입항 중", "speed_kn": round(float(speed), 1),
                         "eta": eta.isoformat(timespec="minutes"),
                         "confidence": "높음" if closing else "보통"})
    arriving.sort(key=lambda x: x["eta"])
    return {"arriving": arriving, "arrived": arrived}
