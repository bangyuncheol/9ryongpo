"""전화 듣기 부품: OpenAI 받아쓰기 전용 실시간 연결(설계 §4.3).

ClawOps 파이프라인이 전화 음성을 PCM16 16kHz 로 넘겨준다. OpenAI 받아쓰기 연결은 24kHz 를 받으므로
올려서 보낸다. 서버 VAD 가 말 시작(→ interim: AI 음성 멈춤)과 말 끝(→ final: 답 생성)을 알려 준다.
일반 Realtime 음성 모델이 아니라 `intent=transcription` 연결이라 받아쓰기 모델 요금만 든다(10/11 실측 확인).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import time
import wave
from pathlib import Path
from typing import AsyncIterator, Callable

import websockets
from clawops.agent._audio import resample_pcm16
from clawops.agent.pipeline import SpeechEvent

log = logging.getLogger(__name__)

URL = "wss://api.openai.com/v1/realtime?intent=transcription"
HINT = "구룡포 위판장, 입항, 자망선, 채낚기, 통발, 붉은대게, 홍게, 대게, 골뱅이, 오징어, 방어, 가자미, 경매, 트럭, 교통"


class OpenAITranscribeSTT:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe", silence_ms: int = 800,
                 on_final: Callable[[str, float | None], None] | None = None,
                 on_speech: Callable[[bool], None] | None = None, record_dir: Path | None = None) -> None:
        self._key, self._model, self._silence_ms = api_key, model, silence_ms
        self._on_final = on_final  # (확정 문장, 가장 낮은 글자 확신도 0~1) — 범위 밖 판정 때 '잘못 들음' 구분용
        self._on_speech = on_speech  # True=말 시작, False=그 말의 받아쓰기 확정. 말하는 중엔 답을 미루려고
        # STT_RECORD=1 일 때만: 질문 음성을 잘라 저장(STT 비교 시험용, 10/11). 본인 목소리 시험에만 켜고 끝나면 지운다.
        self._rec_dir = record_dir / time.strftime("%Y%m%d-%H%M%S") if record_dir else None
        self._pcm16k = bytearray()
        self._spans: dict[str, list[int]] = {}
        self._n = 0

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

    def _session(self) -> dict:
        # 확신도(logprobs)는 확정 메시지에 같이 와서 지연이 늘지 않는다(10/11 실측: 켬·끔 모두 말 끝→확정 0.57초).
        return {"type": "session.update", "session": {"type": "transcription",
            "include": ["item.input_audio_transcription.logprobs"], "audio": {"input": {
            "format": {"type": "audio/pcm", "rate": 24000},
            "transcription": {"model": self._model, "language": "ko", "prompt": HINT},
            # 말 끝 판정: interview_bridge 는 긴 면접 답변이라 2.4초 침묵을 기다렸다. 전화 질문은 짧아 0.8초.
            "turn_detection": {"type": "server_vad", "threshold": 0.5, "prefix_padding_ms": 300,
                               "silence_duration_ms": self._silence_ms},
            "noise_reduction": {"type": "near_field"}}}}}

    async def transcribe(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[SpeechEvent]:
        async with websockets.connect(URL, additional_headers={"Authorization": f"Bearer {self._key}"},
                                      max_size=None) as ws:
            await ws.send(json.dumps(self._session()))

            async def pump() -> None:
                async for pcm16k in audio_stream:
                    if self._rec_dir:
                        self._pcm16k += pcm16k
                    pcm24k = resample_pcm16(pcm16k, from_rate=16000, to_rate=24000)
                    await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                              "audio": base64.b64encode(pcm24k).decode("ascii")}))

            sender = asyncio.create_task(pump())
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    t = m.get("type", "")
                    if t == "input_audio_buffer.speech_started" and self._rec_dir:
                        self._spans[m.get("item_id", "")] = [int(m.get("audio_start_ms", 0))]
                    if t == "input_audio_buffer.speech_stopped" and self._rec_dir:
                        self._spans.setdefault(m.get("item_id", ""), [0]).append(int(m.get("audio_end_ms", 0)))
                    if t == "input_audio_buffer.speech_started":
                        if self._on_speech:
                            self._on_speech(True)
                        yield SpeechEvent(type="interim", transcript="")
                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = (m.get("transcript") or "").strip()
                        # '말 끝'(0.8초 침묵)이 아니라 받아쓰기 확정에서 대기를 푼다. 말 끝과 확정 사이(약 0.6초)에
                        # 앞 응답의 쿠션이 먼저 나갔다가 뒷말 확정으로 끊기는 일을 막는다(10/11).
                        if self._on_speech:
                            self._on_speech(False)
                        lps = [x.get("logprob") for x in (m.get("logprobs") or []) if x.get("logprob") is not None]
                        conf = math.exp(min(lps)) if lps else None
                        if text:
                            # 판정에는 최저값만 쓴다. 평균·낮은 글자 수는 실통화로 기준을 다시 맞추려고 남긴다(10/11).
                            if lps:
                                ps = [math.exp(x) for x in lps]
                                self._save_clip(m.get("item_id", ""), text, conf, sum(ps) / len(ps), sum(p < 0.5 for p in ps))
                                log.info("받아쓰기 확정: %r 최저 확신도 %.2f 평균 %.2f 낮은 글자(0.5 미만) %d/%d",
                                         text[:60], conf, sum(ps) / len(ps), sum(p < 0.5 for p in ps), len(ps))
                            else:
                                log.info("받아쓰기 확정: %r 확신도 없음", text[:60])
                            if self._on_final:
                                self._on_final(text, conf)
                            yield SpeechEvent(type="final", transcript=text)
                    elif t == "error":
                        log.warning("받아쓰기 오류: %s", (m.get("error") or {}).get("message", "")[:200])
                    if sender.done():
                        break
            finally:
                sender.cancel()
