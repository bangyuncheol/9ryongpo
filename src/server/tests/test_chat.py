import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime

import pytest

from app import db, geo
from app.agent import chat
from app.agent.tools import ToolContext, past_auction, run_tool
from app.collectors.auction import load_dir
from app.config import settings
from app.engine import Engine
from app.feed.clock import KST
from app.rules import visit

FLEET = [(3, "남진호", "연안자망어업", 4.92), (7, "강성호", "연안자망어업", 9.77), (17, "장명호", "연안자망어업", 4.93),
         (1, "제33안성호", "근해자망어업", 43.0), (2, "제33성한호", "근해채낚기어업", 29.0), (22, "삼기호", "연안통발어업", 1.99)]
TRAFFIC = {"last_hour": {"hour": "2026-10-13T05:00", "truck": 12, "total": 80}, "hours": [],
           "vs_yesterday": {"level": "한산"}, "vs_day": "한산한 편", "fetched_at": "x", "stale": False}


class FakeTraffic:
    async def now(self, sensor="교통센서3"):
        return TRAFFIC


@pytest.fixture
def ctx(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    load_dir(conn, settings.auction_dir)
    conn.executemany("INSERT INTO fleet (ship_id, name, biz, gt, raw_json, updated_at) VALUES (?,?,?,?, '{}', 'x')", FLEET)
    conn.commit()
    e = Engine(conn, eum=None, place=geo.AUCTION_PLACE, feed="sim")
    e.reload_fleet()
    e.clock._anchor_virtual = datetime.combine(date(2026, 10, 13), datetime.strptime("04:00", "%H:%M").time(), KST)
    return ToolContext(engine=e, traffic=FakeTraffic())


def collect(gen):
    async def go():
        return [ev async for ev in gen]
    return asyncio.run(go())


def test_tool_filters_43t_gillnetter(ctx):
    out = asyncio.run(run_tool(ctx, "get_arrival_forecast", {"biz": "자망", "min_gt": 42.5, "max_gt": 43.5}))
    assert [a["name"] for a in out["arriving"]] == ["제33안성호"]
    assert "04:35" <= out["arriving"][0]["eta"][11:16] <= "04:55"


def test_past_auction_returns_kg_price_not_prediction(ctx):
    out = past_auction(ctx.engine.conn, "붉은대게", 2025, 10)
    assert out["records"][0]["ym"] == "2025-10" and 5000 < out["records"][0]["kg_price"] < 6500
    assert "예측하지 않습니다" in out["note"]
    assert past_auction(ctx.engine.conn, "붉은대게", 2019, 1)["records"] == []


def test_visit_advice():
    boss = visit.recommend(TRAFFIC)
    assert "08:30까지" in boss["advice"] and "어제 이맘때보다 한산" in boss["advice"]
    tour = visit.recommend(TRAFFIC, visitor=True)
    assert "10:00 이후" in tour["advice"]
    assert "단정" not in tour["advice"]


def test_simple_mode_when_no_llm(ctx):
    evs = collect(chat.answer(None, "m", ctx, "43톤 자망선 언제 와?"))
    kinds = [e["type"] for e in evs]
    assert kinds[0] == "tool" and kinds[-1] == "answer"
    ans = evs[-1]
    assert ans["mode"] == "simple" and "제33안성호" in ans["text"] and "도착 예정" in ans["text"]


def test_simple_mode_routes(ctx):
    assert chat.route("오늘 오징어 있어?")[0][0] == "get_arrival_forecast"
    assert chat.route("붉은대게 작년엔 얼마였어?")[0] == ("get_past_auction", {"species": "붉은대게", "month": 10})
    assert chat.route("대게 들어오면 알려줘")[0] == ("subscribe", {"species": "붉은대게"})
    assert chat.route("몇 시에 가면 안 막혀?")[0][0] == "recommend_visit_time"


def test_subscribe_emits_action(ctx):
    evs = collect(chat.answer(None, "m", ctx, "대게 들어오면 알려줘"))
    assert {"type": "action", "name": "subscribe", "species": "붉은대게"} in evs


# --- 가짜 OpenAI 클라이언트로 LLM 경로 ---
@dataclass
class Call:
    name: str
    arguments: str
    call_id: str = "c1"
    type: str = "function_call"

    def model_dump(self, **kw):
        return {"type": self.type, "name": self.name, "arguments": self.arguments, "call_id": self.call_id}


@dataclass
class Resp:
    output: list
    output_text: str = ""


@dataclass
class FakeResponses:
    seen: list = field(default_factory=list)

    async def create(self, **kw):
        self.seen.append(kw)
        if len(self.seen) == 1:
            return Resp([Call("get_arrival_forecast", json.dumps({"biz": "자망", "min_gt": 42, "max_gt": 44}))])
        out = json.loads(kw["input"][-1]["output"])
        return Resp([], f"{out['arriving'][0]['name']}는 {out['arriving'][0]['eta'][11:16]}쯤 도착 예정입니다.")


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class BrokeClient:
    class responses:
        @staticmethod
        async def create(**kw):
            raise type("RateLimitError", (Exception,), {})("no credits")


def test_llm_path_uses_tool_output(ctx):
    client = FakeClient()
    evs = collect(chat.answer(client, "gpt-6.1-sol", ctx, "43톤 자망선 언제 와?"))
    assert [e["type"] for e in evs] == ["tool", "tool_result", "answer"]
    assert evs[-1]["mode"] == "llm" and "제33안성호" in evs[-1]["text"]
    first = client.responses.seen[0]
    assert first["reasoning"] == {"effort": "medium"} and first["model"] == "gpt-6.1-sol"
    assert first["input"][0]["role"] == "system" and "지어내지 않는다" in first["input"][0]["content"]


def test_llm_failure_falls_back_and_cools_down(ctx, monkeypatch):
    monkeypatch.setattr(chat, "_cooldown_until", 0.0)
    evs = collect(chat.answer(BrokeClient(), "m", ctx, "43톤 자망선 언제 와?"))
    assert evs[-1]["mode"] == "simple" and "제33안성호" in evs[-1]["text"]
    assert chat._cooldown_until > 0
    client = FakeClient()
    evs2 = collect(chat.answer(client, "m", ctx, "43톤 자망선 언제 와?"))
    assert client.responses.seen == [] and evs2[-1]["mode"] == "simple"  # 쿨다운 중엔 LLM을 부르지 않음


def test_empty_question(ctx):
    assert collect(chat.answer(None, "m", ctx, "   "))[0]["type"] == "error"


def test_species_question_answers_about_that_species(ctx):
    ans = collect(chat.answer(None, "m", ctx, "오늘 오징어 있어?"))[-1]["text"]   # 04:00: 채낚기선은 막 출발
    assert ans.startswith("지금 들어오는 배 중 살오징어")
    ctx.engine.clock.seek("04:30")
    ans = collect(chat.answer(None, "m", ctx, "오늘 오징어 있어?"))[-1]["text"]
    assert "제33성한호" in ans and "살오징어" in ans
