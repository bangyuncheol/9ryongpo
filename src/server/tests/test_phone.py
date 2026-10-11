"""전화 알림(설계 §4.3). 네트워크 없이: 답하기 부품 흐름, 끝맺음 판정, 허용 번호·전화 켜기 조건, 번호 가리기."""
import asyncio
import json
from dataclasses import replace

from app import db
from app.config import phone_digits, settings
from app.phone import brain
from app.phone.service import PhoneService, call_sub_of, mask, save_call_sub


def collect(agen):
    async def run():
        return [x async for x in agen]
    return asyncio.run(run())


def fake_answer(delay: float, text: str = "제33안성호가 4시 45분쯤 들어옵니다."):
    seen = []

    async def fn(q, history):
        seen.append((q, history))
        await asyncio.sleep(delay)
        yield {"type": "tool_result", "name": "get_arrival_forecast", "summary": "입항 중 1척"}
        yield {"type": "answer", "text": text, "mode": "llm"}
    return fn, seen


def test_phone_digits_and_mask():
    assert phone_digits("010-1234-5678") == "01012345678"
    assert phone_digits("+82 10 1234 5678") == "01012345678"
    assert phone_digits("070-5276-7121") == "" and phone_digits("abc") == ""
    assert mask("01012345678") == "010-****-5678"


def test_greeting_is_fixed_sentences():
    st = brain.CallState(brain.outbound_greeting("04:25~04:35 자망선 3척 입항 예정 · 경매 09:00"), "outbound")
    out = collect(brain.BaemajungLLM(fake_answer(0)[0], st).generate([{"role": "user", "content": brain.START}]))
    assert out == [brain.HELLO, "04:25~04:35 자망선 3척 입항 예정 · 경매 09:00.", brain.ASK_MORE]


def test_slow_answer_gets_cushion_and_logs():
    fn, seen = fake_answer(0.3)
    st = brain.CallState([], "outbound")
    lines = []
    st.log = lambda r, t: lines.append((r, t))
    msgs = [{"role": "user", "content": brain.START}, {"role": "assistant", "content": "인사"},
            {"role": "user", "content": "43톤 자망선 언제 와?"}, {"role": "assistant", "content": f"{brain.CUSHION} 4시 45분쯤입니다. {brain.ASK_MORE}"},
            {"role": "user", "content": "그 배 뭐 싣고 와?"}]
    out = collect(brain.BaemajungLLM(fn, st).generate(msgs))
    assert out == [brain.CUSHION, "제33안성호가 4시 45분쯤 들어옵니다.", brain.ASK_MORE]
    assert seen[0][1] == [{"q": "43톤 자망선 언제 와?", "a": "4시 45분쯤입니다."}]  # 인사·쿠션·되묻기는 이력에서 뺌
    assert [r for r, _ in lines] == ["user", "tool", "ai"]


def test_cushion_comes_first_even_for_fast_answer():
    out = collect(brain.BaemajungLLM(fake_answer(0)[0], brain.CallState([], "inbound")).generate(
        [{"role": "user", "content": "차 많아?"}]))
    assert out[0] == brain.CUSHION  # 실통화(10/11): 답이 0.6초 안에 나온 적이 없어 기다리지 않고 바로 낸다


def test_pipeline_debounce_is_shortened(monkeypatch):
    import clawops.agent.pipeline as cp
    from app.phone import service
    seen = []

    async def fake(self, delay):
        seen.append(delay)
    monkeypatch.setattr(cp.PipelineSession, "_debounced_respond", fake)
    fast = service._pipeline()
    assert fast is service._pipeline() and issubclass(fast, cp.PipelineSession)
    asyncio.run(fast._debounced_respond(object.__new__(fast), 0.5))
    assert seen == [service.DEBOUNCE_S]


def test_closing_words_end_the_call():
    for t in ("없어요", "네 괜찮아요", "아니요.", "고마워요", "됐어요 끊을게요"):
        assert brain.is_closing(t), t
    for t in ("대게 없어요?", "오늘 들어오는 배 없어요? 오징어 배는요?", "43톤 자망선 언제 와?"):
        assert not brain.is_closing(t), t
    st = brain.CallState([], "outbound")
    out = collect(brain.BaemajungLLM(fake_answer(0)[0], st).generate([{"role": "user", "content": "없어요"}]))
    assert out == [brain.CLOSING_OUT] and st.hangup_after == brain.CLOSING_OUT


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def call(self, to, timeout=60):
        self.calls.append(to)


def _service(tmp_path, allowed=("01011112222",)):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    s = replace(settings, phone_enabled=True, clawops_api_key="k", clawops_account_id="a",
                clawops_from_number="07000000000", call_allowed_numbers=allowed)
    ph = PhoneService(s, conn, lambda: None, tmp_path / "tts")
    ph.agent, ph.connected = FakeAgent(), True
    return ph, conn


def test_alert_calls_only_when_switched_on_and_allowed(tmp_path):
    ph, conn = _service(tmp_path)
    save_call_sub(conn, "01011112222", "붉은대게")
    save_call_sub(conn, "01033334444", None)  # 허용 목록 밖: 저장돼 있어도 걸지 않는다
    est = {"overall": [{"name": "붉은대게", "share": 0.79}]}
    asyncio.run(ph.on_alert(None, "본문", est))
    assert ph.agent.calls == []  # 전화 꺼짐(기본)
    ph.calls_on = True
    asyncio.run(ph.on_alert(__import__("datetime").datetime(2026, 10, 10, 3, 10), "본문", est))
    assert ph.agent.calls == ["01011112222"] and ph._pending_greeting == brain.outbound_greeting("본문")
    assert call_sub_of(conn, "01011112222") == {"species": "붉은대게"}


def test_dial_refuses_unlisted_number_and_queues_second(tmp_path):
    ph, _ = _service(tmp_path, allowed=("01011112222", "01055556666"))
    res = asyncio.run(ph.dial("01099998888", ["x"]))
    assert not res["ok"] and "허용 목록" in res["message"]
    assert asyncio.run(ph.dial("01011112222", ["a"]))["ok"]
    assert asyncio.run(ph.dial("01055556666", ["b"])) == {"ok": True, "queued": True}  # 동시 통화 1건
    assert ph.agent.calls == ["01011112222"] and ph.state()["who"] == "010-****-2222"


def test_events_kind_call_is_logged(tmp_path):
    ph, conn = _service(tmp_path)
    ph._log_event({"status": "completed", "seconds": 42})
    row = conn.execute("SELECT kind, payload FROM events WHERE kind='call'").fetchone()
    assert json.loads(row[1])["seconds"] == 42
