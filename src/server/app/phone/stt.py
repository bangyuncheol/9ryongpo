"""전화 듣기 부품(설계 §4.3): 받아쓰기는 CLOVA, 말 시작 신호와 대비책은 OpenAI.

ClawOps 파이프라인이 전화 음성을 PCM16 16kHz 로 넘겨주면 같은 음성을 두 곳에 동시에 보낸다.
- CLOVA Speech(Nest, gRPC): 확정 문장. 한국어 특화 + 키워드 부스팅(배 이름·어종)으로 고유명사를 맞힌다.
  semanticEpd 로 0.8초 침묵마다 문장을 끊어 준다. 실통화 녹음 6개(10/11): '남진호' CLOVA 5/5, OpenAI 1/5.
  OpenAI 에 배 이름을 힌트로 넣으면 4/5까지 오르지만, 알아듣기 어려운 음성에서 힌트 전체를 받아쓰기로 내뱉어 쓰지 않는다.
- OpenAI 받아쓰기 전용 연결(`intent=transcription`, 1분 약 0.3센트): 모델 기반 말 시작 감지(→ interim: AI 음성 멈춤,
  '말하는 중' 대기). CLOVA 연결이 실패하면 그때부터 이 연결의 확정 문장을 쓴다(대비책).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import re
import time
import wave
from pathlib import Path
from typing import AsyncIterator, Callable

import websockets
from clawops.agent._audio import resample_pcm16
from clawops.agent.pipeline import SpeechEvent

log = logging.getLogger(__name__)

URL = "wss://api.openai.com/v1/realtime?intent=transcription"
BACKCHANNEL_1 = {"네", "예", "응"}  # 한 글자 받아쓰기 중 맞장구로 받아 주는 것. 나머지 한 글자는 잡음·잘못 들음으로 버린다(10/11 실통화 '다')
CLOVA_ADDR = "clovaspeech-gw.ncloud.com:50051"
KEYWORDS = ["구룡포", "위판장", "입항", "경매", "자망선", "채낚기", "통발", "붉은대게", "홍게", "대게", "골뱅이",
            "오징어", "방어", "가자미", "싣고"]
CLOVA_CHUNK = 3200  # 100ms(16kHz·2바이트). interview_bridge 와 같은 단위로 묶어 보낸다


# 위판장 전화에서 거의 확실한 받아쓰기 오류를 엔진에 넘기기 전에 바로잡는다(10/11 실통화 녹음에서 반복 확인).
FIXES = [
    (re.compile(r"(뭐|머)\s*(있고|씻고|시고)"), r"뭐 싣고"),
    (re.compile(r"멋있(고|게)\s*(들어|와|오)"), r"뭐 싣고 \2"),
    (re.compile(r"댁에\s*(들어|와|오|있)"), r"대게 \1"),
    (re.compile(r"(^|\s)지\s?(\d+)\s?(?=[가-힣]+호)"), r"\1제\2"),
    (re.compile(r"붉은\s?대{2,}게"), "붉은대게"),  # '붉은대대게'(10/13 물어보기 음성 시험)
]


def fix_text(text: str) -> str:
    out = text
    for pat, rep in FIXES:
        out = pat.sub(rep, out)
    return out


def clova_config(keywords: list[str], gap_ms: int = 800) -> dict:
    """CLOVA Nest 설정(전화·웹 물어보기 음성이 같이 쓴다). 형식은 interview_bridge 운영 코드(driver/stt.py)와 같다."""
    return {"transcription": {"language": "ko"},
            "keywordBoosting": {"boostings": [{"words": ",".join(keywords), "weight": 0.5}]},
            # 침묵(gap) 기준으로 문장을 끊어 확정한다. 녹음 2개+1.5초 무음 시험에서 문장별로 따로 확정(10/11)
            "semanticEpd": {"skipEmptyText": True, "useWordEpd": False, "usePeriodEpd": True,
                            "gapThreshold": gap_ms, "durationThreshold": 20000, "syllableThreshold": 0}}


# --- 웹 물어보기 음성(10/13 오너): 브라우저가 녹음을 PCM16 16kHz 한 덩어리로 보내면 CLOVA 로 받아쓴다 ---
PCM_RATE = 16000
WEB_MAX_SEC, WEB_MIN_SEC = 20, 0.3


def pcm_problem(n_bytes: int) -> str | None:
    """받은 녹음 길이가 받아쓸 만한지. 문제가 있으면 사용자에게 보일 한 문장."""
    sec = n_bytes / (PCM_RATE * 2)
    if sec > WEB_MAX_SEC:
        return f"말은 {WEB_MAX_SEC}초 안으로 해 주세요."
    if sec < WEB_MIN_SEC:
        return "목소리가 들리지 않았어요. 다시 말씀해 주세요."
    return None


async def recognize_once(key: str, pcm: bytes, keywords: list[str], recognize=None, wait_s: float = 6.0) -> str:
    """녹음 한 덩어리를 CLOVA 에 100ms 단위로 흘려보내고, 확정 문장을 이어 붙여 돌려준다(전화와 같은 오류 고침 적용).
    끝 표시(epFlag)를 보낸 뒤 보내는 쪽을 바로 닫으면 CLOVA 가 받아쓰기 결과 없이 끝낸다(10/13 실측: 설정 응답만 옴).
    그래서 끝 표시 뒤 결과가 오고 0.5초 더 조용할 때까지(최대 wait_s) 연결을 열어 둔다.
    recognize: 시험에서 gRPC 대신 넣는 함수(요청 반복자 → 응답 반복자)."""
    import grpc
    from .nest import nest_pb2, nest_pb2_grpc

    pcm = pcm[: len(pcm) // 2 * 2]
    sent_end = asyncio.Event()
    last_text = [0.0]  # 끝 표시 뒤 마지막 결과가 온 때

    async def reqs():
        yield nest_pb2.NestRequest(type=nest_pb2.CONFIG, config=nest_pb2.NestConfig(config=json.dumps(clova_config(keywords))))
        chunks = [pcm[i:i + CLOVA_CHUNK] for i in range(0, len(pcm), CLOVA_CHUNK)] + [b""]
        for seq, chunk in enumerate(chunks, 1):
            last = seq == len(chunks)
            yield nest_pb2.NestRequest(type=nest_pb2.DATA, data=nest_pb2.NestData(
                chunk=chunk, extra_contents=json.dumps({"seqId": seq, "epFlag": last})))
        sent_end.set()
        t0 = time.monotonic()
        while time.monotonic() - t0 < wait_s:
            if last_text[0] and time.monotonic() - last_text[0] > 0.5:
                return
            await asyncio.sleep(0.05)

    texts: list[str] = []
    ch = None
    if recognize is None:
        ch = grpc.aio.secure_channel(CLOVA_ADDR, grpc.ssl_channel_credentials())
        stub = nest_pb2_grpc.NestServiceStub(ch)
        recognize = lambda it: stub.recognize(it, metadata=[("authorization", key)])  # noqa: E731
    try:
        async for r in recognize(reqs()):
            if not r.contents:
                continue
            text = ((json.loads(r.contents).get("transcription") or {}).get("text") or "").strip()
            if text:
                texts.append(text)
                if sent_end.is_set():
                    last_text[0] = time.monotonic()
    finally:
        if ch is not None:
            await ch.close()
    return fix_text(" ".join(texts)).strip()


def _clova_conf(tr: dict) -> float | None:
    """CLOVA 글자별 확신도 중 가장 낮은 값(공백 제외). OpenAI 최저 확신도와 같은 쓰임(다시 묻기 판정)."""
    cs = [a.get("confidence") for a in tr.get("alignInfos") or [] if (a.get("word") or "").strip() and a.get("confidence") is not None]
    return min(cs) if cs else tr.get("confidence")


class PhoneSTT:
    def __init__(self, openai_key: str, clova_key: str = "", silence_ms: int = 800,
                 on_final: Callable[[str, float | None], None] | None = None,
                 on_speech: Callable[[bool], None] | None = None, record_dir: Path | None = None,
                 ship_names: list[str] | None = None) -> None:
        self._key, self._clova_key, self._silence_ms = openai_key, clova_key, silence_ms
        self._keywords = list(dict.fromkeys(KEYWORDS + (ship_names or [])))
        self._on_final = on_final  # (확정 문장, 가장 낮은 글자 확신도 0~1) — 범위 밖 판정 때 '잘못 들음' 구분용
        self._on_speech = on_speech  # True=말 시작, False=그 말의 받아쓰기 확정. 말하는 중엔 답을 미루려고
        self.clova_ok = bool(clova_key)
        # STT_RECORD=1 일 때만: 질문 음성을 잘라 저장(STT 비교 시험용, 10/11). 본인 목소리 시험에만 켜고 끝나면 지운다.
        self._rec_dir = record_dir / time.strftime("%Y%m%d-%H%M%S") if record_dir else None
        self._pcm16k = bytearray()
        self._spans: dict[str, list[int]] = {}
        self._n = 0

    # --- 설정 ---
    def _openai_session(self) -> dict:
        # 확신도(logprobs)는 확정 메시지에 같이 와서 지연이 늘지 않는다(10/11 실측: 켬·끔 모두 말 끝→확정 0.57초).
        return {"type": "session.update", "session": {"type": "transcription",
            "include": ["item.input_audio_transcription.logprobs"], "audio": {"input": {
            "format": {"type": "audio/pcm", "rate": 24000},
            # 힌트(prompt)는 넣지 않는다: 알아듣기 어려운 음성에서 힌트 문장을 그대로 받아쓰기로 내뱉었다(10/11 실통화 2회).
            # 이 연결은 말 시작 감지와 CLOVA 실패 때 대비책이라 힌트가 없어도 된다.
            "transcription": {"model": "gpt-4o-mini-transcribe", "language": "ko"},
            # 말 끝 판정: interview_bridge 는 긴 면접 답변이라 2.4초 침묵을 기다렸다. 전화 질문은 짧아 0.8초.
            "turn_detection": {"type": "server_vad", "threshold": 0.5, "prefix_padding_ms": 300,
                               "silence_duration_ms": self._silence_ms},
            "noise_reduction": {"type": "near_field"}}}}}

    def _clova_config(self) -> dict:
        return clova_config(self._keywords, self._silence_ms)

    # --- 녹음(비교 시험용) ---
    def _save_clip(self, item_id: str, text: str, conf: float | None, avg: float | None, low: int) -> None:
        span = self._spans.pop(item_id, None)
        if not (self._rec_dir and span and len(span) == 2):
            return
        a = max(0, (span[0] - 200) * 32)          # 16kHz·2바이트 = ms당 32바이트, 앞뒤 0.2초 여유
        b = min(len(self._pcm16k), (span[1] + 200) * 32)
        self._rec_dir.mkdir(parents=True, exist_ok=True)
        self._n += 1
        name = f"{self._n:02d}.wav"
        with wave.open(str(self._rec_dir / name), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(bytes(self._pcm16k[a:b]))
        with open(self._rec_dir / "manifest.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"file": name, "openai": text, "min": conf, "avg": avg, "low": low}, ensure_ascii=False) + "\n")

    # --- 확정 문장 하나를 파이프라인으로 ---
    def _final(self, out: asyncio.Queue, text: str, conf: float | None, src: str) -> None:
        if self._on_speech:
            self._on_speech(False)  # '말 끝'이 아니라 확정에서 대기를 푼다(쿠션이 먼저 나갔다 끊기는 일 방지)
        if not text:
            return
        bare = re.sub(r"[\s.,!?~]", "", text)
        if len(bare) <= 1 and bare not in BACKCHANNEL_1:
            log.info("한 글자 받아쓰기 무시(%s): %r", src, text)
            return
        fixed = fix_text(text)
        if fixed != text:
            log.info("받아쓰기 바로잡음: %r → %r", text[:60], fixed[:60])
            text = fixed
        log.info("받아쓰기 확정(%s): %r 최저 확신도 %s", src, text[:60], f"{conf:.2f}" if conf is not None else "-")
        if self._on_final:
            self._on_final(text, conf)
        out.put_nowait(SpeechEvent(type="final", transcript=text))

    async def transcribe(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[SpeechEvent]:
        out: asyncio.Queue = asyncio.Queue()
        clova_in: asyncio.Queue = asyncio.Queue()
        async with websockets.connect(URL, additional_headers={"Authorization": f"Bearer {self._key}"},
                                      max_size=None) as ws:
            await ws.send(json.dumps(self._openai_session()))

            async def pump() -> None:
                buf = bytearray()
                async for pcm16k in audio_stream:
                    if self._rec_dir:
                        self._pcm16k += pcm16k
                    if self.clova_ok:
                        buf += pcm16k
                        if len(buf) >= CLOVA_CHUNK:
                            clova_in.put_nowait(bytes(buf)); buf.clear()
                    pcm24k = resample_pcm16(pcm16k, from_rate=16000, to_rate=24000)
                    await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                              "audio": base64.b64encode(pcm24k).decode("ascii")}))
                clova_in.put_nowait(None)
                out.put_nowait(None)

            async def openai_rx() -> None:
                async for raw in ws:
                    m = json.loads(raw)
                    t = m.get("type", "")
                    if t == "input_audio_buffer.speech_started":
                        if self._rec_dir:
                            self._spans[m.get("item_id", "")] = [int(m.get("audio_start_ms", 0))]
                        if self._on_speech:
                            self._on_speech(True)
                        out.put_nowait(SpeechEvent(type="interim", transcript=""))
                    elif t == "input_audio_buffer.speech_stopped" and self._rec_dir:
                        self._spans.setdefault(m.get("item_id", ""), [0]).append(int(m.get("audio_end_ms", 0)))
                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = (m.get("transcript") or "").strip()
                        lps = [x.get("logprob") for x in (m.get("logprobs") or []) if x.get("logprob") is not None]
                        conf = math.exp(min(lps)) if lps else None
                        if lps and text:
                            ps = [math.exp(x) for x in lps]
                            self._save_clip(m.get("item_id", ""), text, conf, sum(ps) / len(ps), sum(p < 0.5 for p in ps))
                        if not self.clova_ok:
                            self._final(out, text, conf, "OpenAI")
                        elif not text and self._on_speech:
                            self._on_speech(False)  # 소음이라 문장이 없으면 '말하는 중'을 풀어 둔다
                        else:
                            log.info("받아쓰기 참고(OpenAI): %r", text[:60])
                    elif t == "error":
                        log.warning("OpenAI 받아쓰기 오류: %s", (m.get("error") or {}).get("message", "")[:200])

            async def clova_rx() -> None:
                import grpc
                from .nest import nest_pb2, nest_pb2_grpc

                async def reqs():
                    yield nest_pb2.NestRequest(type=nest_pb2.CONFIG,
                                               config=nest_pb2.NestConfig(config=json.dumps(self._clova_config())))
                    seq = 0
                    while True:
                        chunk = await clova_in.get()
                        seq += 1
                        last = chunk is None
                        yield nest_pb2.NestRequest(type=nest_pb2.DATA, data=nest_pb2.NestData(
                            chunk=b"" if last else chunk, extra_contents=json.dumps({"seqId": seq, "epFlag": last})))
                        if last:
                            return

                ch = grpc.aio.secure_channel(CLOVA_ADDR, grpc.ssl_channel_credentials())
                try:
                    stub = nest_pb2_grpc.NestServiceStub(ch)
                    async for r in stub.recognize(reqs(), metadata=[("authorization", self._clova_key)]):
                        if not r.contents:
                            continue
                        tr = json.loads(r.contents).get("transcription") or {}
                        text = (tr.get("text") or "").strip()
                        if text:
                            self._final(out, text, _clova_conf(tr), "CLOVA")
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # 키 오류·동시 연결 한도·네트워크. 통화는 OpenAI 받아쓰기로 이어 간다
                    self.clova_ok = False
                    log.warning("CLOVA 받아쓰기 실패, OpenAI 받아쓰기로 전환: %s", getattr(e, "details", lambda: type(e).__name__)())
                finally:
                    await ch.close()

            tasks = [asyncio.create_task(pump()), asyncio.create_task(openai_rx())]
            if self.clova_ok:
                tasks.append(asyncio.create_task(clova_rx()))
            try:
                while True:
                    ev = await out.get()
                    if ev is None:
                        break
                    yield ev
            finally:
                for t in tasks:
                    t.cancel()


# 이전 이름(테스트·문서 호환)
OpenAITranscribeSTT = PhoneSTT
