"""질문창 도구(설계 §4.2). 계산은 전부 여기서 하고 LLM은 결과 숫자를 인용만 한다."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ..collectors.traffic import TrafficService
from ..engine import Engine
from ..eum import EumError
from ..rules import species, visit

log = logging.getLogger(__name__)
SPECIES_CHOICES = ["붉은대게", "살오징어", "골뱅이", "방어", "가자미류", "전체"]

TOOLS: list[dict] = [
    {"type": "function", "name": "get_arrival_forecast",
     "description": "지금(가상 시계) 구룡포 위판장으로 들어오는 중인 배와 이미 들어온 배. 배마다 이름·어업종류·톤수·남은 거리·도착 예정 시각(ETA)·신뢰도.",
     "parameters": {"type": "object", "properties": {
         "biz": {"type": "string", "description": "어업종류 일부로 거르기. 예: 자망, 채낚기, 통발. 생략하면 전체"},
         "min_gt": {"type": "number", "description": "최소 톤수"}, "max_gt": {"type": "number", "description": "최대 톤수"}},
         "additionalProperties": False}},
    {"type": "function", "name": "get_species_estimate",
     "description": "어종 추정. biz를 주면 그 어업종류가 이 달에 보통 무엇을 잡는지, 생략하면 지금 들어오는 배 전체의 어종 비중. 최근 4년 같은 달 구룡포 위판 실적 기준이며 확률이다.",
     "parameters": {"type": "object", "properties": {"biz": {"type": "string", "description": "어업종류. 예: 연안자망어업"}},
                    "additionalProperties": False}},
    {"type": "function", "name": "get_traffic_now",
     "description": "위판장 80m 앞 교통센서3의 실측 교통량(최근 9시간 트럭·전체)과 혼잡율 비교. 실제 현재 시각 기준이며 미래 예측이 아니다.",
     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"type": "function", "name": "recommend_visit_time",
     "description": "경매 시각과 지금 위판장 앞 실측 교통으로 방문 권장 문구. visitor=true면 관광객(경매 참여 불가)용.",
     "parameters": {"type": "object", "properties": {
         "auction_time": {"type": "string", "description": "HH:MM. 기본 09:00(대게·홍게), 잡어·문어는 07:00"},
         "visitor": {"type": "boolean"}}, "additionalProperties": False}},
    {"type": "function", "name": "get_past_auction",
     "description": "과거 구룡포수협 본소 경매 실적(그 달 kg당 평균 경매가=금액÷중량, 물량, 거래일수). '그때 얼마였나'에만 쓴다. 오늘·내일 가격 예측에 쓰지 않는다. 경매가는 도매가다.",
     "parameters": {"type": "object", "properties": {
         "species": {"type": "string", "description": "어종. 예: 붉은대게, 살오징어"},
         "year": {"type": "integer"}, "month": {"type": "integer"}},
         "required": ["species"], "additionalProperties": False}},
    {"type": "function", "name": "subscribe",
     "description": "사용자가 특정 어종이 들어오면 알림을 받고 싶어 할 때. 화면의 알림 받기 버튼을 그 어종으로 준비시킨다(브라우저 권한은 사용자가 직접 누른다).",
     "parameters": {"type": "object", "properties": {"species": {"type": "string", "enum": SPECIES_CHOICES}},
                    "required": ["species"], "additionalProperties": False}},
]


@dataclass
class ToolContext:
    engine: Engine
    traffic: TrafficService


async def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict:
    """도구 실행. 실패해도 예외 대신 {'error': 한국어 설명}을 돌려 LLM이 사용자에게 설명하게 한다."""
    try:
        if name == "get_arrival_forecast":
            today = await ctx.engine.today()
            def keep(a: dict) -> bool:
                if args.get("biz") and args["biz"] not in (a.get("biz") or ""):
                    return False
                gt = a.get("gt") or 0
                return (args.get("min_gt") is None or gt >= args["min_gt"]) and (args.get("max_gt") is None or gt <= args["max_gt"])
            slim = lambda a: {k: a.get(k) for k in ("name", "biz", "gt", "d_km", "eta", "confidence", "status")}
            out = {"now": today["clock"]["now"],
                   "arriving": [slim(a) for a in today["arriving"] if keep(a)],
                   "arrived": [slim(a) for a in today["arrived"] if keep(a)]}
            if today.get("notice"):  # 실데이터가 멈춰 예보를 못 낼 때만 알린다
                out["notice"] = today["notice"]
            return out
        if name == "get_species_estimate":
            month = ctx.engine.clock.now().month
            if args.get("biz"):
                d = species.biz_distribution(ctx.engine.conn, args["biz"], month)
                if d.get("category_only"):
                    d["note"] = "해마다 1위 어종이 바뀌는 업종이라 특정 어종을 싣고 온다고 말하지 않는다."
                return d
            est = (await ctx.engine.today())["species"]
            if est.get("category_only_biz"):
                est["note"] = f"{', '.join(est['category_only_biz'])}은 해마다 어종이 달라 비율에서 뺐다. 이 업종 배의 어종은 말하지 않는다."
            return est
        if name == "get_traffic_now":
            t = await ctx.traffic.now()
            return {k: t.get(k) for k in ("last_hour", "vs_yesterday", "vs_day", "fetched_at", "stale")} | {"hours": t["hours"][-4:]}
        if name == "recommend_visit_time":
            try:
                t = await ctx.traffic.now()
            except EumError:
                t = None
            return visit.recommend(t, args.get("auction_time") or visit.AUCTION_DEFAULT, bool(args.get("visitor")))
        if name == "get_past_auction":
            return past_auction(ctx.engine.conn, args["species"], args.get("year"), args.get("month"))
        if name == "subscribe":
            sp = args.get("species") if args.get("species") in SPECIES_CHOICES else "전체"
            return {"action": "subscribe", "species": sp, "note": "화면의 알림 받기 버튼을 눌러야 알림이 켜집니다."}
        return {"error": f"모르는 도구입니다: {name}"}
    except EumError:
        return {"error": "디지털트윈 데이터를 지금 불러올 수 없습니다."}
    except Exception:
        log.exception("도구 실행 실패: %s", name)
        return {"error": "이 정보를 지금 계산하지 못했습니다."}


def past_auction(conn, sp: str, year: int | None, month: int | None) -> dict:
    q = "SELECT ym, SUM(amount) a, SUM(weight) w, MAX(days) d FROM auction_stats WHERE place=? AND species=?"
    params: list = [species.MAIN_PLACE, sp]
    if year:
        q += " AND substr(ym,1,4)=?"; params.append(f"{year:04d}")
    if month:
        q += " AND substr(ym,6,2)=?"; params.append(f"{month:02d}")
    rows = conn.execute(q + " GROUP BY ym ORDER BY ym", params).fetchall()
    have = [r[0] for r in conn.execute("SELECT DISTINCT ym FROM auction_stats ORDER BY ym")]
    if not rows:
        return {"species": sp, "records": [], "available_months": have,
                "note": "해당 기간 실적이 서버에 없습니다. 오늘 가격은 예측하지 않습니다."}
    return {"species": sp, "place": "구룡포수협 본소", "unit": "원/kg(금액÷중량, 경매 도매가)",
            "records": [{"ym": r["ym"], "kg_price": round(r["a"] / r["w"]) if r["w"] else None,
                         "tons": round(r["w"] / 1000, 1), "trade_days": r["d"]} for r in rows],
            "note": "과거 실적입니다. 오늘 가격은 예측하지 않습니다."}


def dumps(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)
