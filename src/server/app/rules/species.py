"""어종 추정(설계 §5.2, §1-5). 어업종류 × 같은 달 위판 실적(본소, 연도별 비중 평균). 가격은 내지 않는다(§1-8)."""
from __future__ import annotations

import sqlite3
from collections import defaultdict

MAIN_PLACE = "판매과(1계)"
MIN_SHARE = 0.03  # 3% 미만 어종은 표시하지 않음


def available_months(conn: sqlite3.Connection) -> dict[int, list[str]]:
    out: dict[int, list[str]] = defaultdict(list)
    for (ym,) in conn.execute("SELECT DISTINCT ym FROM auction_stats WHERE place=? ORDER BY ym", (MAIN_PLACE,)):
        out[int(ym[5:7])].append(ym)
    return dict(out)


def nearest_month(month: int, months: dict[int, list[str]]) -> int | None:
    if not months:
        return None
    return min(months, key=lambda m: (min(abs(m - month), 12 - abs(m - month)), m))


def biz_distribution(conn: sqlite3.Connection, biz: str, month: int) -> dict:
    """한 업종의 어종 비중. 연도별 금액 비중을 평균한다(큰 해가 지배하지 않도록)."""
    months = available_months(conn)
    m = month if month in months else nearest_month(month, months)
    if m is None:
        return {"biz": biz, "basis": None, "species": [], "category_only": True}
    yms = months[m]
    per_year: dict[str, dict[str, float]] = {}
    for ym in yms:
        rows = conn.execute("SELECT species, amount FROM auction_stats WHERE place=? AND biz=? AND ym=?",
                            (MAIN_PLACE, biz, ym)).fetchall()
        tot = sum(r["amount"] for r in rows)
        if tot > 0:
            per_year[ym] = {r["species"]: r["amount"] / tot for r in rows}
    if not per_year:
        return {"biz": biz, "basis": {"month": m, "years": []}, "species": [], "category_only": True}
    n = len(per_year)
    avg: dict[str, float] = defaultdict(float)
    for shares in per_year.values():
        for sp, v in shares.items():
            avg[sp] += v / n
    ranked = sorted(((sp, v) for sp, v in avg.items() if v >= MIN_SHARE), key=lambda x: -x[1])
    tops = {max(sh.items(), key=lambda x: x[1])[0] for sh in per_year.values()}
    return {
        "biz": biz,
        "basis": {"month": m, "years": sorted(y[:4] for y in per_year), "same_month": m == month},
        "species": [{"name": sp, "share": round(v, 3)} for sp, v in ranked],
        "category_only": len(tops) > 1 and (ranked[0][1] if ranked else 0) < 0.6,
    }


def estimate(conn: sqlite3.Connection, ships: list[dict], month: int) -> dict:
    """입항 예정 배 묶음 → 업종별 요약 + 톤수 가중 전체 어종 비중."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in ships:
        groups[s.get("biz") or "업종 미상"].append(s)
    by_biz = []
    total_gt = sum((s.get("gt") or 0) for s in ships) or 0.0
    known: list[tuple[float, list[dict]]] = []
    for biz, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        gt = sum((s.get("gt") or 0) for s in members)
        dist = biz_distribution(conn, biz, month)
        by_biz.append({"biz": biz, "count": len(members), "gt": round(gt, 1), **{k: dist[k] for k in ("species", "basis", "category_only")}})
        if not dist["category_only"] and dist["species"]:
            known.append((gt, dist["species"]))
    # 어종을 말할 수 있는 업종끼리만 톤수 가중한다. '범주만' 업종의 톤수가 분모에 들어가면 비율이 희석된다(10/9 화면에서 확인).
    known_gt = sum(g for g, _ in known)
    mix: dict[str, float] = defaultdict(float)
    for gt, sps in known:
        w = gt / known_gt if known_gt else 1 / len(known)
        for sp in sps:
            mix[sp["name"]] += sp["share"] * w
    overall = sorted(({"name": k, "share": round(v, 3)} for k, v in mix.items() if v >= MIN_SHARE), key=lambda x: -x["share"])
    unknown = [b["biz"] for b in by_biz if b["category_only"] or not b["species"]]
    return {"by_biz": by_biz, "overall": overall, "ships": len(ships), "total_gt": round(total_gt, 1),
            "category_only_biz": unknown}
