"""전화 답하기 부품: 물어보기 엔진을 ClawOps 파이프라인의 LLM 자리에 끼운다(설계 §4.3).

화면 질문창과 같은 엔진(범위 판정 + 도구 6개 + 규칙)을 그대로 쓰고, 전화 말투 규칙만 덧붙인다.
- 첫마디: 파이프라인이 "[통화 시작]"을 넣으면 인사 + 알림 문장 + "더 궁금하신 거 있으세요?"
- 질문: 쿠션("네, 확인해 볼게요.")을 바로 먼저 내보낸다. 범위 판정 + 답변만 2초가 넘어 기다릴 이유가 없다(10/11 실통화).
  쿠션·인사·되묻기는 고정 문장이라 음성이 저장돼 있어 바로 재생된다(interview_bridge 쿠션 설계).
- 끝: "없어요"·"괜찮아요" 같은 짧은 끝맺음이면 끝인사 후 통화를 끊는다.
문장마다 마침표로 끝나게 내보내야 파이프라인이 문장 단위로 끊어 말하기 부품에 넘긴다.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator, Callable

from ..agent import chat

log = logging.getLogger(__name__)

START = "[통화 시작]"
HELLO = "안녕하세요, 배마중입니다."
INBOUND_INTRO = "구룡포 위판장 입항과 어종, 위판장 앞 교통을 알려 드려요."
ASK_FIRST = "궁금하신 거 있으세요?"  # 걸려 온 전화 첫인사: 아직 안내한 게 없어 '더'를 빼다(10/11)
ASK_MORE = "더 궁금하신 거 있으세요?"
CUSHION = "네, 확인해 볼게요."
SHORT_CUSHION = "네."  # 주제 단어가 없는 말(잘못 들음·엉뚱한 질문일 가능성)엔 짧게. '확인해 볼게요' 뒤 '잘 못 들었어요'가 어색했다(10/11)
# '배'·'차'처럼 한 글자 단어는 띄어 쓰였거나 조사가 붙을 때만('이차방정식'의 '차'를 주제로 보지 않게)
TOPIC_RE = re.compile(r"[가-힣0-9]+호|들어오|들어와|들어온|언제|입항|싣고|실고|어종|대게|홍게|오징어|골뱅이|방어|가자미|고기|"
                      r"교통|막히|주차|트럭|얼마|가격|시세|경매|위판|몇 ?시|알림|알려|"
                      r"(?:^|\s)(?:배|차)(?=\s|$|[가는들도랑요량])")
CLOSING = "네, 전화 주셔서 감사합니다. 좋은 하루 보내세요."
CLOSING_OUT = "네, 알겠습니다. 좋은 하루 보내세요."
SLOW = "확인이 늦어지고 있어요. 잠시 뒤에 다시 여쭤 봐 주세요."
TIME_UP = "통화가 길어져 이만 끊을게요. 다시 걸어 주시면 이어서 알려 드릴게요."  # 상한 시간이 지나면 하던 답 뒤에(10/11)
# 범위 밖 판정일 때(10/11): 잘못 들은 것 같으면 다시 묻고, 두 번째부터는 선택지를 준다. 분명한 엉뚱한 질문은 부드럽게 안내.
REASK = "죄송해요, 제가 잘 못 들었어요. 한 번만 다시 말씀해 주세요."
CHOICES = "들어오는 배, 대게, 위판장 앞 교통 중에 어떤 게 궁금하세요?"
OFFTOPIC = "그건 제가 안내해 드리기 어려워요. 들어오는 배나 어종, 위판장 앞 교통을 물어봐 주세요."
FIXED = (HELLO, INBOUND_INTRO, ASK_FIRST, ASK_MORE, CUSHION, SHORT_CUSHION, CLOSING, CLOSING_OUT, SLOW, REASK, CHOICES, OFFTOPIC, TIME_UP)
QUIET_WAIT_S = 3.0  # 사용자가 아직 말하는 중이면 쿠션·답을 이만큼까지 미룬다(소음으로 '말 시작'만 오고 끝이 안 오는 경우 상한)
LOW_CONF = 0.2  # 받아쓰기 최저 글자 확신도. 합성 음성 시험(10/11): 크게 틀린 문장 0.00~0.05, 맞은 문장 0.32~0.97

ANSWER_TIMEOUT_S = 20.0
_END_RE = re.compile(r"^(아니(요|에요|오)?|없(어|어요|습니다)|괜찮(아|아요|습니다)|됐(어|어요|습니다)|끊(을게요|어요|겠습니다)|"
                     r"고마(워|워요|웠어요)|감사(해요|합니다)|그게 다(예요|에요)?|이제 됐(어|어요)|수고(하세요|하셨습니다))")


def is_closing(text: str) -> bool:
    t = re.sub(r"[\s.,!?~]+", " ", text).strip()
    return len(t) <= 15 and bool(_END_RE.match(t.replace("네 ", "").replace("예 ", "").strip()))


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?", "。")) else text + "."


class CallState:
    """통화 1건의 상태. 동시 통화 1건(요금제 한도)이라 서비스가 '지금 통화' 하나만 들고 있다."""

    def __init__(self, greeting: str, direction: str) -> None:
        self.greeting = greeting
        self.direction = direction
        self.hangup_after: str | None = None  # 이 문장을 다 말하면 끊는다
        self.conf: dict[str, float | None] = {}  # 받아쓰기 문장 → 최저 글자 확신도
        self.misses = 0  # 연속으로 못 알아들은 횟수
        self.time_up = False  # 통화 상한이 지나면 서비스가 켠다 → 다음 답 뒤에 끝인사하고 끊는다
        self._quiet = asyncio.Event()
        self._quiet.set()
        self.log: Callable[[str, str], None] = lambda role, text: None

    def speaking(self, on: bool) -> None:
        """받아쓰기 연결의 말 시작(True)·말 끝(False) 신호."""
        if on:
            self._quiet.clear()
        else:
            self._quiet.set()

    async def wait_quiet(self, max_s: float = QUIET_WAIT_S) -> None:
        """말하는 중이면 끝날 때까지(최대 max_s) 기다린다. 그사이 뒷말이 확정되면 파이프라인이 이 응답을 취소하고
        두 문장을 합쳐 다시 부른다(10/11 실통화: 말 중간에 쉬면 앞 절반에 먼저 답하던 문제)."""
        try:
            await asyncio.wait_for(self._quiet.wait(), timeout=max_s)
        except asyncio.TimeoutError:
            log.info("말 끝 신호가 %.0f초 안에 오지 않아 그대로 답함(소음일 수 있음)", max_s)

    def heard(self, text: str, conf: float | None) -> None:
        self.conf[text.strip()] = conf

    def reply_for_out(self, question: str, scope: str) -> str:
        """범위 밖 판정을 전화 문장으로. 확신도가 낮거나 말이 안 되는 문장이면 잘못 들은 것으로 본다."""
        conf = self.conf.get(question.strip())
        misheard = scope == "UNCLEAR" or (conf is not None and conf < LOW_CONF)
        if not misheard:
            self.misses = 0
            return OFFTOPIC
        self.misses += 1
        return REASK if self.misses == 1 else CHOICES


class BaemajungLLM:
    def __init__(self, answer_fn: Callable[..., AsyncIterator[dict]], state: CallState) -> None:
        self._answer = answer_fn  # (question, history) -> chat.answer 이벤트
        self.state = state

    @staticmethod
    def _history(messages: list[dict[str, Any]]) -> list[dict]:
        """파이프라인 대화 기록 → 질문창 형식의 이전 질문·답. 인사와 쿠션은 뺀다."""
        pairs, q = [], None
        for m in messages:
            if m.get("role") == "user":
                q = m.get("content") if m.get("content") != START else None
            elif m.get("role") == "assistant" and q and m.get("content"):
                a = m["content"].replace(CUSHION, "").replace(ASK_MORE, "").strip()
                if a:
                    pairs.append({"q": q, "a": a})
                q = None
        return pairs

    async def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> AsyncIterator[str]:
        # 끝에 이어진 사용자 말(중간에 쉬어서 둘로 나뉜 문장)은 한 질문으로 합친다
        tail: list[str] = []
        for m in reversed(messages):
            if m.get("role") != "user":
                break
            tail.insert(0, (m.get("content") or "").strip())
        last = " ".join(t for t in tail if t) if tail else START
        if START in tail:
            last = START
        if last == START:
            for s in self.state.greeting:
                yield s
            return
        self.state.log("user", last)
        if is_closing(last):
            bye = CLOSING if self.state.direction == "inbound" else CLOSING_OUT
            self.state.hangup_after = bye
            yield bye
            return
        history = self._history(messages[:len(messages) - len(tail)])
        result: dict[str, str] = {}

        async def run() -> None:
            async for ev in self._answer(last, history):
                if ev["type"] == "tool_result":
                    self.state.log("tool", f"{ev.get('name')}: {ev.get('summary')}")
                elif ev["type"] == "answer":
                    result["text"] = ev["text"]
                    result["scope"] = ev.get("scope", "IN")
                elif ev["type"] == "error":
                    result["text"] = ev["message"]

        task = asyncio.create_task(run())
        try:
            await self.state.wait_quiet()
            yield cushion_for(last)
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=ANSWER_TIMEOUT_S)
            except asyncio.TimeoutError:
                log.warning("전화 답이 %.0f초 넘게 걸려 안내 문장으로 대신함", ANSWER_TIMEOUT_S)
                yield SLOW
                return
            await self.state.wait_quiet()  # 답을 만드는 사이 다시 말을 시작했으면 끝날 때까지
            if result.get("scope", "IN") != "IN":
                text = self.state.reply_for_out(last, result["scope"])
                log.info("전화 범위 밖(%s, 확신도 %s) → %s", result["scope"], self.state.conf.get(last), text[:20])
                self.state.log("ai", text)
                yield text  # 되묻는 문장이라 '더 궁금하신 거'를 붙이지 않는다
                return
            self.state.misses = 0
            text = result.get("text") or SLOW
            self.state.log("ai", text)
            yield _sentence(text)
            if self.state.time_up:
                self.state.hangup_after = TIME_UP
                self.state.log("ai", TIME_UP)
                yield TIME_UP
                return
            yield ASK_MORE
        finally:
            if not task.done():  # 말 끊기(barge-in)로 응답이 취소되면 엔진 호출도 멈춘다
                task.cancel()


def cushion_for(question: str) -> str:
    return CUSHION if TOPIC_RE.search(question) else SHORT_CUSHION


def outbound_greeting(alert_body: str) -> list[str]:
    return [HELLO, _sentence(alert_body), ASK_MORE]


def inbound_greeting() -> list[str]:
    return [HELLO, INBOUND_INTRO, ASK_FIRST]


def chat_answer_fn(llm: Any, model: str, ctx: Any) -> Callable[[str, list[dict]], AsyncIterator[dict]]:
    def fn(question: str, history: list[dict]) -> AsyncIterator[dict]:
        return chat.answer(llm, model, ctx, question, history, voice=True)
    return fn
