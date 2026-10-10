import asyncio
import json
from dataclasses import replace
from datetime import datetime

import pytest

from app import db, push
from app.config import settings
from app.feed.clock import KST
from app.rules import brief

SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "k", "auth": "a"}}
VT = datetime(2026, 10, 13, 3, 10, tzinfo=KST)
EST = {"overall": [{"name": "붉은대게", "share": 0.78}, {"name": "골뱅이", "share": 0.1}]}
NEW = [{"ship_id": 3, "biz": "연안자망어업", "eta": "2026-10-13T04:25+09:00"},
       {"ship_id": 7, "biz": "연안자망어업", "eta": "2026-10-13T04:30+09:00"},
       {"ship_id": 17, "biz": "연안자망어업", "eta": "2026-10-13T04:35+09:00"}]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    return c


def test_template_text():
    title, body = brief.template(NEW, EST)
    assert body == "04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성. 경매 09:00(기본값)"


def test_matches():
    assert brief.matches({"species": None}, EST)
    assert brief.matches({"species": "붉은대게"}, EST)
    assert not brief.matches({"species": "골뱅이"}, EST)  # 20% 미만
    assert not brief.matches({"species": "살오징어"}, EST)


def test_save_subscription_validates(conn):
    with pytest.raises(ValueError):
        push.save_subscription(conn, {"endpoint": "http://x"}, {"species": None})
    with pytest.raises(ValueError):
        push.save_subscription(conn, SUB, {"species": "고래"})
    a = push.save_subscription(conn, SUB, {"species": "붉은대게"})
    b = push.save_subscription(conn, SUB, {"species": None})  # 같은 기기는 조건만 갱신
    assert a == b and conn.execute("SELECT COUNT(*) FROM subs").fetchone()[0] == 1


class FakeResp:
    def __init__(self, code): self.status_code = code


def test_notify_sends_to_matching_and_drops_gone(conn):
    sent = []

    def sender(**kw):
        sent.append(kw)
        if kw["subscription_info"]["endpoint"].endswith("gone"):
            raise push.WebPushException("gone", response=FakeResp(410))

    push.save_subscription(conn, SUB, {"species": "붉은대게"})
    push.save_subscription(conn, {**SUB, "endpoint": SUB["endpoint"] + "gone"}, {"species": None})
    push.save_subscription(conn, {**SUB, "endpoint": SUB["endpoint"] + "squid"}, {"species": "살오징어"})
    s = replace(settings, vapid_private_key="x", vapid_subject="mailto:team@example.com")
    r = asyncio.run(push.Pusher(conn, s, sender=sender).notify(VT, "t", "b", EST, [3]))
    assert r["ok"] == 1 and r["gone"] == 1 and len(sent) == 2
    assert json.loads(sent[0]["data"])["body"] == "b"
    assert conn.execute("SELECT COUNT(*) FROM subs").fetchone()[0] == 2  # 만료 구독 삭제


def test_notify_without_vapid_subject_records_but_skips(conn):
    push.save_subscription(conn, SUB, {"species": None})
    s = replace(settings, vapid_private_key="x", vapid_subject="")
    r = asyncio.run(push.Pusher(conn, s, sender=lambda **kw: pytest.fail("보내면 안 됨")).notify(VT, "t", "b", EST, []))
    assert r["skipped_config"] is True
    assert push.recent_notifications(conn, VT)[0]["body"] == "b"  # 알림함에는 남는다


def test_recent_notifications_hides_future_and_duplicates(conn):
    s = replace(settings, vapid_private_key="x", vapid_subject="mailto:a@b.c")
    p = push.Pusher(conn, s, sender=lambda **kw: None)
    asyncio.run(p.notify(VT, "t", "같은 장면", EST, []))
    asyncio.run(p.notify(VT, "t", "같은 장면", EST, []))  # 되감아 다시 재생
    asyncio.run(p.notify(VT.replace(hour=5), "t", "나중 장면", EST, []))
    got = push.recent_notifications(conn, VT.replace(minute=30))
    assert [g["body"] for g in got] == ["같은 장면"]


def test_vapid_subject_accepts_bare_email():
    from app.config import _vapid_subject
    assert _vapid_subject("team@example.com") == "mailto:team@example.com"
    assert _vapid_subject("mailto:a@b.c") == "mailto:a@b.c"
    assert _vapid_subject("") == ""


TEMPLATE = "04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성. 경매 09:00(기본값)"


def test_accept_keeps_numbers_exact():
    assert brief.accept(TEMPLATE, "자망선 3척 04:25~04:35 입항 예정, 붉은대게·골뱅이 가능성. 경매 09:00(기본값)")
    assert not brief.accept(TEMPLATE, "자망선 4척 04:25~04:35 입항 예정, 붉은대게 가능성. 경매 09:00")  # 숫자 바뀜
    assert not brief.accept(TEMPLATE, "자망선 3척 입항 예정, 붉은대게 가능성. 경매 09:00")              # 시각 빠짐
    assert not brief.accept(TEMPLATE, "04:25~04:35 자망선 3척, 붉은대게 확실. 경매 09:00")              # '가능성' 빠짐


class _R:
    def __init__(self, text): self.output_text = text


class _Client:
    def __init__(self, text): self.text = text; self.responses = self

    async def create(self, **kw): return _R(self.text)


def test_polish_falls_back_on_bad_llm_output(monkeypatch):
    from app.agent import chat
    monkeypatch.setattr(chat, "_cooldown_until", 0.0)
    good = "04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성 · 경매 09:00(기본값)"
    assert asyncio.run(brief.polish(_Client(good), "m", TEMPLATE)) == (good, "llm")
    assert asyncio.run(brief.polish(_Client("자망선 5척 곧 입항!"), "m", TEMPLATE)) == (TEMPLATE, "template")
    assert asyncio.run(brief.polish(None, "m", TEMPLATE)) == (TEMPLATE, "template")


def test_inbox_keeps_latest_five(conn):
    p = push.Pusher(conn, replace(settings, vapid_private_key="x", vapid_subject="mailto:a@b.c"), sender=lambda **kw: None)
    for m in range(7):
        asyncio.run(p.notify(VT.replace(minute=m), "t", f"알림 {m}", EST, []))
    got = push.recent_notifications(conn, VT.replace(hour=4))
    assert [g["body"] for g in got] == ["알림 6", "알림 5", "알림 4", "알림 3", "알림 2"]
