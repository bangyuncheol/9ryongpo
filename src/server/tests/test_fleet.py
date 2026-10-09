from app.collectors.fleet import parse_sign, to_row


def test_parse_sign_fishery_types():
    assert parse_sign("0003005-6491102 근해자망어업(43톤)") == ("근해자망어업", 43.0)
    assert parse_sign("0504003-6312000 수하식양식업(4.97톤)") == ("수하식양식업", 4.97)
    assert parse_sign("0204004-6458000 연근해어획물운반업(19톤)") == ("연근해어획물운반업", 19.0)


def test_parse_sign_missing():
    assert parse_sign(None) == (None, None)
    assert parse_sign("표지판 없음") == (None, None)


def test_to_row_uses_sign_when_type_empty():
    raw = {"id": 1, "shipId": "0003005-6491102", "type": None, "name": "제33안성호",
           "gt": 43.0, "sign": "0003005-6491102 근해자망어업(43톤)"}
    row = to_row(raw, "2026-10-10T00:00:00+00:00")
    assert row[0] == 1 and row[2] == "제33안성호" and row[3] == "근해자망어업" and row[4] == 43.0
