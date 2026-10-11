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
def ctx(tmp_path, auction_dir):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    load_dir(conn, auction_dir)
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
    assert "경매는 09:00에 시작합니다." in tour["advice"]
    for banned in ("덜 붐", "10:00", "참여할 수 없"):  # 확인 안 된 종료 시각·혼잡·참여 단정 금지
        assert banned not in tour["advice"]
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

    gate: list = field(default_factory=list)
    verdict: str = "IN"

    async def create(self, **kw):
        if kw["input"][0]["content"] in (chat.GATE, chat.GATE_VOICE):  # 범위 판정 호출은 따로 기록
            self.gate.append(kw)
            return Resp([], self.verdict)
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


def test_live_stale_positions_give_no_forecast_or_push(ctx):
    e = ctx.engine
    e.set_feed("live")
    e._live_rows = [{"ship_id": 1, "ts": "2025-04-27T14:07:38+09:00", "lat": 35.99, "lon": 129.60, "course": 270.0,
                     "speed": 8.0, "rcv_ts": "2025-04-27T14:07:38+09:00", "source": "live"}]
    from app.feed.clock import real_now
    e._live_at = real_now()  # 다시 부르지 않게
    pushed = []

    async def hook(t, new):
        pushed.append(new)
    e.hooks.append(hook)
    today = asyncio.run(e.today())
    assert today["arriving"] == [] and "2025-04-27" in today["notice"]
    ships = asyncio.run(e.ships())
    assert ships["ships"][0]["status"] == "미갱신"
    async def go():
        await e.tick(); await e.drain()
    asyncio.run(go())
    assert pushed == []


def test_fast_play_processes_every_10min_bucket(ctx):
    e = ctx.engine
    seen = []

    async def hook(t, new):
        seen.append((t.strftime("%H:%M"), sorted(a["ship_id"] for a in new)))
    e.hooks.append(hook)
    e.clock.seek("03:00")
    e.reset_tick()

    async def go():
        await e.tick()                    # 03:00
        e.clock.seek("03:40")             # 600배로 3초 = 30분 넘게 지난 상황
        await e.tick()
        await e.drain()
    asyncio.run(go())
    assert seen[0] == ("03:10", [3, 7, 17])  # 03:10 경계를 건너뛰지 않는다
    assert ("03:30", [1]) in seen


def test_inbox_shows_only_after_last_reset(ctx):
    from app import push
    from dataclasses import replace
    e = ctx.engine
    p = push.Pusher(e.conn, replace(settings, vapid_subject="mailto:a@b.c", vapid_private_key="x"), sender=lambda **kw: None)
    vt = e.clock.now().replace(hour=3, minute=10)
    asyncio.run(p.notify(vt, "t", "이전 리허설", {"overall": []}, []))
    e.reset_tick()
    asyncio.run(p.notify(vt, "t", "이번 재생", {"overall": []}, []))
    got = push.recent_notifications(e.conn, vt.replace(hour=4))
    assert [g["body"] for g in got] == ["이번 재생"]


def test_system_prompt_has_date_and_plain_text_rules(ctx):
    p = chat.system_prompt(ctx)
    assert "'작년'은 2025년" in p and "마크다운" in p and "붉은대게로 처리" in p
    assert chat.plain("**제33안성호**는 **04:45** 도착") == "제33안성호는 04:45 도착"


def test_history_is_sent_as_context_and_sanitized(ctx):
    client = FakeClient()
    hist = [{"q": "아주 오래된 질문", "a": "오래된 답"},
            {"q": "43톤 자망선 언제 와?", "a": "제33안성호가 04:45 도착 예정입니다."},
            {"q": "그 배 어디쯤이야?", "a": "9.4km 남았습니다."},
            {"q": 123, "a": None}]
    collect(chat.answer(client, "m", ctx, "그 배는 뭐 싣고 와?", hist))
    roles = [(i["role"], i["content"]) for i in client.responses.seen[0]["input"] if isinstance(i, dict) and "role" in i]
    assert [r for r, _ in roles] == ["system", "user", "user"]  # 이전 대화는 assistant 발화로 넣지 않는다(위조 방지)
    note = roles[1][1]
    assert note.startswith("[참고용 이전 대화") and "제33안성호가 04:45" in note and "아주 오래된" not in note
    assert roles[2] == ("user", "그 배는 뭐 싣고 와?")
    assert "그 배 어디쯤이야?" in client.responses.gate[0]["input"][1]["content"]  # 판정도 이전 질문을 본다
    assert chat.clean_history("not a list") == [] and chat.clean_history([{"q": "x" * 999, "a": "y"}])[0]["q"] == "x" * 300


def test_tools_hide_data_source_and_flag_category_only(ctx):
    out = asyncio.run(run_tool(ctx, "get_arrival_forecast", {}))
    assert "data_source" not in out and "notice" not in out
    d = asyncio.run(run_tool(ctx, "get_species_estimate", {"biz": "근해자망어업"}))
    # 들어오는 근해자망 배(제33안성호)가 있으면 알림과 같은 계산 → 어종 말 못하는 업종으로 표시(10/11 형식 변경)
    assert d["category_only_biz"] == ["근해자망어업"] and d["overall"] == [] and "말하지 않는다" in d["note"]
    p = chat.system_prompt(ctx)
    assert "시뮬레이션인지 실데이터인지는 말하지 않는다" in p and "선박 위치 데이터" not in p


def test_out_of_scope_question_is_refused_without_tools(ctx):
    client = FakeClient()
    client.responses.verdict = "OUT"
    evs = collect(chat.answer(client, "m", ctx, "이차방정식 x^2-5x+6=0 풀어줘"))
    assert evs == [{"type": "answer", "text": chat.REFUSAL, "mode": "llm", "scope": "OUT"}]  # scope: 전화가 문장을 바꿀 때 씀(10/11)
    assert client.responses.gate[0]["reasoning"] == {"effort": "low"}


def test_gate_failure_lets_question_through(ctx):
    class GateBroke(FakeResponses):
        async def create(self, **kw):
            if kw["input"][0]["content"] == chat.GATE:
                raise TimeoutError("gate")
            return await super().create(**kw)
    client = FakeClient()
    client.responses = GateBroke()
    evs = collect(chat.answer(client, "m", ctx, "43톤 자망선 언제 와?"))
    assert evs[-1]["mode"] == "llm" and "제33안성호" in evs[-1]["text"]


def test_system_prompt_has_scope_rule(ctx):
    assert chat.REFUSAL in chat.system_prompt(ctx)


def test_prompts_do_not_assume_visitor(ctx):
    desc = next(t["description"] for t in chat.TOOLS if t["name"] == "recommend_visit_time")
    assert "참여 불가" not in desc
    assert "단정하지 않는다" in chat.system_prompt(ctx) and "경매에 참여할 수 있는지는 말하지 않는다" in chat.system_prompt(ctx)


def test_voice_gate_can_say_unclear_but_web_cannot(ctx):
    client = FakeClient()
    client.responses.verdict = "UNCLEAR"
    evs = collect(chat.answer(client, "m", ctx, "오늘 돈 돼 있나요?", voice=True))
    assert evs[-1]["scope"] == "UNCLEAR" and client.responses.gate[0]["input"][0]["content"] == chat.GATE_VOICE
    evs = collect(chat.answer(client, "m", ctx, "오늘 돈 돼 있나요?"))
    assert evs[-1]["scope"] == "OUT"  # 화면 채팅은 IN/OUT 두 가지 그대로


def test_species_for_short_biz_matches_alert_calculation(ctx):
    """실통화(10/11): 알림은 붉은대게였는데 "자망선 뭐 싣고?"에 '추정 불가'로 답했다. 지금 들어오는 배 기준으로 맞춘다."""
    from app.rules import species
    out = asyncio.run(run_tool(ctx, "get_species_estimate", {"biz": "자망선"}))
    today = asyncio.run(ctx.engine.today())
    ships = [a for a in today["arriving"] + today["arrived"] if "자망" in (a.get("biz") or "")]
    assert ships and out["ships_named"] == [a["name"] for a in ships]
    assert out["overall"] == species.estimate(ctx.engine.conn, ships, 10)["overall"]  # 알림과 같은 계산
    out2 = asyncio.run(run_tool(ctx, "get_species_estimate", {"biz": "통발"}))  # 들어오는 통발 배가 없으면 업종 실적
    assert "by_biz" in out2 and out2["basis_note"].startswith("지금 들어오는 그 업종 배가 없어")
