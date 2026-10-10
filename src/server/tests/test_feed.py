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
    tracks = simulator.tracks(DAY)
    idle = [t.ship_id for t in tracks if t.depart is None]
    assert idle, "조업선이 일부 있어야 판정이 의미 있다"
    for t in ("03:00", "05:00", "06:30"):
        s = by_id(simulator.snapshot(at(t)))
        assert all(s[i]["speed"] < 2 for i in idle)


def test_clock_seek_play_pause():
    c = VirtualClock(mode="sim")
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
    for s in SLOTS[:14]:
        d = geo.haversine_km(*s, *PLACE)
        assert 0.02 < d < 0.35, "첫 줄 정박 자리는 위판장 앞 부두를 따라 350m 안"


def test_ship_enters_through_channel_and_moors_at_berth(simulator):
    from app.feed.harbor import APPROACH
    tr = next(t for t in simulator.tracks(DAY) if t.ship_id == 3)  # 남진호(가장 먼저 도착)
    assert tr.berth is not None
    arrive = sim.arrival_time(tr, PLACE)
    # 도착 전 어느 순간 수로(APPROACH[1]) 근처를 지난다
    passed = min(geo.haversine_km(*APPROACH[1], *(lambda p: (p["lat"], p["lon"]))(sim.position(tr, arrive - timedelta(minutes=m), PLACE)))
                 for m in range(1, 40))
    assert passed < 0.15
    end = sim.position(tr, arrive + timedelta(minutes=5), PLACE)
    assert (round(end["lat"], 6), round(end["lon"], 6)) == (round(tr.berth[0], 6), round(tr.berth[1], 6))
    assert end["speed"] == 0


def test_earliest_arrival_gets_berth_nearest_auction_place(simulator):
    from app.feed.harbor import SLOTS
    tracks = [t for t in simulator.tracks(DAY) if t.depart is not None]
    first = min(tracks, key=lambda t: sim.arrival_time(t, PLACE))
    assert first.berth == SLOTS[0]
