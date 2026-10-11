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
    assert out == [brain.CUSHION, "제33안성호가 4시 45분쯤 들어옵니다.", brain.ASK_MORE]  # "그 배 뭐 싣고" → 주제 있음
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


def out_answer(scope):
    async def fn(q, history):
        yield {"type": "answer", "text": "배마중은 …만 안내해 드려요.", "mode": "llm", "scope": scope}
    return fn


def ask(st, fn, q):
    return collect(brain.BaemajungLLM(fn, st).generate([{"role": "user", "content": q}]))


def test_low_confidence_out_is_reasked_then_choices():
    st = brain.CallState([], "inbound")
    st.heard("오늘 돈 돼 있나요?", 0.03)
    assert ask(st, out_answer("OUT"), "오늘 돈 돼 있나요?") == [brain.SHORT_CUSHION, brain.REASK]
    st.heard("오늘 해보고 있나요?", 0.0)
    assert ask(st, out_answer("OUT"), "오늘 해보고 있나요?") == [brain.SHORT_CUSHION, brain.CHOICES]  # 같은 말을 반복하지 않는다
    assert ask(st, fake_answer(0)[0], "오늘 배 들어와 있나요?")[-1] == brain.ASK_MORE and st.misses == 0


def test_confident_offtopic_gets_soft_guide_and_unclear_is_reasked():
    st = brain.CallState([], "inbound")
    st.heard("이차방정식 좀 풀어 주세요.", 0.82)
    assert ask(st, out_answer("OUT"), "이차방정식 좀 풀어 주세요.") == [brain.SHORT_CUSHION, brain.OFFTOPIC]
    st.heard("옥외 광고가 있나요?", 0.9)  # 확신도는 높아도 말이 안 되는 문장이면 잘못 들은 것
    assert ask(st, out_answer("UNCLEAR"), "옥외 광고가 있나요?") == [brain.SHORT_CUSHION, brain.REASK]


def test_in_scope_answer_ignores_low_confidence():
    st = brain.CallState([], "inbound")
    st.heard("남진호 뭐 싣고 와요?", 0.05)  # 배 이름 같은 고유명사는 맞아도 확신도가 낮을 수 있다
    assert ask(st, fake_answer(0)[0], "남진호 뭐 싣고 와요?")[-1] == brain.ASK_MORE


def test_split_question_is_merged_into_one():
    fn, seen = fake_answer(0)
    st = brain.CallState([], "inbound")
    msgs = [{"role": "user", "content": brain.START}, {"role": "assistant", "content": "인사"},
            {"role": "user", "content": "이런 것까지 맥락을 다 읽고"}, {"role": "user", "content": "2차 방정식이 뭔지 알려주세요."}]
    collect(brain.BaemajungLLM(fn, st).generate(msgs))
    assert seen[0][0] == "이런 것까지 맥락을 다 읽고 2차 방정식이 뭔지 알려주세요." and seen[0][1] == []


def test_cushion_waits_while_user_is_still_speaking():
    st = brain.CallState([], "inbound")
    st.speaking(True)
    order = []

    async def run():
        gen = brain.BaemajungLLM(fake_answer(0)[0], st).generate([{"role": "user", "content": "오늘 배"}])
        first = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0.2)
        order.append(("나옴" if first.done() else "기다림"))
        st.speaking(False)
        order.append(await first)
        await gen.aclose()
    asyncio.run(run())
    assert order == ["기다림", brain.CUSHION]


def test_wait_quiet_gives_up_after_limit():
    st = brain.CallState([], "inbound")
    st.speaking(True)  # 소음으로 말 시작만 오고 끝이 안 오는 경우
    import time
    t = time.monotonic()
    asyncio.run(st.wait_quiet(0.2))
    assert 0.15 < time.monotonic() - t < 1.0


def test_inbound_greeting_asks_without_more():
    assert brain.inbound_greeting()[-1] == "궁금하신 거 있으세요?"
    assert brain.outbound_greeting("알림")[-1] == brain.ASK_MORE


def test_time_up_ends_after_current_answer():
    st = brain.CallState([], "inbound")
    st.time_up = True
    out = ask(st, fake_answer(0)[0], "오늘 배 들어와요?")
    assert out[-1] == brain.TIME_UP and st.hangup_after == brain.TIME_UP and brain.ASK_MORE not in out


def test_ship_names_for_stt_hint(tmp_path):
    ph, conn = _service(tmp_path)
    conn.execute("INSERT INTO fleet (ship_id, name, biz, gt, sign, raw_json, updated_at) VALUES (1, '남진호', '연안자망', 9, 's', '{}', 'x')")
    conn.execute("INSERT INTO forecast (ts, ship_id, d_km, eta) VALUES ('2026-10-11T03:40', 1, 9.0, '2026-10-11T04:26')")
    assert ph.ship_names()[0] == "남진호"
    from app.phone.stt import PhoneSTT
    stt = PhoneSTT("k", "c", ship_names=["남진호"])
    assert "남진호" in stt._clova_config()["keywordBoosting"]["boostings"][0]["words"]
    assert "prompt" not in stt._openai_session()["session"]["audio"]["input"]["transcription"]  # 힌트 누출 방지
    assert stt._clova_config()["semanticEpd"]["gapThreshold"] == 800 and stt.clova_ok
    assert not PhoneSTT("k").clova_ok  # CLOVA 키가 없으면 OpenAI 받아쓰기만


def test_clova_confidence_ignores_spaces():
    from app.phone.stt import _clova_conf
    tr = {"confidence": 0.9, "alignInfos": [{"word": "남", "confidence": 0.8}, {"word": " ", "confidence": 0.1},
                                            {"word": "진", "confidence": 0.6}]}
    assert _clova_conf(tr) == 0.6 and _clova_conf({"confidence": 0.7}) == 0.7


def test_fix_common_misrecognitions():
    from app.phone.stt import fix_text
    assert fix_text("뭐 남진호가 멋있고 들어오는지") == "뭐 남진호가 뭐 싣고 들어오는지"
    assert fix_text("예남진호 혹시 지금 뭐 씻고 들어오나요.") == "예남진호 혹시 지금 뭐 싣고 들어오나요."
    assert fix_text("오늘 댁에 들어오나요.") == "오늘 대게 들어오나요."
    assert fix_text("남진호 말고 지33 안성호 뭐 있고") == "남진호 말고 제33안성호 뭐 싣고"  # 명부 표기(제33안성호)로 붙는다
    assert fix_text("오늘 날씨 멋있네요") == "오늘 날씨 멋있네요"  # 맥락 없는 '멋있'은 그대로


def test_cushion_depends_on_topic_words():
    assert brain.cushion_for("오늘 남진호 들어오나") == brain.CUSHION
    assert brain.cushion_for("위판장 앞에 차 많아요?") == brain.CUSHION
    assert brain.cushion_for("작년 10월 대게 얼마였어?") == brain.CUSHION
    assert brain.cushion_for("포항 맛집 알려 주세요") == brain.CUSHION  # '알려'가 있어 주제로 본다(알림 요청과 구분 못 함)
    assert brain.cushion_for("이차방정식 풀어 주세요") == brain.SHORT_CUSHION
    assert brain.cushion_for("안녕하세요") == brain.SHORT_CUSHION
    assert brain.cushion_for("오늘 들어오는 배 있어요?") == brain.CUSHION and brain.cushion_for("차가 많아요?") == brain.CUSHION


def test_single_char_transcripts_are_dropped_unless_backchannel():
    from app.phone.stt import PhoneSTT
    got = []
    stt = PhoneSTT("k", on_final=lambda t, c: got.append(t))
    q = asyncio.Queue()
    for t in ("다", "네.", "아", "오늘 배 들어와요?"):
        stt._final(q, t, 1.0, "CLOVA")
    assert got == ["네.", "오늘 배 들어와요?"]


def test_openai_connection_has_no_prompt():
    from app.phone.stt import PhoneSTT
    assert "prompt" not in PhoneSTT("k")._openai_session()["session"]["audio"]["input"]["transcription"]
