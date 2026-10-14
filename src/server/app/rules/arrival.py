"""입항 판정(설계 §5.1). 숫자는 이 룰이 내고 LLM은 문장만 쓴다."""
from __future__ import annotations

from datetime import datetime, timedelta

from .. import geo

MAX_KM = 15.0
MIN_SPEED_KN = 2.0
MAX_HEADING_DIFF = 35.0
ARRIVED_KM = 0.5
# 항구 안(위판장 1.5km 이내)에서는 방향 조건을 보지 않는다(10/11 오너 승인). 방파제 입구를 돌 때 배가
# 서남서→북으로 꺾어 위판장 방향과 80° 가까이 어긋나, 0.5~0.6km 구간에서 1~2분 동안 '입항 중'에서 빠졌다.
# 거리가 줄어드는 조건·2노트 이상 조건은 그대로라 항구에서 나가는 배는 계속 제외된다.
HARBOR_KM = 1.5


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
        speed, course = p.get("speed") or 0.0, p.get("course")
        if d <= ARRIVED_KM:
            # 항구 안에서 2kn 이상으로 멀어지는 배는 출항 중이다. '입항'으로 세지 않는다(10/15: 종일 드나드는 시뮬레이터)
            leaving = speed >= MIN_SPEED_KN and sid in prev_d and d > prev_d[sid]
            if not leaving:
                arrived.append({**base, "status": "입항"})
            continue
        if d > MAX_KM or speed < MIN_SPEED_KN or course is None:
            continue
        if d > HARBOR_KM and geo.angle_diff(float(course), geo.bearing_deg(p["lat"], p["lon"], *place)) > MAX_HEADING_DIFF:
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
