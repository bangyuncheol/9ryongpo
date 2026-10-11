"""알림 문장(설계 §5.3). 숫자는 룰 결과를 그대로 쓴다. LLM 문장은 이후 단계에서 덧붙이고, 실패하면 이 템플릿을 쓴다."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from typing import Any

from .visit import AUCTION_DEFAULT

log = logging.getLogger(__name__)


def short_biz(biz: str | None) -> str:
    if not biz:
        return "배"
    b = biz.removesuffix("어업")
    for p in ("연안", "근해", "동해구"):
        b = b.removeprefix(p)
    return b


def template(new: list[dict], est: dict) -> tuple[str, str]:
    """(제목, 본문). 예: '04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이. 경매 06:00'"""
    etas = sorted(a["eta"][11:16] for a in new if a.get("eta"))
    when = (etas[0] if etas[0] == etas[-1] else f"{etas[0]}~{etas[-1]}") if etas else "곧"
    kinds = Counter(short_biz(a.get("biz")) for a in new)
    ships = ", ".join(f"{k}선 {v}척" for k, v in kinds.most_common())
    species = "·".join(s["name"] for s in est.get("overall", [])[:2])
    body = f"{when} {ships} 입항 예정"
    if species:
        body += f" · {species} 가능성"
    body += f". 경매 {AUCTION_DEFAULT}"  # '(기본값)'은 사용자에게 필요 없는 표시라 뺌(10/10)
    return "배마중 · 구룡포 입항 예보", body


def matches(cond: dict, est: dict) -> bool:
    """구독 조건: {'species': None} 이면 모든 입항, {'species': ['붉은대게', '살오징어']} 면 그중 하나라도 비중 20% 이상.
    옛 형식 {'species': '붉은대게'}(문자열)도 같은 뜻으로 읽는다(10/12). 여럿이 맞아도 알림은 입항 한 번에 한 번."""
    want = cond.get("species")
    if not want:
        return True
    if isinstance(want, str):
        want = [want]
    return any(s["name"] in want and s["share"] >= 0.2 for s in est.get("overall", []))


NUM_RE = re.compile(r"\d+(?::\d+)?")
POLISH_PROMPT = """아래 입항 알림 문장을 횟집 사장이 잠금 화면에서 한눈에 읽게 다듬어라.
- 한 문장, 70자 이내, 존댓말 없이 간결하게.
- 숫자·시각·어종·'가능성'을 하나도 바꾸거나 빼거나 더하지 마라. '기본값'이라는 말은 넣지 마라.
- 다듬은 문장만 출력하라."""


def numbers(text: str) -> list[str]:
    return sorted(NUM_RE.findall(text))


def accept(template_body: str, candidate: str) -> bool:
    """LLM 문장이 템플릿의 숫자를 정확히 같은 집합으로 담고, 길이·어종이 지켜졌을 때만 쓴다."""
    c = candidate.strip()
    if not c or len(c) > 90 or "\n" in c or "기본값" in c:
        return False
    if numbers(c) != numbers(template_body):
        return False
    return "가능성" in c if "가능성" in template_body else True


async def polish(client: Any, model: str, template_body: str, timeout_s: float = 8.0) -> tuple[str, str]:
    """(본문, 'llm'|'template'). 실패·검증 탈락이면 템플릿 그대로."""
    if client is None:
        return template_body, "template"
    from ..agent import chat  # 크레딧 소진 쿨다운을 질문창과 공유
    import time
    if time.monotonic() < chat._cooldown_until:
        return template_body, "template"
    try:
        r = await asyncio.wait_for(client.responses.create(
            model=model, reasoning={"effort": "low"}, max_output_tokens=300,
            input=[{"role": "system", "content": POLISH_PROMPT}, {"role": "user", "content": template_body}]), timeout_s)
        out = (r.output_text or "").strip().strip('"')
    except Exception as e:
        log.warning("알림 문장 다듬기 실패, 템플릿 사용: %s", type(e).__name__)
        if type(e).__name__ in ("RateLimitError", "AuthenticationError", "PermissionDeniedError"):
            chat._cooldown_until = time.monotonic() + chat.COOLDOWN_S
        return template_body, "template"
    if accept(template_body, out):
        return out, "llm"
    log.info("알림 문장 검증 탈락(숫자·길이), 템플릿 사용: %r", out[:100])
    return template_body, "template"
