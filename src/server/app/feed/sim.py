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
from dataclasses import dataclass, replace
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

from .. import geo
from .clock import KST
from .harbor import APPROACH, BASIN_NORTH, HARBOR_KN, SLOTS, Berth

SEED = 20261013
KMH_PER_KN = geo.KM_PER_NM
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
    berth: Berth | None = None  # 위판장 앞 정박 자리(harbor.SLOTS)


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


def _seg_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return geo.haversine_km(a[0], a[1], b[0], b[1])


def path_of(track: Track, place: tuple[float, float]) -> list[tuple[tuple[float, float], float]]:
    """(지점, 그 지점까지 가는 속도 kn) 목록. 바다 구간은 배 속도, 수로부터는 HARBOR_KN.
    APPROACH 경로는 위판장 기준으로 그려져 있어, 다른 위판장 좌표가 들어오면(테스트 등) 직선으로 간다."""
    end = (track.berth.lat, track.berth.lon) if track.berth else place
    if geo.haversine_km(*place, *geo.AUCTION_PLACE) > 0.5:
        return [(end, track.speed_kn)]
    pts = [(APPROACH[0], track.speed_kn)] + [(p, HARBOR_KN) for p in APPROACH[1:]]
    if track.berth and track.berth.via_north:
        pts.append((BASIN_NORTH, HARBOR_KN))
    return pts + [(end, HARBOR_KN)]


def arrival_time(track: Track, place: tuple[float, float]) -> datetime | None:
    if track.depart is None:
        return None
    hours, cur = 0.0, track.start
    for pt, kn in path_of(track, place):
        hours += _seg_km(cur, pt) / (kn * KMH_PER_KN)
        cur = pt
    return track.depart + timedelta(hours=hours)


def position(track: Track, t: datetime, place: tuple[float, float]) -> dict:
    """시각 t의 위치. 출발 전·조업 중에는 0.8kn 표류(입항 판정에 걸리지 않는 속도).
    출발 뒤에는 바다 → 항구 입구 → 수로 → 정박 자리 순으로 꺾은선을 따라간다(10/10)."""
    lat0, lon0 = track.start
    if track.depart is None or t < track.depart:
        return {"lat": lat0, "lon": lon0, "course": track.idle_course, "speed": 0.8}
    left_h = (t - track.depart).total_seconds() / 3600
    cur, course = track.start, track.idle_course
    for pt, kn in path_of(track, place):
        seg = _seg_km(cur, pt)
        need_h = seg / (kn * KMH_PER_KN) if seg else 0.0
        if left_h < need_h:
            f = left_h / need_h
            return {"lat": cur[0] + (pt[0] - cur[0]) * f, "lon": cur[1] + (pt[1] - cur[1]) * f,
                    "course": round(geo.bearing_deg(*cur, *pt), 1), "speed": kn}
        left_h -= need_h
        if seg:
            course = round(geo.bearing_deg(*cur, *pt), 1)
        cur = pt
    if track.berth:  # 정박: 자리마다 정한 방향(부두와 나란히 / 뱃머리를 해안에)
        course = track.berth.heading
    return {"lat": cur[0], "lon": cur[1], "course": course, "speed": 0.0}


def remaining_route(track: Track, t: datetime, place: tuple[float, float]) -> list[tuple[float, float]]:
    """시각 t에 아직 지나지 않은 꺾이는 지점(정박 자리까지). 움직이지 않으면 빈 목록.
    화면은 2초마다 위치를 받아 사이를 잇는데, 빠른 재생에선 그 사이에 방파제 모서리를 지나 직선으로 그리면
    육지·방파제를 가로지른다(10/11). 이 목록으로 화면이 모서리를 거쳐 움직인다."""
    if track.depart is None or t < track.depart:
        return []
    left_h = (t - track.depart).total_seconds() / 3600
    cur = track.start
    pts = path_of(track, place)
    for i, (pt, kn) in enumerate(pts):
        seg = _seg_km(cur, pt)
        need_h = seg / (kn * KMH_PER_KN) if seg else 0.0
        if left_h < need_h:
            return [p for p, _ in pts[i:]]
        left_h -= need_h
        cur = pt
    return []


class Simulator:
    def __init__(self, place: tuple[float, float], starts: dict[int, tuple[float, float]] | None = None,
                 seed: int = SEED):
        self.place, self.seed = place, seed
        self.starts = starts if starts is not None else load_start_positions()
        self._day: date | None = None
        self._tracks: list[Track] = []

    def tracks(self, day: date) -> list[Track]:
        if day != self._day:
            raw = build_tracks(day, self.place, self.starts, self.seed)
            # 정박 자리: 먼저 도착하는 배가 위판장에 가까운 자리(SLOTS[0])부터 차지
            order = sorted((tr for tr in raw if tr.depart is not None), key=lambda tr: arrival_time(tr, self.place))
            berth = {tr.ship_id: SLOTS[i % len(SLOTS)] for i, tr in enumerate(order)}
            self._tracks = [replace(tr, berth=berth.get(tr.ship_id)) for tr in raw]
            self._day = day
        return self._tracks

    def routes(self, t: datetime) -> dict[int, list[list[float]]]:
        """움직이는 배의 남은 꺾이는 지점(위도, 경도). 화면 보간용."""
        out = {}
        for tr in self.tracks(t.date()):
            r = remaining_route(tr, t, self.place)
            if r:
                out[tr.ship_id] = [[round(a, 6), round(b, 6)] for a, b in r]
        return out

    def snapshot(self, t: datetime) -> list[dict]:
        ts = t.isoformat(timespec="seconds")
        out = []
        for tr in self.tracks(t.date()):
            p = position(tr, t, self.place)
            out.append({"ship_id": tr.ship_id, "ts": ts, "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                        "course": p["course"], "speed": p["speed"], "rcv_ts": None, "source": "sim"})
        return out
