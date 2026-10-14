"""선박 위치 시뮬레이터(설계 §5.5, §1-13, §1-25).

E-UM 선박 위치가 2025-04-27에 멈춰 있어, 같은 스키마로 배의 하루(24시간) 움직임을 만든다(10/15 개편).
- 하루 대본은 24시간 주기로 똑같이 반복된다. 모든 다리(leg)가 자정 전에 끝나 배마다 00:00 상태(정박 또는 조업 해역)로
  돌아온 뒤 날이 바뀌므로, 날짜가 넘어가도 위치가 튀지 않는다.
- 위치는 1분 단위로만 바뀐다(실제 위치 수신 주기를 흉내). 시각의 순수 함수라 되감기·배속은 시각만 바꾸면 된다.
- 데모 핵심 배는 대본(KEY_SHIPS)으로 새벽 입항·오후 출항을 고정한다(03:10 예보에서 연안자망 3척 → 붉은대게 푸시).
- 나머지 배는 실제 마지막 위치(start_positions.json)를 조업 해역으로 삼고, 시드 고정 난수로 하루 패턴을 고른다:
  night(새벽 입항·오후 출항) · dawn(새벽 출항·낮 입항) · day(아침 출항·오후 입항) · late(낮 출항·밤 입항) · sea(종일 조업) · moored(종일 정박).
  그래서 새벽만이 아니라 낮·저녁에도 들어오고 나가는 배가 있다.
가짜는 '배의 움직임'뿐이다. 명부·좌표·교통·위판 실적은 실데이터.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import geo
from .clock import KST
from .harbor import APPROACH, BASIN_NORTH, HARBOR_KN, SLOTS, Berth

SEED = 20261013
KMH_PER_KN = geo.KM_PER_NM
START_POSITIONS = Path(__file__).with_name("start_positions.json")
DAY_S = 24 * 3600
DRIFT_KN = 0.8  # 조업 중 표류 속도(입항 판정 2kn 미만)

Pt = tuple[float, float]


@dataclass(frozen=True)
class KeyShip:
    ship_id: int
    note: str
    bearing: float      # 위판장에서 본 조업 해역 방위(°)
    dist_km: float      # 조업 해역 거리
    depart: str         # 입항 출발 시각 HH:MM
    speed_kn: float
    leave: str          # 오후 출항 시각 HH:MM (조업 해역으로 돌아가 자정엔 바다에 있다)


# 데모 대본. 03:10 예보에서 연안자망 3척이 '입항 중'이 되어 붉은대게 구독 푸시가 나간다.
KEY_SHIPS: tuple[KeyShip, ...] = (
    KeyShip(3, "연안자망 남진호 4.9t — 03:10 푸시", 92, 12.5, "03:05", 5.0, "14:30"),
    KeyShip(7, "연안자망 강성호 9.8t — 03:10 푸시", 90, 13.5, "03:06", 5.2, "15:10"),
    KeyShip(17, "연안자망 장명호 4.9t — 03:10 푸시", 100, 13.0, "03:08", 4.8, "15:40"),
    KeyShip(1, "근해자망 제33안성호 43t — 질문 '43톤 자망선 언제 와?'", 104, 14.5, "03:20", 5.5, "16:20"),
    KeyShip(2, "근해채낚기 제33성한호 29t — 질문 '오늘 오징어 있어?'", 97, 14.8, "04:00", 5.5, "17:00"),
    KeyShip(22, "연안통발 삼기호 2.0t — 붉은대게 두 번째 알림", 98, 12.0, "04:20", 5.0, "14:00"),
)

# 배경 배의 하루 패턴: (다리 종류, 출발 시각 범위 초). 창은 다리가 자정 전에 끝나고 서로 겹치지 않게 잡았다
# (바다 6~15km를 5~9kn로 1~1.7시간 + 항구 안 3kn 약 15분).
PATTERNS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "night": (("in", 4 * 3600 + 1800, 6 * 3600 + 1800), ("out", 12 * 3600 + 1800, 18 * 3600)),  # 밤새 조업 → 새벽 입항 → 오후 출항
    "dawn": (("out", 1 * 3600 + 1800, 4 * 3600), ("in", 11 * 3600, 16 * 3600)),                 # 새벽 출항 → 낮 입항
    "day": (("out", 8 * 3600, 10 * 3600 + 1800), ("in", 14 * 3600 + 1800, 17 * 3600 + 1800)),   # 아침 출항 → 오후 입항
    "late": (("out", 9 * 3600 + 1800, 12 * 3600), ("in", 18 * 3600 + 1800, 21 * 3600 + 1800)),  # 낮 출항 → 밤 입항
    "sea": (),                                                                                    # 종일 조업
    "moored": (),                                                                                 # 종일 정박(정비·휴어)
}
PATTERN_WEIGHTS = {"night": 30, "dawn": 20, "day": 15, "late": 15, "sea": 12, "moored": 8}


@dataclass(frozen=True)
class Leg:
    depart_s: int               # 출발(하루 안 초)
    inbound: bool               # True 조업 해역 → 정박 자리, False 정박 자리 → 조업 해역
    start: Pt
    pts: tuple[tuple[Pt, float], ...]  # (지점, 그 지점까지 가는 속도 kn)
    end_s: float                # 도착(하루 안 초). 항상 DAY_S 미만


@dataclass(frozen=True)
class Plan:
    ship_id: int
    pattern: str
    spot: Pt                    # 조업 해역(바다)
    speed_kn: float
    idle_course: float          # 조업 중 침로
    berth: Berth | None         # 정박 자리. 종일 조업(sea)은 None
    legs: tuple[Leg, ...]       # 시각순, 서로 겹치지 않음, in/out 번갈아

    def current(self, s: float) -> Leg | None:
        """시각 s(하루 안 초)에 진행 중인 다리. 없으면 None(쉬는 중)."""
        for leg in self.legs:
            if leg.depart_s <= s < leg.end_s:
                return leg
        return None

    def resting_inbound(self, s: float) -> bool:
        """쉬는 중일 때 정박(True)인지 조업 해역(False)인지. 하루가 순환하므로 마지막 다리의 끝 상태가 00:00 상태다."""
        last = None
        for leg in self.legs:
            if leg.end_s <= s:
                last = leg
        if last is None:
            last = self.legs[-1] if self.legs else None
        if last is None:
            return self.pattern == "moored"
        return last.inbound


def _offset(origin: Pt, bearing: float, dist_km: float) -> Pt:
    lat1, lon1 = map(math.radians, origin)
    b, d = math.radians(bearing), dist_km / geo.EARTH_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def _sec(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 3600 + int(m) * 60


def sec_of_day(t: datetime) -> int:
    """KST 하루 안 초. 위치는 1분 단위로만 바뀐다(초는 버린다)."""
    t = t.astimezone(KST)
    return t.hour * 3600 + t.minute * 60


def floor_minute(t: datetime) -> datetime:
    return t.astimezone(KST).replace(second=0, microsecond=0)


def at_sec(day: date, s: float) -> datetime:
    return datetime.combine(day, datetime.min.time(), KST) + timedelta(seconds=s)


def load_start_positions(path: Path = START_POSITIONS) -> dict[int, Pt]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(p["ship_id"]): (float(p["lat"]), float(p["lon"])) for p in raw["positions"]}


def _seg_km(a: Pt, b: Pt) -> float:
    return geo.haversine_km(a[0], a[1], b[0], b[1])


def _use_harbor_path(place: Pt) -> bool:
    """APPROACH 경로는 구룡포 위판장 기준으로 그려져 있어, 다른 위판장 좌표가 들어오면(테스트 등) 직선으로 간다."""
    return geo.haversine_km(*place, *geo.AUCTION_PLACE) <= 0.5


def inbound_pts(berth: Berth | None, place: Pt, speed_kn: float) -> tuple[tuple[Pt, float], ...]:
    """바다 → 입구 → 수로 → 정박 자리. 바다 구간은 배 속도, 수로부터는 HARBOR_KN."""
    end = (berth.lat, berth.lon) if berth else place
    if not _use_harbor_path(place):
        return ((end, speed_kn),)
    pts = [(APPROACH[0], speed_kn)] + [(p, HARBOR_KN) for p in APPROACH[1:]]
    if berth and berth.via_north:
        pts.append((BASIN_NORTH, HARBOR_KN))
    return tuple(pts + [(end, HARBOR_KN)])


def outbound_pts(berth: Berth | None, place: Pt, spot: Pt, speed_kn: float) -> tuple[tuple[Pt, float], ...]:
    """정박 자리 → 수로 → 입구 → 바다(조업 해역). 입항 경로를 거꾸로 간다."""
    if not _use_harbor_path(place):
        return ((spot, speed_kn),)
    pts: list[tuple[Pt, float]] = []
    if berth and berth.via_north:
        pts.append((BASIN_NORTH, HARBOR_KN))
    pts += [(p, HARBOR_KN) for p in reversed(APPROACH)]
    return tuple(pts + [(spot, speed_kn)])


def _travel_h(start: Pt, pts: tuple[tuple[Pt, float], ...]) -> float:
    hours, cur = 0.0, start
    for pt, kn in pts:
        hours += _seg_km(cur, pt) / (kn * KMH_PER_KN)
        cur = pt
    return hours


def make_leg(depart_s: int, inbound: bool, start: Pt, pts: tuple[tuple[Pt, float], ...]) -> Leg:
    return Leg(depart_s, inbound, start, pts, depart_s + _travel_h(start, pts) * 3600)


def position(plan: Plan, s: float, place: Pt) -> dict:
    """시각 s(하루 안 초)의 위치. 조업 중에는 0.8kn 표류, 정박 중에는 0kn(자리마다 정한 방향),
    다리 진행 중에는 꺾은선을 따라간다(바다 → 항구 입구 → 수로 → 정박 자리, 또는 그 반대)."""
    leg = plan.current(s)
    if leg is None:
        if plan.resting_inbound(s) and plan.berth:
            return {"lat": plan.berth.lat, "lon": plan.berth.lon, "course": plan.berth.heading, "speed": 0.0}
        return {"lat": plan.spot[0], "lon": plan.spot[1], "course": plan.idle_course, "speed": DRIFT_KN}
    left_h = (s - leg.depart_s) / 3600
    cur, course = leg.start, plan.idle_course
    for pt, kn in leg.pts:
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
    if leg.inbound and plan.berth:
        course = plan.berth.heading
    return {"lat": cur[0], "lon": cur[1], "course": course, "speed": 0.0}


def remaining_route(plan: Plan, s: float) -> list[Pt]:
    """시각 s에 진행 중인 다리에서 아직 지나지 않은 꺾이는 지점. 움직이지 않으면 빈 목록.
    화면은 1초마다 위치를 받아 사이를 잇는데, 빠른 재생에선 그 사이에 방파제 모서리를 지나 직선으로 그리면
    육지·방파제를 가로지른다(10/11). 이 목록으로 화면이 모서리를 거쳐 움직인다."""
    leg = plan.current(s)
    if leg is None:
        return []
    left_h = (s - leg.depart_s) / 3600
    cur = leg.start
    for i, (pt, kn) in enumerate(leg.pts):
        seg = _seg_km(cur, pt)
        need_h = seg / (kn * KMH_PER_KN) if seg else 0.0
        if left_h < need_h:
            return [p for p, _ in leg.pts[i:]]
        left_h -= need_h
        cur = pt
    return []


# --- 하루 대본 만들기 ---

@dataclass
class _Draft:
    ship_id: int
    pattern: str
    spot: Pt
    speed_kn: float
    idle_course: float
    specs: tuple[tuple[str, int], ...]   # (in|out, 출발 초)


def _drafts(place: Pt, starts: dict[int, Pt], seed: int) -> list[_Draft]:
    rng = random.Random(seed)
    out = []
    key_ids = {k.ship_id for k in KEY_SHIPS}
    for k in KEY_SHIPS:
        out.append(_Draft(k.ship_id, "key", _offset(place, k.bearing, k.dist_km), k.speed_kn, (k.bearing + 90) % 360,
                          (("in", _sec(k.depart)), ("out", _sec(k.leave)))))
    names, weights = zip(*PATTERN_WEIGHTS.items())
    for sid in sorted(starts):
        if sid in key_ids:
            continue
        idle_course = rng.uniform(0, 360)
        pattern = rng.choices(names, weights)[0]
        speed = round(rng.uniform(5.0, 9.0), 1)
        specs = tuple((kind, rng.randint(lo // 60, hi // 60) * 60) for kind, lo, hi in PATTERNS[pattern])
        out.append(_Draft(sid, pattern, starts[sid], speed, idle_course, specs))
    return out


def _docked_intervals(d: _Draft, place: Pt) -> list[tuple[float, float]]:
    """정박해 있는 구간들 [시작, 끝] (끝이 DAY_S를 넘으면 자정을 넘겨 다음 날까지). 도착은 위판장 기준 근사."""
    if d.pattern == "moored":
        return [(0.0, float(DAY_S))]
    out = []
    n = len(d.specs)
    for i, (kind, dep) in enumerate(d.specs):
        if kind != "in":
            continue
        arrive = dep + _travel_h(d.spot, inbound_pts(None, place, d.speed_kn)) * 3600
        nxt = d.specs[(i + 1) % n][1]
        if nxt <= arrive:
            nxt += DAY_S
        out.append((arrive, float(nxt)))
    return out


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    def segs(x: tuple[float, float]) -> list[tuple[float, float]]:
        lo, hi = x
        return [(lo, min(hi, DAY_S))] + ([(0.0, hi - DAY_S)] if hi > DAY_S else [])
    return any(p[0] < q[1] and q[0] < p[1] for p in segs(a) for q in segs(b))


def _assign_berths(drafts: list[_Draft], place: Pt) -> dict[int, Berth]:
    """정박 자리: 먼저 도착하는 배가 위판장에 가까운 자리(SLOTS[0])부터. 같은 시간에 정박해 있는 배끼리만 자리가 달라야 하므로
    하루 동안 자리를 돌려 쓴다. 종일 정박하는 배는 맨 뒤에 남는 자리(북쪽 해안·바깥 겹)로 보낸다."""
    busy: list[list[tuple[float, float]]] = [[] for _ in SLOTS]
    out: dict[int, Berth] = {}
    items = [(d, _docked_intervals(d, place)) for d in drafts if d.pattern != "sea"]
    items.sort(key=lambda x: (x[0].pattern == "moored", x[1][0][0] if x[1] else 0.0))
    for n, (d, ivs) in enumerate(items):
        pick = next((i for i in range(len(SLOTS)) if not any(_overlaps(iv, b) for iv in ivs for b in busy[i])), None)
        if pick is None:  # 자리가 모자라면(설계상 생기지 않음) 바깥 겹에 겹쳐 세운다
            pick = n % len(SLOTS)
        busy[pick].extend(ivs)
        out[d.ship_id] = SLOTS[pick]
    return out


def build_plans(place: Pt, starts: dict[int, Pt], seed: int = SEED) -> dict[int, Plan]:
    drafts = _drafts(place, starts, seed)
    berths = _assign_berths(drafts, place)
    plans = {}
    for d in drafts:
        berth = berths.get(d.ship_id)
        dock = (berth.lat, berth.lon) if berth else place
        legs = []
        for kind, dep in d.specs:
            if kind == "in":
                legs.append(make_leg(dep, True, d.spot, inbound_pts(berth, place, d.speed_kn)))
            else:
                legs.append(make_leg(dep, False, dock, outbound_pts(berth, place, d.spot, d.speed_kn)))
        legs.sort(key=lambda lg: lg.depart_s)
        plans[d.ship_id] = Plan(d.ship_id, d.pattern, d.spot, d.speed_kn, d.idle_course, berth, tuple(legs))
    return plans


class Simulator:
    def __init__(self, place: Pt, starts: dict[int, Pt] | None = None, seed: int = SEED):
        self.place, self.seed = place, seed
        self.starts = starts if starts is not None else load_start_positions()
        self.plans: dict[int, Plan] = build_plans(place, self.starts, seed)

    def plan(self, ship_id: int) -> Plan:
        return self.plans[ship_id]

    def routes(self, t: datetime) -> dict[int, list[list[float]]]:
        """움직이는 배(입항·출항 모두)의 남은 꺾이는 지점(위도, 경도). 화면 보간용."""
        s = sec_of_day(t)
        out = {}
        for sid, plan in self.plans.items():
            r = remaining_route(plan, s)
            if r:
                out[sid] = [[round(a, 6), round(b, 6)] for a, b in r]
        return out

    def inbound(self, t: datetime) -> set[int]:
        """지금 정박 자리로 들어가는 중인 배."""
        s = sec_of_day(t)
        return {sid for sid, plan in self.plans.items() if (leg := plan.current(s)) is not None and leg.inbound}

    def snapshot(self, t: datetime) -> list[dict]:
        """시각 t의 위치(1분 단위). ships_pos 스키마."""
        tm = floor_minute(t)
        s, ts = sec_of_day(tm), tm.isoformat(timespec="seconds")
        out = []
        for sid, plan in self.plans.items():
            p = position(plan, s, self.place)
            out.append({"ship_id": sid, "ts": ts, "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                        "course": p["course"], "speed": p["speed"], "rcv_ts": None, "source": "sim"})
        return out
