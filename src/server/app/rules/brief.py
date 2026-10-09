"""알림 문장(설계 §5.3). 숫자는 룰 결과를 그대로 쓴다. LLM 문장은 이후 단계에서 덧붙이고, 실패하면 이 템플릿을 쓴다."""
from __future__ import annotations

from collections import Counter

AUCTION_DEFAULT = "09:00"


def short_biz(biz: str | None) -> str:
    if not biz:
        return "배"
    b = biz.removesuffix("어업")
    for p in ("연안", "근해", "동해구"):
        b = b.removeprefix(p)
    return b


def template(new: list[dict], est: dict) -> tuple[str, str]:
    """(제목, 본문). 예: '04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이. 경매 09:00(기본값)'"""
    etas = sorted(a["eta"][11:16] for a in new if a.get("eta"))
    when = (etas[0] if etas[0] == etas[-1] else f"{etas[0]}~{etas[-1]}") if etas else "곧"
    kinds = Counter(short_biz(a.get("biz")) for a in new)
    ships = ", ".join(f"{k}선 {v}척" for k, v in kinds.most_common())
    species = "·".join(s["name"] for s in est.get("overall", [])[:2])
    body = f"{when} {ships} 입항 예정"
    if species:
        body += f" · {species} 가능성"
    body += f". 경매 {AUCTION_DEFAULT}(기본값)"
    return "구룡포 입항 예보", body


def matches(cond: dict, est: dict) -> bool:
    """구독 조건: {'species': None} 이면 모든 입항, {'species': '붉은대게'} 면 그 어종 비중 20% 이상."""
    want = cond.get("species")
    if not want:
        return True
    return any(s["name"] == want and s["share"] >= 0.2 for s in est.get("overall", []))
