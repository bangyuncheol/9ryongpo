"""위판장 앞 교통 현황 → 권장 문구(설계 §5.4). 실측 지금 상황과 경매 시각으로만 만든다. 미래 혼잡을 단정하지 않는다."""
from __future__ import annotations

from datetime import datetime, timedelta

# 경매 시작 06:00 고정(10/11 오너 결정). 9시면 배가 닿은 뒤 전화로 물어봐도 충분해 새벽 예보가 쓸모없어진다.
# 대본상 04:25~04:35 정박 → 05:30 도착 권장까지 내리고 고를 시간 1시간. 실제 위판장 시각은 수협 확인 전 가정
AUCTION_DEFAULT = "06:00"
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
        # 관광객도 경매를 구경하러 올 수 있다. 참여 여부·종료 시각·혼잡을 단정하지 않고 시작 시각만 알린다(10/10).
        lines.append(f"경매는 {at:%H:%M}에 시작합니다.")
    else:
        lines.append(f"경매 {at:%H:%M} 기준 {arrive_by}까지 도착을 권합니다.")
    return {"auction_time": at.strftime("%H:%M"), "arrive_by": arrive_by,
            "now": now_txt, "last_hour": last, "advice": " ".join(lines),
            "basis": "위판장 80m 앞 E-UM 교통센서3 실측(실제 현재 시각). 미래 혼잡 예측 아님"}
