from datetime import date, datetime, timedelta

import pytest

from app import geo
from app.feed import live, sim
from app.feed.clock import KST, VirtualClock

PLACE = geo.AUCTION_PLACE
DAY = date(2026, 10, 13)


def at(hhmm):
    return datetime.combine(DAY, datetime.strptime(hhmm, "%H:%M").time(), KST)


@pytest.fixture(scope="module")
def simulator():
    return sim.Simulator(PLACE)


def by_id(snap):
    return {r["ship_id"]: r for r in snap}


def test_snapshot_is_deterministic(simulator):
    a = sim.Simulator(PLACE).snapshot(at("04:00"))
    b = simulator.snapshot(at("04:00"))
    assert a == b
    assert len(a) == 50  # 실제 마지막 위치 50척(핵심 배 포함)


def test_key_ships_idle_before_depart_and_moving_at_0310(simulator):
    before = by_id(simulator.snapshot(at("03:00")))
    after = by_id(simulator.snapshot(at("03:10")))
    for sid in (3, 7, 17):
        assert before[sid]["speed"] < 2, "출발 전에는 입항 판정 속도 미만"
        assert after[sid]["speed"] >= 4.5
        brg = geo.bearing_deg(after[sid]["lat"], after[sid]["lon"], *PLACE)
        assert geo.angle_diff(after[sid]["course"], brg) < 5, "위판장 쪽으로 향한다"
        assert geo.haversine_km(after[sid]["lat"], after[sid]["lon"], *PLACE) <= 15


def test_key_ship_arrives_and_stops(simulator):
    s = by_id(simulator.snapshot(at("06:00")))
    for sid in (3, 7, 17, 1, 2, 22):
        d = geo.haversine_km(s[sid]["lat"], s[sid]["lon"], *PLACE)
        assert d < 0.6 and s[sid]["speed"] == 0


def test_43t_ship_arrival_time_window(simulator):
    # 제33안성호: 03:20 출발, 14.2km / 5.5kn ≈ 84분 → 04:44 전후
    def dist(t):
        r = by_id(simulator.snapshot(t))[1]
        return geo.haversine_km(r["lat"], r["lon"], *PLACE)
    assert dist(at("04:30")) > 0.6
    assert dist(at("05:00")) < 0.6


def test_fishing_ships_never_qualify_as_arriving(simulator):
    idle = [p.ship_id for p in simulator.plans.values() if p.pattern == "sea"]
    assert idle, "종일 조업하는 배가 일부 있어야 판정이 의미 있다"
    for t in ("03:00", "05:00", "06:30", "15:00"):
        s = by_id(simulator.snapshot(at(t)))
        assert all(s[i]["speed"] < 2 for i in idle)


def test_clock_defaults_to_realtime():
    from app.feed.clock import real_now
    c = VirtualClock(mode="sim")
    assert c.playing and c.speed == 1.0
    assert abs((c.now() - real_now()).total_seconds()) < 2
    c.seek("03:30")
    c.play(speed=60)
    c.realtime()
    assert c.playing and c.speed == 1.0 and abs((c.now() - real_now()).total_seconds()) < 2


def test_clock_seek_play_pause():
    c = VirtualClock(mode="sim")
    c.pause()
    c.seek("03:30")
    assert c.now().strftime("%H:%M") == "03:30" and not c.playing
    c.play(speed=3600)
    assert c.now() >= c.now() - timedelta(seconds=1)
    c.pause()
    frozen = c.now()
    assert c.now() == frozen
    with pytest.raises(ValueError):
        c.seek("3시")
    with pytest.raises(ValueError):
        c.play(speed=0)


def test_live_rows_accept_actual_field_names_and_flag_stale():
    items = [{"devId": 1, "latitude": 35.96, "longitude": 129.67, "course": 180.0, "speed": 9.0,
              "rcvDateTime": "2025-04-27 14:07:38"},
             {"devId": 2, "lati": 35.95, "long": 129.66, "rcvDateTime": "2025-04-27 14:07:38"},
             {"devId": 3, "latitude": None}]
    rows = live.to_rows(items)
    assert [r["ship_id"] for r in rows] == [1, 2]
    f = live.freshness(rows, now=at("04:00"))
    assert f["stale"] is True and f["latest"].startswith("2025-04-27")


def test_berths_are_distinct_and_in_front_of_auction_place():
    from app.feed.harbor import SLOTS
    assert len(set(SLOTS)) == len(SLOTS)
    for s in SLOTS[:11]:
        d = geo.haversine_km(s.lat, s.lon, *PLACE)
        assert d < 0.2, "첫 줄 정박 자리는 위판장 부두·북쪽 해안(200m 안)"
    assert all(not s.via_north for s in SLOTS[:6]), "1순위는 위판장 부두(하역)"


def test_ship_enters_through_channel_and_moors_at_berth(simulator):
    from app.feed.harbor import APPROACH
    plan = simulator.plan(3)  # 남진호(가장 먼저 도착)
    leg = plan.legs[0]
    assert plan.berth is not None and leg.inbound
    # 도착 전 어느 순간 수로(APPROACH[1]) 근처를 지난다
    passed = min(geo.haversine_km(*APPROACH[1], *(lambda p: (p["lat"], p["lon"]))(sim.position(plan, leg.end_s - 60 * m, PLACE)))
                 for m in range(1, 40))
    assert passed < 0.1, "방파제 사이 입구를 지난다"
    end = sim.position(plan, leg.end_s + 300, PLACE)
    assert (round(end["lat"], 6), round(end["lon"], 6)) == (round(plan.berth.lat, 6), round(plan.berth.lon, 6))
    assert end["speed"] == 0 and end["course"] == plan.berth.heading


def test_earliest_arrival_gets_berth_nearest_auction_place(simulator):
    from app.feed.harbor import SLOTS
    first = min((p for p in simulator.plans.values() if p.legs and p.legs[0].inbound), key=lambda p: p.legs[0].end_s)
    assert first.ship_id == 3 and first.berth == SLOTS[0]


def test_remaining_route_lists_unpassed_harbor_corners(simulator):
    """빠른 재생에서 화면이 방파제를 가로지르지 않게, 남은 꺾이는 지점을 준다(10/11)."""
    from app.feed.harbor import APPROACH
    plan = simulator.plan(3)
    leg = plan.legs[0]
    assert sim.remaining_route(plan, leg.depart_s - 60) == []  # 출발 전
    r0 = sim.remaining_route(plan, leg.depart_s + 1)
    assert r0[0] == APPROACH[0] and r0[-1] == (plan.berth.lat, plan.berth.lon)  # 바다 → 입구 → … → 자리
    assert sim.remaining_route(plan, leg.end_s + 60) == []  # 정박 뒤
    mid = sim.remaining_route(plan, leg.end_s - 120)
    assert 0 < len(mid) < len(r0) and mid == r0[len(r0) - len(mid):]  # 남은 경로는 처음 경로의 뒷부분
    out = plan.legs[1]  # 오후 출항: 자리 → 수로 → 입구 → 조업 해역
    r1 = sim.remaining_route(plan, out.depart_s + 1)
    assert not out.inbound and r1[-1] == plan.spot and APPROACH[0] in r1


# --- 24시간 순환 대본(10/15) ---

def hhmm_s(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 3600 + int(m) * 60


def test_day_is_cyclic_no_jump_at_midnight(simulator):
    """모든 다리가 자정 전에 끝나, 23:59 위치와 다음 날 00:00 위치가 같다(날짜가 바뀌어도 배가 튀지 않는다)."""
    for p in simulator.plans.values():
        for a, b in zip(p.legs, p.legs[1:]):
            assert a.end_s <= b.depart_s, (p.ship_id, "다리가 겹친다")
        assert all(lg.end_s < sim.DAY_S for lg in p.legs), (p.ship_id, "자정을 넘긴다")
    late = by_id(simulator.snapshot(at("23:59")))
    early = by_id(simulator.snapshot(datetime.combine(DAY + timedelta(days=1), datetime.min.time(), KST)))
    for sid in late:
        assert (late[sid]["lat"], late[sid]["lon"]) == (early[sid]["lat"], early[sid]["lon"])
        assert late[sid]["speed"] == early[sid]["speed"]


def test_positions_change_once_a_minute(simulator):
    t = at("05:00")
    a = simulator.snapshot(t + timedelta(seconds=10))
    b = simulator.snapshot(t + timedelta(seconds=50))
    c = simulator.snapshot(t + timedelta(seconds=61))
    assert a == b and a[0]["ts"].endswith("05:00:00+09:00")
    assert any(x["lat"] != y["lat"] or x["lon"] != y["lon"] for x, y in zip(a, c)), "1분이 지나면 움직인 배가 있다"


def test_ships_move_in_and_out_all_day(simulator):
    """새벽만이 아니라 낮·저녁에도 들어오고 나가는 배가 있다."""
    def moving(hhmm):
        s = hhmm_s(hhmm)
        return {p.ship_id: lg.inbound for p in simulator.plans.values() if (lg := p.current(s)) is not None}
    assert any(v for v in moving("03:30").values()), "새벽 입항"
    assert any(not v for v in moving("02:30").values()), "새벽 출항"
    assert any(v for v in moving("15:30").values()), "오후 입항"
    assert any(not v for v in moving("16:00").values()), "오후 출항"
    assert any(v for v in moving("20:00").values()), "밤 입항"
    # 대본 배는 오후에 나가서 자정엔 바다(조업 해역)에 있다
    mid = by_id(simulator.snapshot(at("23:59")))
    for sid in (3, 7, 17, 1, 2, 22):
        p = simulator.plan(sid)
        assert geo.haversine_km(mid[sid]["lat"], mid[sid]["lon"], *p.spot) < 0.01 and mid[sid]["speed"] < 2


def test_no_two_ships_share_a_berth_at_the_same_time(simulator):
    for m in range(0, 24 * 60, 10):
        snap = simulator.snapshot(at("00:00") + timedelta(minutes=m))
        docked = [(r["lat"], r["lon"]) for r in snap if r["speed"] == 0]
        assert len(docked) == len(set(docked)), f"{m // 60:02d}:{m % 60:02d} 같은 자리에 두 척"


def test_outbound_ship_is_not_reported_as_arrived(simulator):
    """부두를 떠나 수로를 나가는 배는 '입항'·'입항 중'이 아니다(10/15)."""
    from app.rules import arrival
    plan = simulator.plan(3)
    out = plan.legs[1]
    for m in (1, 5, 10, 20):
        t = at("00:00") + timedelta(seconds=out.depart_s + 60 * m)
        res = arrival.judge(simulator.snapshot(t), simulator.snapshot(t - timedelta(minutes=10)), {}, t, PLACE)
        assert 3 not in {a["ship_id"] for a in res["arriving"] + res["arrived"]}, m
    assert 3 in simulator.routes(at("00:00") + timedelta(seconds=out.depart_s + 120))
    assert 3 not in simulator.inbound(at("00:00") + timedelta(seconds=out.depart_s + 120))
