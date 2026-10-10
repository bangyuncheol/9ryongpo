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
from typing import AsyncIterator

import websockets
from clawops.agent._audio import resample_pcm16
from clawops.agent.pipeline import SpeechEvent

log = logging.getLogger(__name__)

URL = "wss://api.openai.com/v1/realtime?intent=transcription"
HINT = "구룡포 위판장, 입항, 자망선, 채낚기, 통발, 붉은대게, 홍게, 대게, 골뱅이, 오징어, 방어, 가자미, 경매, 트럭, 교통"


class OpenAITranscribeSTT:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe", silence_ms: int = 800) -> None:
        self._key, self._model, self._silence_ms = api_key, model, silence_ms

    def _session(self) -> dict:
        return {"type": "session.update", "session": {"type": "transcription", "audio": {"input": {
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
                    pcm24k = resample_pcm16(pcm16k, from_rate=16000, to_rate=24000)
                    await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                              "audio": base64.b64encode(pcm24k).decode("ascii")}))

            sender = asyncio.create_task(pump())
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    t = m.get("type", "")
                    if t == "input_audio_buffer.speech_started":
                        yield SpeechEvent(type="interim", transcript="")
                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = (m.get("transcript") or "").strip()
                        if text:
                            yield SpeechEvent(type="final", transcript=text)
                    elif t == "error":
                        log.warning("받아쓰기 오류: %s", (m.get("error") or {}).get("message", "")[:200])
                    if sender.done():
                        break
            finally:
                sender.cancel()
