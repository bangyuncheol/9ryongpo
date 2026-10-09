"""선박 위치 시뮬레이터(설계 §5.5, §1-13).

E-UM 선박 위치가 2025-04-27에 멈춰 있어, 같은 스키마로 새벽 입항을 재생한다.
- 데모 핵심 배는 대본(KEY_SHIPS)으로 출발 위치·시각·속도를 고정한다.
- 나머지 배는 실제 마지막 위치(start_positions.json)에서 시작하고, 시드 고정 난수로 조업/입항을 정한다.
- 위치는 시각의 순수 함수다. 되감기·배속은 시각만 바꾸면 된다.
가짜는 '배의 움직임'뿐이다. 명부·좌표·교통·위판 실적은 실데이터.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

from .. import geo
from .clock import KST

SEED = 20261013
KMH_PER_KN = geo.KM_PER_NM
HARBOR_STOP_KM = 0.3  # 위판장 좌표 바로 앞에서 멈춤
START_POSITIONS = Path(__file__).with_name("start_positions.json")


@dataclass(frozen=True)
class KeyShip:
    ship_id: int
    note: str
    bearing: float      # 위판장에서 본 출발점 방위(°)
    dist_km: float      # 출발점 거리
    depart: str         # 출발 시각 HH:MM
    speed_kn: float


# 데모 대본. 03:10 예보에서 연안자망 3척이 '입항 중'이 되어 붉은대게 구독 푸시가 나간다.
KEY_SHIPS: tuple[KeyShip, ...] = (
    KeyShip(3, "연안자망 남진호 4.9t — 03:10 푸시", 92, 12.5, "03:05", 5.0),
    KeyShip(7, "연안자망 강성호 9.8t — 03:10 푸시", 90, 13.5, "03:06", 5.2),
    KeyShip(17, "연안자망 장명호 4.9t — 03:10 푸시", 100, 13.0, "03:08", 4.8),
    KeyShip(1, "근해자망 제33안성호 43t — 질문 '43톤 자망선 언제 와?'", 104, 14.5, "03:20", 5.5),
    KeyShip(2, "근해채낚기 제33성한호 29t — 질문 '오늘 오징어 있어?'", 97, 14.8, "04:00", 5.5),
    KeyShip(22, "연안통발 삼기호 2.0t — 붉은대게 두 번째 알림", 98, 12.0, "04:20", 5.0),
)


@dataclass(frozen=True)
class Track:
    ship_id: int
    start: tuple[float, float]
    depart: datetime | None     # None 이면 창 안에서 입항하지 않는 조업선
    speed_kn: float
    idle_course: float          # 출발 전·조업 중 침로


def _offset(origin: tuple[float, float], bearing: float, dist_km: float) -> tuple[float, float]:
    lat1, lon1 = map(math.radians, origin)
    b, d = math.radians(bearing), dist_km / geo.EARTH_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def _at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), KST)


def load_start_positions(path: Path = START_POSITIONS) -> dict[int, tuple[float, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {p["ship_id"]: (p["lat"], p["lon"]) for p in data["positions"]}


def build_tracks(day: date, place: tuple[float, float], starts: dict[int, tuple[float, float]],
                 seed: int = SEED) -> list[Track]:
    rng = random.Random(seed)
    tracks = []
    key_ids = {k.ship_id for k in KEY_SHIPS}
    for k in KEY_SHIPS:
        tracks.append(Track(k.ship_id, _offset(place, k.bearing, k.dist_km), _at(day, k.depart),
                            k.speed_kn, (k.bearing + 90) % 360))
    for sid in sorted(starts):
        if sid in key_ids:
            continue
        idle_course = rng.uniform(0, 360)
        if rng.random() < 0.4:  # 조업 중 — 창 안에서 들어오지 않음
            tracks.append(Track(sid, starts[sid], None, 0.0, idle_course))
            continue
        minute = rng.randint(30, 150)  # 04:30~06:30 출발
        depart = datetime.combine(day, dtime(4, 0), KST) + timedelta(minutes=minute)
        tracks.append(Track(sid, starts[sid], depart, round(rng.uniform(5.0, 9.0), 1), idle_course))
    return tracks


def position(track: Track, t: datetime, place: tuple[float, float]) -> dict:
    """시각 t의 위치. 출발 전·조업 중에는 0.8kn 표류(입항 판정에 걸리지 않는 속도)."""
    lat0, lon0 = track.start
    if track.depart is None or t < track.depart:
        return {"lat": lat0, "lon": lon0, "course": track.idle_course, "speed": 0.8}
    total = max(geo.haversine_km(lat0, lon0, *place) - HARBOR_STOP_KM, 0.0)
    hours = (t - track.depart).total_seconds() / 3600
    traveled = track.speed_kn * KMH_PER_KN * hours
    frac = 1.0 if total == 0 else min(traveled / total, 1.0)
    course = geo.bearing_deg(lat0, lon0, *place)
    return {
        "lat": lat0 + (place[0] - lat0) * frac * (total / (total + HARBOR_STOP_KM) if total else 1),
        "lon": lon0 + (place[1] - lon0) * frac * (total / (total + HARBOR_STOP_KM) if total else 1),
        "course": round(course, 1),
        "speed": track.speed_kn if frac < 1.0 else 0.0,
    }


class Simulator:
    def __init__(self, place: tuple[float, float], starts: dict[int, tuple[float, float]] | None = None,
                 seed: int = SEED):
        self.place, self.seed = place, seed
        self.starts = starts if starts is not None else load_start_positions()
        self._day: date | None = None
        self._tracks: list[Track] = []

    def tracks(self, day: date) -> list[Track]:
        if day != self._day:
            self._tracks, self._day = build_tracks(day, self.place, self.starts, self.seed), day
        return self._tracks

    def snapshot(self, t: datetime) -> list[dict]:
        ts = t.isoformat(timespec="seconds")
        out = []
        for tr in self.tracks(t.date()):
            p = position(tr, t, self.place)
            out.append({"ship_id": tr.ship_id, "ts": ts, "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                        "course": p["course"], "speed": p["speed"], "rcv_ts": None, "source": "sim"})
        return out
