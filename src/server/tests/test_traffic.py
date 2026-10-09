import json
from pathlib import Path

from app import geo
from app.collectors.traffic import compare_level, day_position, parse_sensors, summarize

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_sensor3_is_closest_to_auction_place():
    sensors = parse_sensors(load("eum_sensors.json"), geo.AUCTION_PLACE)
    assert sensors[0]["name"] == "교통센서3"
    assert sensors[0]["dist_m"] < 150


def test_summarize_sensor3():
    s = summarize(load("eum_traffic_per_hour.json"), load("eum_congestion.json"), "교통센서3")
    assert s["hours"], "센서3 시간대 데이터가 있어야 한다"
    assert s["hours"] == sorted(s["hours"], key=lambda x: x["hour"])
    last = s["last_hour"]
    assert last["total"] >= last["truck"] >= 0
    assert len(s["congestion"]) == len(load("eum_congestion.json"))
    assert s["vs_yesterday"]["level"] in {"붐빔", "비슷", "한산", "비교 불가"}


def test_summarize_unknown_sensor_is_empty():
    s = summarize({}, [], "없는센서")
    assert s["hours"] == [] and s["last_hour"] is None
    assert s["vs_yesterday"]["level"] == "비교 불가"


def test_compare_level():
    assert compare_level(150, 100) == "붐빔"
    assert compare_level(70, 100) == "한산"
    assert compare_level(105, 100) == "비슷"
    assert compare_level(3, 1) == "비슷"   # 아주 작은 값은 같다고 본다
    assert compare_level(None, 100) == "비교 불가"


def test_vs_yesterday_matches_24h_earlier():
    cong = [{"hour": "2026-10-08 06:00:00.0", "cntPerc": 100.0},
            {"hour": "2026-10-09 06:00:00.0", "cntPerc": 150.0}]
    s = summarize({}, cong, "교통센서3")
    assert s["vs_yesterday"] == {"now": 150.0, "yesterday": 100.0, "hour": "06:00", "level": "붐빔"}


def test_day_position():
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    assert day_position(90, vals) == "붐비는 편"
    assert day_position(10, vals) == "한산한 편"
    assert day_position(50, vals) == "보통"
    assert day_position(50, [1, 2]) == "비교 불가"


def test_fixture_has_no_24h_pair_but_day_position_works():
    s = summarize(load("eum_traffic_per_hour.json"), load("eum_congestion.json"), "교통센서3")
    assert s["vs_day"] in {"붐비는 편", "보통", "한산한 편"}
