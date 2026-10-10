"""위판장 앞 교통 현황 → 권장 문구(설계 §5.4). 실측 지금 상황과 경매 시각으로만 만든다. 미래 혼잡을 단정하지 않는다."""
from __future__ import annotations

from datetime import datetime, timedelta

AUCTION_DEFAULT = "09:00"
VISITOR_LINE = "관광객은 경매에 참여할 수 없습니다. 경매({auction}, 기본값)가 끝난 뒤 회센터·시장을 이용하세요."
EARLY_MIN = 30  # 경매 30분 전 도착 권장 — 제품 가정(수협 확인 전), 화면에 '기본값' 표기


def _now_level(traffic: dict | None) -> str | None:
    if not traffic:
        return None
    lvl = traffic.get("vs_yesterday", {}).get("level")
    if lvl and lvl != "비교 불가":
        return {"붐빔": "어제 이맘때보다 붐빕니다", "한산": "어제 이맘때보다 한산합니다", "비슷": "어제 이맘때와 비슷합니다"}[lvl]
    day = traffic.get("vs_day")
    if day and day != "비교 불가":
        return f"오늘 하루 중 {day}입니다"
    return None


def recommend(traffic: dict | None, auction_time: str = AUCTION_DEFAULT, visitor: bool = False) -> dict:
    try:
        at = datetime.strptime(auction_time, "%H:%M")
    except ValueError:
        at = datetime.strptime(AUCTION_DEFAULT, "%H:%M")
    arrive_by = (at - timedelta(minutes=EARLY_MIN)).strftime("%H:%M")
    last = (traffic or {}).get("last_hour")
    now_txt = _now_level(traffic)
    lines = []
    if last:
        lines.append(f"지금 위판장 앞 지난 1시간 트럭 {last['truck']}대, 전체 {last['total']}대" + (f"로 {now_txt}" if now_txt else "입니다") + ".")
    if visitor:
        # 경매 종료 시각은 확인되지 않았고, 경매 뒤 덜 붐빈다는 근거도 없다(10/10 그래프에서 11~13시가 더 많음). 시각·혼잡을 단정하지 않는다.
        lines.append(VISITOR_LINE.format(auction=at.strftime("%H:%M")))
    else:
        lines.append(f"경매 {at:%H:%M}(기본값) 기준 {arrive_by}까지 도착을 권합니다.")
    return {"auction_time": at.strftime("%H:%M"), "arrive_by": arrive_by,
            "visitor_line": VISITOR_LINE.format(auction=at.strftime("%H:%M")),
            "now": now_txt, "last_hour": last, "advice": " ".join(lines),
            "basis": "위판장 80m 앞 E-UM 교통센서3 실측(실제 현재 시각). 미래 혼잡 예측 아님"}
