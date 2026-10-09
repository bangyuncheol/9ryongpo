"""질문창(설계 §4.2, §1-7). LLM은 도구 결과의 숫자를 인용만 한다.

이벤트(SSE로 화면에 흘림):
  {"type":"tool","name":..,"args":..}         도구 호출 시작
  {"type":"tool_result","name":..,"summary":..} 도구 결과 한 줄
  {"type":"action","name":"subscribe","species":..}
  {"type":"answer","text":..,"mode":"llm"|"simple"}
  {"type":"error","message":..}
LLM 호출이 실패하면(크레딧 소진·지연·네트워크) 낱말 규칙으로 같은 도구를 불러 정해진 문장으로 답한다.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, AsyncIterator

from ..rules.brief import short_biz
from .tools import TOOLS, ToolContext, dumps, run_tool

log = logging.getLogger(__name__)
MAX_ROUNDS = 5
MAX_INPUT = 300
COOLDOWN_S = 300
_cooldown_until = 0.0  # 크레딧 소진·인증 오류 뒤 잠시 LLM을 건너뛴다(질문마다 실패를 기다리지 않도록)

SYSTEM = """너는 '위판 당직'이다. 구룡포 위판장에 생선을 사러 오는 사람(횟집 사장, 관광객)에게 새벽 입항·어종·위판장 앞 교통을 알려 준다.
규칙:
- 숫자(시각, 척수, 톤수, 거리, 비율, 가격, 교통량)는 반드시 도구 결과에서 그대로 인용한다. 계산하거나 지어내지 않는다.
- 어종은 배의 어업 종류로 추정한 '가능성'이다. 근거(예: 최근 4년 10월 구룡포 위판 실적)를 한 번 밝힌다.
- 오늘·내일 가격은 예측하지 않는다. 물으면 과거 실적(get_past_auction)만 말하고, 경매가는 도매가라 소매가와 다르다고 덧붙인다.
- 교통은 실제 현재 시각의 실측이다. 미래 혼잡을 단정하지 않는다.
- 경매 시각 09:00(잡어·문어 07:00)은 기본값이다.
- 모르는 것은 모른다고 말한다. 2~4문장의 짧은 한국어 존댓말로 답한다."""


def _summary(name: str, out: dict) -> str:
    if "error" in out:
        return out["error"]
    if name == "get_arrival_forecast":
        return f"입항 중 {len(out['arriving'])}척, 입항 {len(out['arrived'])}척"
    if name in ("get_species_estimate",):
        sp = out.get("overall") or out.get("species") or []
        return " · ".join(f"{s['name']} {round(s['share'] * 100)}%" for s in sp[:3]) or "추정 불가"
    if name == "get_traffic_now":
        lh = out.get("last_hour") or {}
        return f"지난 1시간 트럭 {lh.get('truck', '?')}대, 전체 {lh.get('total', '?')}대"
    if name == "recommend_visit_time":
        return out.get("advice", "")[:60]
    if name == "get_past_auction":
        return f"{out['species']} 실적 {len(out['records'])}개월"
    if name == "subscribe":
        return f"{out['species']} 알림 준비"
    return "완료"


async def _tool_events(ctx: ToolContext, name: str, args: dict) -> AsyncIterator[tuple[dict, dict]]:
    yield {"type": "tool", "name": name, "args": args}, {}
    out = await run_tool(ctx, name, args)
    yield {"type": "tool_result", "name": name, "summary": _summary(name, out)}, out
    if out.get("action") == "subscribe":
        yield {"type": "action", "name": "subscribe", "species": out["species"]}, {}


async def llm_answer(client: Any, model: str, ctx: ToolContext, question: str) -> AsyncIterator[dict]:
    items: list[Any] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for _ in range(MAX_ROUNDS):
        r = await client.responses.create(model=model, reasoning={"effort": "medium"}, tools=TOOLS,
                                          input=items, max_output_tokens=1200)
        calls = [o for o in r.output if getattr(o, "type", None) == "function_call"]
        if not calls:
            yield {"type": "answer", "text": (r.output_text or "").strip() or "답을 만들지 못했습니다. 다시 물어봐 주세요.", "mode": "llm"}
            return
        items += [o.model_dump(exclude_none=True) if hasattr(o, "model_dump") else o for o in r.output]
        for c in calls:
            try:
                args = json.loads(c.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            out: dict = {}
            async for ev, res in _tool_events(ctx, c.name, args):
                yield ev
                out = res or out
            items.append({"type": "function_call_output", "call_id": c.call_id, "output": dumps(out)})
    yield {"type": "answer", "text": "질문이 복잡해 답을 끝내지 못했습니다. 조금 더 짧게 물어봐 주세요.", "mode": "llm"}


# --- 대비책: 낱말 규칙 ---
TON_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:톤|t)")
SPECIES_WORDS = {"대게": "붉은대게", "홍게": "붉은대게", "붉은대게": "붉은대게", "오징어": "살오징어",
                 "골뱅이": "골뱅이", "방어": "방어", "가자미": "가자미류"}
BIZ_WORDS = ["자망", "채낚기", "통발", "선망", "트롤", "정치망"]


def route(q: str) -> list[tuple[str, dict]]:
    sp = next((v for k, v in SPECIES_WORDS.items() if k in q), None)
    if re.search(r"알려|알림|구독", q):
        return [("subscribe", {"species": sp or "전체"})]
    if re.search(r"얼마|가격|시세|값", q):
        return [("get_past_auction", {"species": sp or "붉은대게", "month": 10})]
    if re.search(r"막히|교통|트럭|붐비|몇 시에 가|언제 가|가면", q):
        return [("recommend_visit_time", {"visitor": bool(re.search(r"관광|구경|회", q))})]
    if sp or re.search(r"뭐가|어종|무슨", q):
        return [("get_arrival_forecast", {}), ("get_species_estimate", {})]
    args: dict = {}
    if (biz := next((b for b in BIZ_WORDS if b in q), None)):
        args["biz"] = biz
    if (m := TON_RE.search(q)):
        g = float(m.group(1)); args.update(min_gt=g - 0.5, max_gt=g + 0.5)
    return [("get_arrival_forecast", args)]


def compose(q: str, results: dict[str, dict]) -> str:
    if (s := results.get("subscribe")):
        return f"{s['species']} 알림을 준비했습니다. 아래 '알려줘' 버튼을 누르면 켜집니다."
    if (p := results.get("get_past_auction")):
        if not p["records"]:
            return "그 기간 경매 실적은 서버에 없습니다. 오늘 가격은 예측하지 않습니다."
        rec = " / ".join(f"{r['ym']} kg당 {r['kg_price']:,}원" for r in p["records"][-4:])
        return f"구룡포수협 본소 {p['species']} 경매 실적은 {rec}입니다. 경매 도매가이며 오늘 가격은 예측하지 않습니다."
    if (v := results.get("recommend_visit_time")):
        return v["advice"]
    f = results.get("get_arrival_forecast")
    if f is None or "error" in f:
        return "지금 정보를 불러오지 못했습니다. 잠시 후 다시 물어봐 주세요."
    want = next((v for k, v in SPECIES_WORDS.items() if k in q), None)
    est = results.get("get_species_estimate") or {}
    if want and est:
        main_biz = {b["biz"] for b in est.get("by_biz", []) if b.get("species") and b["species"][0]["name"] == want and not b.get("category_only")}
        ships = [a for a in f["arriving"] if a.get("biz") in main_biz]
        share = next((x["share"] for x in est.get("overall", []) if x["name"] == want), 0)
        if ships:
            names = ", ".join(f"{a['name']}({short_biz(a['biz'])} {round(a['gt'] or 0)}t, {a['eta'][11:16]} 도착 예정)" for a in ships[:3])
            return f"{want}을(를) 주로 잡는 배가 들어오고 있습니다: {names}. 최근 4년 같은 달 구룡포 실적 기준 가능성입니다."
        tail = f" 지금 들어오는 배 전체로 보면 {want} 가능성은 {round(share * 100)}%입니다." if share else ""
        return f"지금 들어오는 배 중 {want}을(를) 주로 잡는 배는 아직 없습니다.{tail} 조금 뒤 다시 확인해 주세요."
    lines = []
    if f["arriving"]:
        a = f["arriving"][:3]
        lines.append(" ".join(f"{x['name']}({short_biz(x['biz'])} {round(x['gt'] or 0)}t) {x['eta'][11:16]} 도착 예정," for x in a).rstrip(",") + ".")
    elif f["arrived"]:
        lines.append(f"이미 들어온 배가 {len(f['arrived'])}척 있고, 지금 들어오는 중인 배는 없습니다.")
    else:
        lines.append("지금 조건에 맞게 들어오는 배가 없습니다.")
    if (s := results.get("get_species_estimate")) and (sp := s.get("overall")):
        lines.append("어종은 " + "·".join(f"{x['name']} {round(x['share'] * 100)}%" for x in sp[:3]) + " 가능성입니다(최근 4년 같은 달 실적 기준).")
    return " ".join(lines)


async def simple_answer(ctx: ToolContext, question: str) -> AsyncIterator[dict]:
    results: dict[str, dict] = {}
    for name, args in route(question):
        async for ev, res in _tool_events(ctx, name, args):
            yield ev
            if res:
                results[name] = res
    yield {"type": "answer", "text": compose(question, results), "mode": "simple"}


async def answer(client: Any, model: str, ctx: ToolContext, question: str) -> AsyncIterator[dict]:
    q = (question or "").strip()[:MAX_INPUT]
    if not q:
        yield {"type": "error", "message": "질문을 입력해 주세요."}
        return
    global _cooldown_until
    if client is not None and time.monotonic() >= _cooldown_until:
        sent_any = False
        try:
            async for ev in llm_answer(client, model, ctx, q):
                sent_any = True
                yield ev
            return
        except Exception as e:  # 크레딧 소진·지연·네트워크. 기록하고 간단 모드로.
            log.warning("LLM 질문창 실패, 간단 모드로 전환: %s", type(e).__name__)
            if type(e).__name__ in ("RateLimitError", "AuthenticationError", "PermissionDeniedError"):
                _cooldown_until = time.monotonic() + COOLDOWN_S
            if sent_any:
                yield {"type": "tool_result", "name": "llm", "summary": "AI 응답이 끊겨 간단 모드로 답합니다"}
    async for ev in simple_answer(ctx, q):
        yield ev
