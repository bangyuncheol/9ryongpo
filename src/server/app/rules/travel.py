"""출발지 → 위판장 소요 시간·출발 권장 시각(10/11, 설계 §4.2). 숫자는 여기서 정하고 LLM은 인용만 한다.

- 도로 구간: 카카오 길찾기. '지금'은 실제 지금 도로 상황, 시각을 정하면(경매 맞춰 도착 포함) 그 시각의 예측 교통.
- 위판장 앞 마지막 구간: E-UM 센서는 위판장 주변(1km 안 4대)만 덮어 경로 전체 가중치로는 근거가 약하다.
  그래서 '지금 출발'일 때만 위판장 앞 실측 혼잡으로 여유를 더하고, 미래 시각은 고정 여유를 둔다
  (교통 예측은 하지 않는다 — CLAUDE.md '의도적으로 하지 않는 것').
- 카카오 길찾기가 실패하면 직선거리 × 도로 계수 ÷ 평균 속도로 '대략'을 낸다.
- '여기서·내 위치에서'(10/13): 웹은 질문과 함께 휴대폰 GPS 좌표(here)를 보내 그 좌표에서 길찾기를 한다.
  전화에는 좌표가 오지 않으므로 출발지를 되묻는다. 좌표는 이 계산에만 쓰고 저장하지 않는다.
- 위판장에서 60km 밖 출발지는 계산하지 않고 '멀어서 안내하기 어렵다'고 답한다(10/13 오너 결정).
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .. import geo
from ..kakao import KakaoClient, KakaoError
from . import visit

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
MAX_KM = 60            # 안내 범위. 이보다 먼 출발지는 계산하지 않는다(같은 이름의 다른 지역도 걸러진다)
ROAD_FACTOR = 1.35     # 직선거리 → 도로 거리(대략 계산용, 제품 가정)
FALLBACK_KMH = 40      # 대략 계산 평균 속도(국도·시내 섞임, 제품 가정)
FUTURE_EXTRA = 3       # 미래 시각: 위판장 앞 진입·주차 여유(분, 제품 가정)
NOW_EXTRA = {"붐빔": 5, "붐비는 편": 4, "비슷": 2, "보통": 2, "한산한 편": 1, "한산": 1}  # 지금 출발: 위판장 앞 실측별 여유(분)
NOW_WORDS = {"지금", "now", "바로", "당장"}
HERE = "내 위치"     # LLM이 '여기서·내 위치에서·지금 있는 곳에서'를 이 값으로 넘긴다
HERE_WORDS = re.compile(r"^(내\s*위치|현재\s*위치|여기|지금\s*있는\s*곳|제\s*위치)$")
TOO_FAR = (f"구룡포 위판장에서 {MAX_KM}km 넘게 떨어진 곳이라 출발 시각을 안내하기 어렵습니다. "
           f"구룡포에서 {MAX_KM}km 안의 출발지로 물어봐 주세요.")
NO_HERE = "지금 계신 곳을 알 수 없습니다. 출발하시는 동네나 큰 건물 이름을 말씀해 주세요."
ADDRESS_LIKE = re.compile(r"(동|읍|면|리|가|로|길)\s*\d*(번지)?$")  # '양덕동', '구룡포읍', '호미로 341'


def pick_place(docs: list[dict], max_km: float = MAX_KM) -> dict | None:
    """정확도 순 결과 중 구룡포에서 max_km 안의 첫 장소."""
    for d in docs:
        try:
            if float(d.get("distance") or 0) / 1000 <= max_km:
                return d
        except (TypeError, ValueError):
            continue
    return None


def fallback_min(km_straight: float) -> int:
    return max(1, math.ceil(km_straight * ROAD_FACTOR / FALLBACK_KMH * 60))


def last_mile(traffic: dict | None, now_query: bool) -> tuple[int, str]:
    """위판장 앞 마지막 구간 여유(분)와 근거."""
    if not now_query:
        return FUTURE_EXTRA, "위판장 앞 진입·주차 여유(미래 시각의 위판장 앞 혼잡은 예측하지 않아 고정값)"
    t = traffic or {}
    lvl = (t.get("vs_yesterday") or {}).get("level")
    if not lvl or lvl == "비교 불가":
        lvl = t.get("vs_day")
    if lvl in NOW_EXTRA:
        return NOW_EXTRA[lvl], f"위판장 앞 E-UM 실측 지금 '{lvl}'"
    return 2, "위판장 앞 실측을 비교할 수 없어 기본 여유"


def next_at(hhmm: str, now: datetime) -> datetime:
    """오늘 그 시각이 10분 넘게 남았으면 오늘, 아니면 내일(길찾기 예측은 미래 시각만 받는다)."""
    h, m = (int(x) for x in hhmm.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t - now > timedelta(minutes=10) else t + timedelta(days=1)


def floor5(t: datetime) -> datetime:
    return t - timedelta(minutes=t.minute % 5)


def _hhmm(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


async def _here_place(kakao: KakaoClient, here: tuple[float, float], dest: tuple[float, float]) -> dict:
    """GPS 좌표를 장소 결과 꼴로. 동네 이름은 좌표→행정구역으로 붙이고, 실패하면 이름 없이 간다."""
    name = None
    try:
        name = await kakao.region(here)
    except KakaoError as e:
        log.warning("내 위치 동네 이름 조회 실패: %s", e)
    d = round(geo.haversine_km(dest[1], dest[0], here[1], here[0]) * 1000)
    return {"place_name": f"지금 계신 곳({name} 근처)" if name else "지금 계신 곳", "address_name": name,
            "x": str(here[0]), "y": str(here[1]), "distance": str(d)}


async def estimate(kakao: KakaoClient | None, dest: tuple[float, float], origin: str, traffic: dict | None,
                   auction_time: str = visit.AUCTION_DEFAULT, depart_time: str | None = None,
                   now: datetime | None = None, here: tuple[float, float] | None = None) -> dict:
    """dest=(lon, lat) 위판장. depart_time: None=경매에 맞춰 출발 시각 계산, '지금', 'HH:MM'=그 시각 출발.
    origin 이 '내 위치'면 here=(lon, lat)(웹 GPS)를 출발지로 쓴다. here 가 없으면(전화 등) 출발지를 되묻는다."""
    if not kakao or not kakao.enabled:
        return {"error": "길찾기 설정이 없어 걸리는 시간을 계산할 수 없습니다."}
    origin = (origin or "").strip()
    if not origin:
        return {"error": "어디서 출발하는지 알려 주셔야 계산할 수 있습니다."}
    mine = bool(HERE_WORDS.match(origin))
    if mine and here is None:
        return {"error": NO_HERE}
    if mine and geo.haversine_km(dest[1], dest[0], here[1], here[0]) > MAX_KM:
        return {"error": TOO_FAR}
    now = now or datetime.now(KST)
    try:
        if mine:
            place = await _here_place(kakao, here, dest)
        else:
            place, far = await _find(kakao, dest, origin)
            if not place and far:
                return {"error": TOO_FAR}
    except KakaoError:
        return {"error": "지금 장소를 찾을 수 없습니다. 잠시 후 다시 물어봐 주세요."}
    if not place:
        return {"error": f"'{origin}'을(를) 구룡포 근처에서 찾지 못했습니다. 동네나 큰 건물 이름으로 다시 말씀해 주세요."}
    return await _route(kakao, dest, place, traffic, auction_time, depart_time, now)


async def _find(kakao: KakaoClient, dest: tuple[float, float], origin: str) -> tuple[dict | None, bool]:
    """이름 → 장소. 60km 안 결과가 없고 먼 결과만 있으면 far=True."""
    docs: list[dict] = []
    place = None
    if ADDRESS_LIKE.search(origin):  # 주소 꼴이면 주소 검색 먼저(거리는 직접 재서 같은 기준으로 고른다)
        docs = await kakao.address(origin)
        for d in docs:
            d["distance"] = str(round(geo.haversine_km(dest[1], dest[0], float(d["y"]), float(d["x"])) * 1000))
            d.setdefault("place_name", d.get("address_name"))
        place = pick_place(docs)
    if not place:
        found = await kakao.search(origin, dest)
        place = pick_place(found)
        docs = docs + found
    return place, bool(docs) and not place


async def _route(kakao: KakaoClient, dest: tuple[float, float], place: dict, traffic: dict | None,
                 auction_time: str, depart_time: str | None, now: datetime) -> dict:
    o = (float(place["x"]), float(place["y"]))
    out: dict = {"origin": place.get("place_name"), "origin_address": place.get("road_address_name") or place.get("address_name"),
                 "destination": "구룡포수협 위판장"}

    at = _hhmm(depart_time)
    mode = "now" if (depart_time or "").strip() in NOW_WORDS else ("at" if at else "auction")
    auction = _hhmm(auction_time) or visit.AUCTION_DEFAULT
    arrive_by = (datetime.strptime(auction, "%H:%M") - timedelta(minutes=visit.EARLY_MIN)).strftime("%H:%M")
    if mode == "now":
        query = None
    elif mode == "at":
        query = next_at(at, now)
    else:  # 도착 권장 시각보다 1시간 앞 출발로 한 번 물어 소요 시간을 얻는다
        query = next_at(arrive_by, now) - timedelta(minutes=60)
        if query - now <= timedelta(minutes=10):
            query = None  # 이미 그 시각에 가깝다 → 실제 지금 도로 상황
    extra, reason = last_mile(traffic, now_query=query is None)

    try:
        r = await kakao.route(o, dest, query)
        km, drive, approx = r["distance_m"] / 1000, max(1, math.ceil(r["duration_s"] / 60)), False
        basis = "카카오 길찾기 " + ("실제 지금 도로 상황" if query is None else f"{query:%H:%M} 출발 예측 교통")
    except KakaoError:
        sk = geo.haversine_km(o[1], o[0], dest[1], dest[0])
        km, drive, approx = sk * ROAD_FACTOR, fallback_min(sk), True
        basis = "길찾기를 불러오지 못해 직선거리로 낸 대략 값"
    total = drive + extra
    out |= {"distance_km": round(km, 1), "drive_min": drive, "last_mile_min": extra, "last_mile_reason": reason,
            "total_min": total, "approx": approx, "basis": f"{basis} + 위판장 앞 여유 {extra}분"}
    if mode == "now":
        out["note"] = "지금 바로 출발할 때 걸리는 시간이다. 시각은 말하지 말고 걸리는 분만 말한다."
    elif mode == "at":
        out |= {"depart_at": at, "arrive_at": (query + timedelta(minutes=total)).strftime("%H:%M")}
    else:
        dep = floor5(datetime.strptime(arrive_by, "%H:%M") - timedelta(minutes=total))
        out |= {"auction_time": auction, "arrive_by": arrive_by, "depart_by": dep.strftime("%H:%M"),
                "early_min": visit.EARLY_MIN,
                # (당시 경매 09:00) 9시 경매인데 왜 8시 20분이냐는 질문이 나왔다(10/11 실통화) → 30분 일찍 도착하는 이유를 답에 꼭 넣게 한다
                "note": f"출발 시각을 말할 때 반드시 '경매 {auction}보다 {visit.EARLY_MIN}분 이른 {arrive_by}까지 도착하려면'을 함께 말한다. "
                        f"{arrive_by} 도착 기준 {dep:%H:%M}까지 출발(5분 단위로 당김)."}
    return out
