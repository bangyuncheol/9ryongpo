from datetime import date, datetime, timedelta

import pytest

from app import db, geo
from app.collectors.auction import load_dir
from app.config import settings
from app.feed import sim
from app.feed.clock import KST
from app.rules import arrival, species

PLACE = geo.AUCTION_PLACE


def at(hhmm, day=date(2026, 10, 13)):
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), KST)


FLEET = {3: {"name": "남진호", "biz": "연안자망어업", "gt": 4.92},
         7: {"name": "강성호", "biz": "연안자망어업", "gt": 9.77},
         17: {"name": "장명호", "biz": "연안자망어업", "gt": 4.93},
         1: {"name": "제33안성호", "biz": "근해자망어업", "gt": 43.0},
         2: {"name": "제33성한호", "biz": "근해채낚기어업", "gt": 29.0},
         22: {"name": "삼기호", "biz": "연안통발어업", "gt": 1.99}}


@pytest.fixture(scope="module")
def simulator():
    return sim.Simulator(PLACE)


def judge_at(simulator, hhmm):
    t = at(hhmm)
    return arrival.judge(simulator.snapshot(t), simulator.snapshot(t - timedelta(minutes=10)), FLEET, t, PLACE)


def test_0300_nobody_arriving_0310_three_gillnetters(simulator):
    assert {a["ship_id"] for a in judge_at(simulator, "03:00")["arriving"]} & {3, 7, 17} == set()
    got = judge_at(simulator, "03:10")["arriving"]
    ids = {a["ship_id"] for a in got}
    assert {3, 7, 17} <= ids
    for a in got:
        if a["ship_id"] in (3, 7, 17):
            assert a["biz"] == "연안자망어업" and a["confidence"] == "높음"
            assert "04:15" <= a["eta"][11:16] <= "04:45"


def test_43t_eta_and_arrival(simulator):
    a = {x["ship_id"]: x for x in judge_at(simulator, "04:00")["arriving"]}
    assert 1 in a and "04:35" <= a[1]["eta"][11:16] <= "04:55"
    done = {x["ship_id"] for x in judge_at(simulator, "05:00")["arrived"]}
    assert 1 in done


def test_moving_away_is_not_arriving():
    cur = [{"ship_id": 9, "lat": 35.99, "lon": 129.62, "course": 90.0, "speed": 8.0}]   # 동쪽으로 멀어짐
    assert arrival.judge(cur, [], {}, at("04:00"), PLACE)["arriving"] == []


def test_not_closing_is_dropped():
    prev = [{"ship_id": 9, "lat": 35.99, "lon": 129.60, "course": 270.0, "speed": 8.0}]
    cur = [{"ship_id": 9, "lat": 35.99, "lon": 129.61, "course": 270.0, "speed": 8.0}]  # 침로는 맞지만 거리가 늘었다
    assert arrival.judge(cur, prev, {}, at("04:00"), PLACE)["arriving"] == []


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    c = db.connect(tmp_path_factory.mktemp("db") / "t.db")
    db.init_schema(c)
    load_dir(c, settings.auction_dir)  # 저장소의 실제 10월 4개년 + 2026-08
    return c


def test_gillnet_october_is_red_snow_crab(conn):
    d = species.biz_distribution(conn, "연안자망어업", 10)
    assert d["species"][0]["name"] == "붉은대게"
    assert 0.7 < d["species"][0]["share"] < 0.85
    assert d["basis"]["years"] == ["2022", "2023", "2024", "2025"] and not d["category_only"]


def test_jigging_october_is_squid(conn):
    d = species.biz_distribution(conn, "근해채낚기어업", 10)
    assert d["species"][0]["name"] == "살오징어" and d["species"][0]["share"] > 0.9


def test_missing_month_uses_nearest(conn):
    d = species.biz_distribution(conn, "연안자망어업", 11)
    assert d["basis"]["month"] == 10 and d["basis"]["same_month"] is False


def test_estimate_group(conn):
    ships = [{"biz": "연안자망어업", "gt": 5.0}, {"biz": "연안자망어업", "gt": 10.0}, {"biz": "근해채낚기어업", "gt": 29.0}]
    e = species.estimate(conn, ships, 10)
    assert e["ships"] == 3 and e["total_gt"] == 44.0
    assert e["by_biz"][0]["biz"] == "연안자망어업" and e["by_biz"][0]["count"] == 2
    names = [x["name"] for x in e["overall"]]
    assert names[0] == "살오징어" and "붉은대게" in names
