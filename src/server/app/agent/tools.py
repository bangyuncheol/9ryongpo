"""질문창 도구(설계 §4.2). 계산은 전부 여기서 하고 LLM은 결과 숫자를 인용만 한다."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ..collectors.traffic import TrafficService
from ..engine import Engine
from ..eum import EumError
from ..kakao import KakaoClient
from ..rules import species, travel, visit

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
     "description": "어종 추정. biz를 주면 지금 들어오는 그 업종 배들 기준(입항 알림과 같은 계산), 그런 배가 없으면 그 업종이 이 달에 보통 무엇을 잡는지. 생략하면 지금 들어오는 배 전체. 최근 4년 같은 달 구룡포 위판 실적 기준이며 확률이다.",
     "parameters": {"type": "object", "properties": {"biz": {"type": "string", "description": "어업종류. '자망', '연안자망', '채낚기'처럼 줄여도 된다"}},
                    "additionalProperties": False}},
    {"type": "function", "name": "get_traffic_now",
     "description": "위판장 80m 앞 교통센서3의 실측 교통량(최근 9시간 트럭·전체)과 혼잡율 비교. 실제 현재 시각 기준이며 미래 예측이 아니다.",
     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"type": "function", "name": "recommend_visit_time",
     "description": "경매 시각과 지금 위판장 앞 실측 교통으로 방문 권장 문구. visitor=true는 질문한 사람이 스스로 관광·구경이라고 밝혔을 때만 쓴다(그때는 경매 시작 시각만 알린다).",
     "parameters": {"type": "object", "properties": {
         "auction_time": {"type": "string", "description": "HH:MM. 기본 06:00"},
         "visitor": {"type": "boolean"}}, "additionalProperties": False}},
    {"type": "function", "name": "estimate_travel",
     "description": "다른 곳에서 구룡포 위판장까지 차로 걸리는 시간과 출발 권장 시각. 카카오 길찾기(지금 도로 상황 또는 그 시각 예측 교통) + 위판장 앞 여유. "
                    "'OO에서 몇 시에 출발하면 돼?'는 depart_time 없이(경매 도착 권장 시각에 맞춘 depart_by) — 문장에 '지금 OO에서 출발하는데'처럼 '지금'이 있어도 출발 시각을 묻는 질문이면 생략한다. "
                    "'지금 출발하면 얼마나 걸려?'처럼 걸리는 시간만 물을 때만 depart_time='지금', '8시에 출발하면 언제 도착해?'는 depart_time='08:00'. "
                    "한 질문에 한 번만 부른다. 출발지를 모르면 부르지 말고 어디서 출발하는지 먼저 묻는다.",
     "parameters": {"type": "object", "properties": {
         "origin": {"type": "string", "description": "출발지 이름 그대로. 예: 포항과학기술고등학교, 포항시청, 구룡포읍사무소"},
         "depart_time": {"type": "string", "description": "'지금' 또는 HH:MM. 생략하면 경매에 맞춰 출발 시각을 계산"},
         "auction_time": {"type": "string", "description": "HH:MM. 기본 06:00"}},
         "required": ["origin"], "additionalProperties": False}},
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
    kakao: KakaoClient | None = None  # 출발지 → 위판장 길찾기(10/11). 없으면 그 도구만 '설정 없음'으로 답한다


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
                return await species_for_biz(ctx, args["biz"], month)
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
        if name == "estimate_travel":
            try:
                t = await ctx.traffic.now()
            except EumError:
                t = None
            lat, lon = ctx.engine.place
            return await travel.estimate(ctx.kakao, (lon, lat), args.get("origin", ""), t,
                                         args.get("auction_time") or visit.AUCTION_DEFAULT, args.get("depart_time"))
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


def _biz_key(raw: str) -> str:
    """'자망선'·'연안자망 배'·'근해채낚기어업' → '자망'·'연안자망'·'근해채낚기'."""
    k = raw.replace(" ", "")
    for suf in ("어업", "선", "배"):
        k = k.removesuffix(suf)
    return k


async def species_for_biz(ctx: ToolContext, raw: str, month: int) -> dict:
    """업종을 지정한 어종 질문. 알림과 답이 어긋나지 않게, 지금 들어오는 그 업종 배가 있으면 알림과 같은
    계산(species.estimate, 톤수 가중)을 쓴다. 실통화(10/11): 알림은 '붉은대게·골뱅이', "자망선 뭐 싣고?"엔
    업종명 '자망'이 실적 업종명과 안 맞아 '추정 불가'로 답했다."""
    key = _biz_key(raw)
    today = await ctx.engine.today()
    ships = [a for a in today["arriving"] + today["arrived"] if key and key in (a.get("biz") or "")]
    if ships:
        est = species.estimate(ctx.engine.conn, ships, month)
        est["ships_named"] = [a.get("name") for a in ships]
        est["basis_note"] = f"지금 들어오는 {key} 배 {len(ships)}척 기준(입항 알림과 같은 계산)"
        if est.get("category_only_biz"):
            est["note"] = f"{', '.join(est['category_only_biz'])}은 해마다 어종이 달라 비율에서 뺐다. 이 업종 배의 어종은 말하지 않는다."
        return est
    names = [r[0] for r in ctx.engine.conn.execute("SELECT DISTINCT biz FROM fleet WHERE biz IS NOT NULL").fetchall()]
    full = [b for b in names if key and key in b] or [raw]
    out = {"by_biz": []}
    for b in full:
        d = species.biz_distribution(ctx.engine.conn, b, month)
        if d.get("category_only"):
            d["note"] = "해마다 1위 어종이 바뀌는 업종이라 특정 어종을 싣고 온다고 말하지 않는다."
        out["by_biz"].append(d)
    out["basis_note"] = "지금 들어오는 그 업종 배가 없어, 업종의 이 달 보통 어종이다"
    return out


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
