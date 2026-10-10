"""전화 말하기 부품: Gemini TTS + 문장별 음성 저장(설계 §4.3).

- Gemini 키는 하루 100회 한도라, 한 번 만든 문장은 `data/tts_cache/` 에 PCM 으로 저장해 다시 쓴다.
  (interview_bridge 가 쿠션·고정 발화 음성을 미리 빌드해 두는 방식과 같다.)
- 파이프라인은 답 한 덩어리를 한 조각으로 넘긴다(물어보기 엔진이 답 전체를 한 번에 내므로) → 답 1개 = 요청 1회.
- Gemini 가 실패(한도 초과·지연)하면 그 문장만 OpenAI gpt-4o-mini-tts 로 읽는다. 통화는 끊기지 않는다.
출력은 PCM16 24kHz mono. ClawOps 가 8kHz μ-law 로 바꿔 전화로 보낸다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Callable

import httpx

log = logging.getLogger(__name__)

RATE = 24000
CHUNK = RATE * 2 // 5  # 200ms 단위로 내보낸다
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"


class CachedTTS:
    sample_rate = RATE

    def __init__(self, cache_dir: Path, gemini_key: str, gemini_model: str, voice: str,
                 openai_key: str = "", on_spoken: Callable[[str, float], None] | None = None) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._gkey, self._gmodel, self._voice, self._okey = gemini_key, gemini_model, voice, openai_key
        self.on_spoken = on_spoken  # (문장, 음성 길이 초) — 끝인사 뒤 끊기 시점 계산용
        self.stats = {"cache": 0, "gemini": 0, "openai": 0, "fail": 0}

    def _path(self, text: str) -> Path:
        h = hashlib.sha1(f"{self._gmodel}|{self._voice}|{text}".encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{h}.pcm"

    def cached(self, text: str) -> bool:
        return self._path(text.strip()).exists()

    async def synthesize(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async for text in text_stream:
            text = text.strip()
            if not text:
                continue
            total = 0
            async for chunk in self.speak(text):
                total += len(chunk)
                yield chunk
            if self.on_spoken:
                self.on_spoken(text, total / (RATE * 2))

    async def speak(self, text: str) -> AsyncIterator[bytes]:
        path = self._path(text)
        if path.exists():
            self.stats["cache"] += 1
            data = path.read_bytes()
            for i in range(0, len(data), CHUNK):
                yield data[i:i + CHUNK]
            return
        pcm = bytearray()
        try:
            async for chunk in self._gemini(text):
                pcm += chunk
                yield chunk
            self.stats["gemini"] += 1
        except Exception as e:  # 한도 초과(429)·지연·네트워크. 이미 일부를 보냈으면 이어서 읽을 수 없으니 그대로 둔다.
            log.warning("Gemini 음성 합성 실패(%s), OpenAI 음성으로 대신함", type(e).__name__)
            if pcm:
                return
            try:
                async for chunk in self._openai(text):
                    pcm += chunk
                    yield chunk
                self.stats["openai"] += 1
            except Exception as e2:
                self.stats["fail"] += 1
                log.error("음성 합성 모두 실패: %s", type(e2).__name__)
                return
        if pcm:
            path.write_bytes(bytes(pcm))

    async def _gemini(self, text: str) -> AsyncIterator[bytes]:
        if not self._gkey:
            raise RuntimeError("GEMINI_API_KEY 없음")
        body = {"contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"responseModalities": ["AUDIO"],
                                     "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._voice}}}}}
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as c:
            async with c.stream("POST", GEMINI_URL.format(model=self._gmodel), json=body,
                                headers={"x-goog-api-key": self._gkey}) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"Gemini HTTP {r.status_code}")
                buf = b""
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    for part in json.loads(line[5:]).get("candidates", [{}])[0].get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            buf += base64.b64decode(part["inlineData"]["data"])
                            while len(buf) >= CHUNK:
                                yield buf[:CHUNK]
                                buf = buf[CHUNK:]
                if buf:
                    yield buf

    async def _openai(self, text: str) -> AsyncIterator[bytes]:
        if not self._okey:
            raise RuntimeError("OPENAI_API_KEY 없음")
        body = {"model": "gpt-4o-mini-tts", "voice": "marin", "input": text, "response_format": "pcm"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as c:
            async with c.stream("POST", "https://api.openai.com/v1/audio/speech", json=body,
                                headers={"Authorization": f"Bearer {self._okey}"}) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"OpenAI TTS HTTP {r.status_code}")
                async for chunk in r.aiter_bytes(CHUNK):
                    yield chunk
