"""출발지 → 위판장 소요 시간·출발 권장 시각(rules/travel). 카카오 응답은 tests/fixtures 의 실제 응답 일부로."""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.kakao import KakaoError
from app.rules import travel

FIX = Path(__file__).parent / "fixtures"
DEST = (129.5560, 35.9886)  # 위판장(lon, lat)
NOW = datetime(2026, 10, 11, 17, 0, tzinfo=travel.KST)  # 실제 시각(오후) → 경매 도착 권장 시각은 내일 아침


class FakeKakao:
    """search·route 를 고정 응답으로. route_fail 이면 길찾기 실패를 흉내 낸다."""

    def __init__(self, docs=None, route_fail=False):
        self.docs = json.loads((FIX / "kakao_search.json").read_text(encoding="utf-8"))["documents"] if docs is None else docs
        self.route_fail = route_fail
        self.departs = []
        self.enabled = True

    async def search(self, query, near):
        return self.docs

    async def address(self, query):
        self.address_used = True
        return json.loads((FIX / "kakao_address.json").read_text(encoding="utf-8"))["documents"]

    async def route(self, origin, dest, depart=None):
        self.departs.append(depart)
        if self.route_fail:
            raise KakaoError("timeout", "길찾기")
        s = json.loads((FIX / "kakao_route.json").read_text(encoding="utf-8"))["routes"][0]["summary"]
        return {"distance_m": s["distance"], "duration_s": s["duration"]}


def run(**kw):
    return asyncio.run(travel.estimate(kw.pop("kakao"), DEST, kw.pop("origin", "포항과학기술고등학교"), kw.pop("traffic", None), now=NOW, **kw))


def test_auction_mode_gives_depart_by_from_future_route():
    k = FakeKakao()
    r = run(kakao=k)
    # 실제 응답: 1,481m · 230초 → 4분, 미래 시각 여유 3분 → 7분. 08:30 도착이면 08:23 → 5분 단위로 당겨 08:20
    assert r["origin"] == "포항과학기술고등학교" and r["distance_km"] == 1.5
    assert (r["drive_min"], r["last_mile_min"], r["total_min"]) == (4, travel.FUTURE_EXTRA, 7)
    assert (r["arrive_by"], r["depart_by"]) == ("08:30", "08:20") and not r["approx"]
    assert "30분 이른 08:30까지 도착하려면" in r["note"]  # 9시 경매인데 왜 8시 20분인지 답에 넣게(10/11 실통화)
    assert k.departs[0] == datetime(2026, 10, 12, 7, 30, tzinfo=travel.KST)  # 내일 08:30 도착보다 1시간 앞 출발 예측으로 물음


def test_now_mode_uses_realtime_and_eum_level():
    k = FakeKakao()
    r = run(kakao=k, depart_time="지금", traffic={"vs_yesterday": {"level": "붐빔"}})
    assert k.departs == [None]  # 실제 지금 도로 상황
    assert r["last_mile_min"] == travel.NOW_EXTRA["붐빔"] and r["total_min"] == 4 + travel.NOW_EXTRA["붐빔"]
    assert "depart_by" not in r


def test_at_mode_gives_arrival_time():
    r = run(kakao=FakeKakao(), depart_time="08:00")
    assert (r["depart_at"], r["arrive_at"]) == ("08:00", "08:07")


def test_route_failure_falls_back_to_rough_estimate():
    r = run(kakao=FakeKakao(route_fail=True))
    assert r["approx"] and r["drive_min"] >= 1 and "대략" in r["basis"]


def test_far_or_missing_place_is_an_error():
    far = [{"place_name": "다른 지역 같은 이름", "x": "127.0", "y": "37.5", "distance": "300000"}]
    assert "찾지 못했습니다" in run(kakao=FakeKakao(docs=far))["error"]
    assert "찾지 못했습니다" in run(kakao=FakeKakao(docs=[]))["error"]


def test_no_key_is_an_error():
    k = FakeKakao()
    k.enabled = False
    assert "설정" in run(kakao=k)["error"]


def test_next_at_rolls_to_tomorrow_when_passed():
    assert travel.next_at("08:30", NOW).day == 12
    assert travel.next_at("18:00", NOW).day == 11


def test_district_name_uses_address_search_and_skips_far_same_name():
    # 실제 응답: '양덕동' 주소 검색은 포항 북구 양덕동과 창원 양덕동이 함께 온다. 장소 이름 검색은 동 안의 아무 시설을 잡았다(10/11)
    k = FakeKakao()
    r = run(kakao=k, origin="양덕동")
    assert getattr(k, "address_used", False) and r["origin"] == "경북 포항시 북구 양덕동"
