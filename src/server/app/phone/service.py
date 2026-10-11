"""전화 알림(설계 §4.3). ClawOps 070 번호에 에이전트를 붙이고, 입항 알림 때 등록 번호로 전화를 건다.

ClawOps 가 하는 일: 번호·발신·전화 음성 변환·부품 사이 전달·말 끊기·통화 종료.
우리가 하는 일: 듣기(stt.py), 답하기(brain.py = 물어보기 엔진), 말하기(tts.py), 발신 조건, 화면용 통화 기록.

안전장치
- PHONE_ENABLED=1 인 서버만 번호에 붙는다(번호당 연결 하나 — 로컬·VM 이 동시에 붙으면 서로 밀어낸다).
- CALL_ALLOWED_NUMBERS 에 있는 번호만 저장·발신한다(공개 주소에서 모르는 사람에게 전화가 가지 않게).
- 알림 발신은 진행 막대 '전화 켜기'가 켜졌을 때만(기본 꺼짐) — 데모 재생마다 발신 시간(체험 10분)이 빠지지 않게.
- 말이 없으면 IDLE_HANGUP_S 뒤, 길어져도 MAX_CALL_S 뒤 끊는다.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import Settings, phone_digits
from ..db import tx
from ..feed.clock import real_now
from ..rules import brief
from . import brain

log = logging.getLogger(__name__)

IDLE_HANGUP_S = 25.0
CLOSING_PAUSE_S = 2.0  # 끝인사 음성 길이 + 이만큼 뒤 끊는다. 전화로 소리가 실제 나오는 시점이 보내는 시점보다 늦다(10/11 실통화: 0.8초는 말 끝나자마자 끊기는 느낌)
MAX_CALL_S = 150.0
MAX_LINES = 40
ALLOWED_SPECIES = {None, "붉은대게", "살오징어", "골뱅이", "방어", "가자미류"}


def mask(phone: str) -> str:
    d = phone_digits(phone) or phone
    return f"{d[:3]}-****-{d[-4:]}" if len(d) >= 8 else "***"


# --- 전화 구독(call_subs) ---
def save_call_sub(conn: sqlite3.Connection, phone: str, species: str | None) -> None:
    with tx(conn):
        conn.execute("""INSERT INTO call_subs (phone, cond_json, created_at) VALUES (?,?,?)
                        ON CONFLICT(phone) DO UPDATE SET cond_json=excluded.cond_json""",
                     (phone, json.dumps({"species": species}, ensure_ascii=False), real_now().isoformat(timespec="seconds")))


def delete_call_sub(conn: sqlite3.Connection, phone: str) -> None:
    with tx(conn):
        conn.execute("DELETE FROM call_subs WHERE phone=?", (phone,))


def call_sub_of(conn: sqlite3.Connection, phone: str) -> dict | None:
    r = conn.execute("SELECT cond_json FROM call_subs WHERE phone=?", (phone,)).fetchone()
    return json.loads(r[0]) if r else None


DEBOUNCE_S = 0.1


@functools.cache
def _pipeline():
    """ClawOps 파이프라인은 받아쓰기 확정 뒤 0.5초를 더 기다린다(이어 말하면 합치려고). 우리 받아쓰기가 이미
    0.8초 침묵을 기다려 확정하므로 같은 기다림이 두 번이다 → 0.1초로 줄여 쿠션을 당긴다(10/11 실통화).
    SDK 내부 메서드라 clawops==0.62.0 고정에 기댄다."""
    from clawops.agent.pipeline import PipelineSession

    class FastPipeline(PipelineSession):
        async def _debounced_respond(self, delay: float) -> None:
            await super()._debounced_respond(min(delay, DEBOUNCE_S))

    return FastPipeline


class PhoneService:
    def __init__(self, settings: Settings, conn: sqlite3.Connection, answer_factory, cache_dir: Path) -> None:
        self.s, self.conn = settings, conn
        self._answer_factory = answer_factory  # () -> (question, history) -> chat 이벤트
        self.cache_dir = cache_dir
        self.enabled = bool(settings.phone_enabled and settings.clawops_api_key and settings.clawops_account_id
                            and settings.clawops_from_number)
        self.calls_on = False
        self.connected = False
        self.agent: Any = None
        self._pending_greeting: list[str] | None = None
        self._state: brain.CallState | None = None
        self._call: Any = None
        self._queue: list[tuple[str, list[str]]] = []
        self._last_activity = 0.0
        self._started_at = 0.0
        self._watch: asyncio.Task | None = None
        self.live: dict[str, Any] = {"active": False, "status": "idle", "lines": []}

    # --- 상태 ---
    def allowed(self, phone: str) -> bool:
        return phone in self.s.call_allowed_numbers

    def state(self) -> dict:
        return {"enabled": self.enabled, "connected": self.connected, "calls_on": self.calls_on,
                "number": self.s.clawops_from_number if self.enabled else None, **self.live}

    def _line(self, role: str, text: str) -> None:
        self._last_activity = time.monotonic()
        lines = self.live["lines"]
        lines.append({"role": role, "text": text, "t": real_now().strftime("%H:%M:%S")})
        del lines[:-MAX_LINES]

    # --- 시작·종료 ---
    async def start(self) -> None:
        if not self.enabled:
            log.info("전화 기능 꺼짐(PHONE_ENABLED=1 과 ClawOps 키·발신 번호가 있어야 켜짐)")
            return
        os.environ.setdefault("CLAWOPS_READY_FILE", "")  # SDK 준비 표시 파일(/tmp) 끔 — 윈도우에 경로가 없다
        from clawops.agent import ClawOpsAgent
        self.agent = ClawOpsAgent(api_key=self.s.clawops_api_key, account_id=self.s.clawops_account_id,
                                  from_=self.s.clawops_from_number, session_factory=self._new_session,
                                  builtin_tools=[])
        self.agent.on("call_start")(self._on_start)
        self.agent.on("call_end")(self._on_end)
        self.agent.on("call_failed")(self._on_failed)
        try:
            await asyncio.wait_for(self.agent.connect(), timeout=15)
            self.connected = True
            log.info("전화 에이전트 연결됨: %s", self.s.clawops_from_number)
        except Exception as e:
            log.error("전화 에이전트 연결 실패(웹·푸시는 정상 동작): %s", type(e).__name__)
        self._watch = asyncio.create_task(self._watchdog())
        asyncio.create_task(self.prebuild())

    async def stop(self) -> None:
        if self._watch:
            self._watch.cancel()
        if self.agent:
            try:
                await self.agent.disconnect()
            except Exception as e:
                log.warning("전화 에이전트 종료 중 오류: %s", type(e).__name__)

    def _tts(self, state: brain.CallState):
        from .tts import CachedTTS

        def spoken(text: str, seconds: float) -> None:
            self._last_activity = time.monotonic()
            if state.hangup_after and text.strip() == state.hangup_after:
                asyncio.create_task(self._hangup_later(seconds + CLOSING_PAUSE_S))

        return CachedTTS(self.cache_dir, self.s.gemini_api_key, self.s.gemini_tts_model, self.s.gemini_tts_voice,
                         openai_key=self.s.openai_api_key, on_spoken=spoken)

    async def prebuild(self) -> None:
        """고정 문장(인사·쿠션·끝인사) 음성을 한 번만 만들어 둔다. 이미 있으면 Gemini 를 부르지 않는다."""
        tts = self._tts(brain.CallState([], "inbound"))
        missing = [t for t in brain.FIXED if not tts.cached(t)]
        for t in missing:
            async for _ in tts.speak(t):
                pass
        if missing:
            log.info("전화 고정 문장 음성 %d개 생성(저장 위치 %s)", len(missing), self.cache_dir)

    def _new_session(self):
        from .stt import OpenAITranscribeSTT
        greeting, direction = (self._pending_greeting, "outbound") if self._pending_greeting else (brain.inbound_greeting(), "inbound")
        self._pending_greeting = None
        state = brain.CallState(greeting, direction)
        state.log = self._line
        self._state = state
        return _pipeline()(stt=OpenAITranscribeSTT(self.s.openai_api_key, on_final=state.heard, on_speech=state.speaking),
                               llm=brain.BaemajungLLM(self._answer_factory(), state),
                               tts=self._tts(state), system_prompt="", greeting=True)

    # --- 통화 이벤트 ---
    async def _on_start(self, call) -> None:
        self._call = call
        self._started_at = self._last_activity = time.monotonic()
        who = mask(call.to_number if call.direction == "outbound" else call.from_number)
        self.live = {"active": True, "status": "in-progress", "direction": call.direction, "who": who, "lines": []}
        if self._state:
            for s in self._state.greeting:
                self._line("ai", s)
        log.info("통화 시작(%s) %s", call.direction, who)

    async def _on_end(self, call) -> None:
        dur = getattr(call, "ended_duration", None) or int(getattr(call, "duration", 0))
        self.live.update(active=False, status="completed", duration=dur)
        self._call = None
        self._log_event({"status": "completed", "direction": call.direction, "seconds": dur})
        log.info("통화 종료: %s초", dur)
        await self._next()

    async def _on_failed(self, call, reason) -> None:
        self.live.update(active=False, status=str(reason))
        self._call = None
        self._log_event({"status": str(reason), "direction": call.direction})
        log.info("통화 연결 안 됨: %s", reason)
        await self._next()

    def _log_event(self, payload: dict) -> None:
        try:
            with tx(self.conn):
                self.conn.execute("INSERT INTO events (ts, kind, payload) VALUES (?,?,?)",
                                  (real_now().isoformat(timespec="seconds"), "call", json.dumps(payload, ensure_ascii=False)))
        except sqlite3.Error as e:
            log.warning("통화 기록 저장 실패: %s", e)

    async def _hangup_later(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._call:
            await self._call.hangup()

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(2)
            if not self._call:
                continue
            now = time.monotonic()
            if now - self._last_activity > IDLE_HANGUP_S or now - self._started_at > MAX_CALL_S:
                log.info("통화 자동 종료(말 없음 또는 시간 초과)")
                try:
                    await self._call.hangup()
                except Exception as e:
                    log.warning("자동 종료 실패: %s", type(e).__name__)
                self._started_at = self._last_activity = now  # 중복 시도 방지

    # --- 발신 ---
    async def dial(self, phone: str, greeting: list[str]) -> dict:
        if not self.enabled or not self.connected:
            return {"ok": False, "message": "전화 기능이 꺼져 있어 전화를 걸 수 없습니다. 서버 설정(PHONE_ENABLED)을 확인해 주세요."}
        if not self.allowed(phone):
            return {"ok": False, "message": "시연용 허용 목록에 없는 번호라 전화를 걸 수 없습니다."}
        if self._call or self.live.get("status") == "dialing":
            self._queue.append((phone, greeting))
            return {"ok": True, "queued": True}
        self._pending_greeting = greeting
        self.live = {"active": False, "status": "dialing", "direction": "outbound", "who": mask(phone), "lines": []}
        try:
            await self.agent.call(phone, timeout=30)
        except Exception as e:
            self._pending_greeting = None
            self.live.update(status="failed")
            log.warning("발신 실패: %s", e)
            return {"ok": False, "message": "전화를 걸지 못했습니다. 잠시 뒤 다시 시도해 주세요."}
        return {"ok": True}

    async def _next(self) -> None:
        if self._queue:
            phone, greeting = self._queue.pop(0)
            await asyncio.sleep(2)
            await self.dial(phone, greeting)

    async def on_alert(self, vt: datetime, body: str, est: dict) -> None:
        """입항 알림 훅. '전화 켜기'가 켜져 있으면 조건이 맞는 허용 번호에 전화를 건다."""
        if not (self.enabled and self.calls_on):
            return
        rows = self.conn.execute("SELECT phone, cond_json FROM call_subs").fetchall()
        targets = [r[0] for r in rows if self.allowed(r[0]) and brief.matches(json.loads(r[1]), est)]
        for phone in targets:
            res = await self.dial(phone, brain.outbound_greeting(body))
            log.info("입항 알림 전화 %s → %s: %s", vt.strftime("%H:%M"), mask(phone), res)
