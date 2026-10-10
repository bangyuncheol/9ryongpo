"""교통 센서·교통량·혼잡율(E-UM S07_001/004/005). 저장하지 않고 실시간 조회 + 5분 메모리 캐시(설계 §5.4)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .. import geo
from ..eum import EumClient, EumError

log = logging.getLogger(__name__)
CACHE_TTL_S = 300
DEFAULT_SENSOR = "교통센서3"  # 위판장 80m 앞


def parse_sensors(items: list[dict], place: tuple[float, float]) -> list[dict]:
    out = []
    for s in items:
        try:
            lat, lon = float(s["latitude"]), float(s["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "id": s.get("id"), "name": s.get("name"), "nickname": s.get("nickname"),
            "address": s.get("address"), "lat": lat, "lon": lon,
            "dist_m": round(geo.haversine_km(place[0], place[1], lat, lon) * 1000),
        })
    return sorted(out, key=lambda x: x["dist_m"])


def _hour_key(s: str) -> datetime | None:
    """'2026-10-09 12' 또는 '2026-10-08 23:00:00.0' → 정시 datetime."""
    s = s.strip()
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H", 13)):
        try:
            return datetime.strptime(s[:n], fmt)
        except ValueError:
            continue
    return None


def compare_level(now: float | None, before: float | None) -> str:
    if now is None or before is None:
        return "비교 불가"
    if abs(now - before) < 5:  # 상대 지수라 아주 작은 차이는 같다고 본다
        return "비슷"
    ratio = now / before if before > 0 else float("inf")
    if ratio >= 1.2:
        return "붐빔"
    if ratio <= 0.8:
        return "한산"
    return "비슷"


def day_position(now: float | None, values: list[float]) -> str:
    """지금 값이 최근 24시간 분포에서 어디쯤인지. 어제 같은 시각이 응답에 없을 때도 항상 답할 수 있다."""
    if now is None or len(values) < 6:
        return "비교 불가"
    below = sum(v < now for v in values) / len(values)
    if below >= 2 / 3:
        return "붐비는 편"
    if below <= 1 / 3:
        return "한산한 편"
    return "보통"


def summarize(per_hour: dict[str, list[dict]], congestion: list[dict], sensor: str) -> dict[str, Any]:
    rows = []
    for r in per_hour.get(sensor, []):
        h = _hour_key(str(r.get("time", "")))
        if h is None:
            continue
        rows.append({
            "hour": h.strftime("%Y-%m-%dT%H:00"),
            "truck": int(r.get("truck") or 0) + int(r.get("lorry") or 0),
            "car": int(r.get("car") or 0), "bus": int(r.get("bus") or 0),
            "total": int(r.get("sumCnt") or 0),
        })
    rows.sort(key=lambda x: x["hour"])

    cong = []
    for c in congestion:
        h = _hour_key(str(c.get("hour", "")))
        if h is not None and c.get("cntPerc") is not None:
            cong.append({"hour": h, "value": round(float(c["cntPerc"]), 1)})
    cong.sort(key=lambda x: x["hour"])
    now_c = cong[-1] if cong else None
    before_c = None
    if now_c:
        target = now_c["hour"] - timedelta(hours=24)
        before_c = next((c for c in cong if c["hour"] == target), None)

    return {
        "sensor": sensor,
        "hours": rows,
        "last_hour": rows[-1] if rows else None,
        "congestion": [{"hour": c["hour"].strftime("%Y-%m-%dT%H:00"), "value": c["value"]} for c in cong],
        "vs_yesterday": {
            "now": now_c["value"] if now_c else None,
            "yesterday": before_c["value"] if before_c else None,
            "hour": now_c["hour"].strftime("%H:00") if now_c else None,
            "level": compare_level(now_c["value"] if now_c else None, before_c["value"] if before_c else None),
        },
        # 혼잡율 응답이 23시간만 올 때가 있어(10/9 확인) 어제 같은 시각이 없을 수 있다. 이 값은 항상 계산된다.
        "vs_day": day_position(now_c["value"] if now_c else None, [c["value"] for c in cong]),
    }


def last_hour_by_sensor(per_hour: dict[str, list[dict]], sensors: list[dict], max_m: int = 1000) -> list[dict]:
    """위판장 max_m 안 센서마다 지난 1시간 트럭·전체 수. 트럭의 위치가 아니라 '그 지점을 지나간 수'다."""
    out = []
    for s in sensors:
        if s["dist_m"] > max_m:
            continue
        rows = [(h, r) for r in per_hour.get(s["name"], []) if (h := _hour_key(str(r.get("time", "")))) is not None]
        if not rows:
            continue
        h, r = max(rows, key=lambda x: x[0])
        out.append({"name": s["name"], "nickname": s.get("nickname"), "lat": s["lat"], "lon": s["lon"],
                    "dist_m": s["dist_m"], "hour": h.strftime("%Y-%m-%dT%H:00"),
                    "truck": int(r.get("truck") or 0) + int(r.get("lorry") or 0), "total": int(r.get("sumCnt") or 0)})
    return sorted(out, key=lambda x: x["dist_m"])


@dataclass
class TrafficService:
    eum: EumClient
    place: tuple[float, float] = geo.AUCTION_PLACE
    sensors: list[dict] = field(default_factory=list)
    _cache: dict[str, Any] | None = None
    _cache_at: float = 0.0
    _per_hour: dict[str, list[dict]] = field(default_factory=dict)  # 11개 센서 원본(같은 5분 캐시)

    async def load_sensors(self) -> None:
        self.sensors = parse_sensors(await self.eum.sensors(), self.place)

    async def now(self, sensor: str = DEFAULT_SENSOR) -> dict[str, Any]:
        """실측 요약. 캐시가 5분 안이면 캐시. 호출 실패 시 이전 값이 있으면 stale 표시로 돌려준다."""
        if self._cache and self._cache["sensor"] == sensor and time.monotonic() - self._cache_at < CACHE_TTL_S:
            return self._cache
        try:
            per_hour = await self.eum.traffic_per_hour()
            congestion = await self.eum.congestion()
        except EumError as e:
            log.warning("교통 조회 실패: %s", e)
            if self._cache and self._cache["sensor"] == sensor:
                return {**self._cache, "stale": True}
            raise
        self._per_hour = per_hour
        data = summarize(per_hour, congestion, sensor)
        data["fetched_at"] = datetime.now().isoformat(timespec="seconds")
        data["stale"] = False
        self._cache, self._cache_at = data, time.monotonic()
        return data

    async def nearby(self, max_m: int = 1000) -> dict[str, Any]:
        """지도용: 위판장 주변 센서별 지난 1시간 트럭 수. now()와 같은 조회·캐시를 쓴다."""
        base = await self.now()
        return {"fetched_at": base.get("fetched_at"), "stale": base.get("stale", False),
                "sensors": last_hour_by_sensor(self._per_hour, self.sensors, max_m)}
