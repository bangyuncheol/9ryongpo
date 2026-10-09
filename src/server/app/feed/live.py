"""실제 E-UM 선박 위치(S03_007) → ships_pos 와 같은 형식(설계 §5.5 FEED=live)."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..eum import EumClient
from .clock import KST, real_now

STALE_AFTER = timedelta(hours=24)


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
    except ValueError:
        return None


def to_rows(items: list[dict]) -> list[dict]:
    """스펙은 lati/long 이지만 실제 응답은 latitude/longitude(10/8 확인). 둘 다 받는다."""
    out = []
    for p in items:
        lat = p.get("latitude", p.get("lati"))
        lon = p.get("longitude", p.get("long"))
        rcv = _parse(p.get("rcvDateTime") or p.get("logDateTime"))
        if lat is None or lon is None or p.get("devId") is None or rcv is None:
            continue
        out.append({"ship_id": int(p["devId"]), "ts": rcv.isoformat(timespec="seconds"),
                    "lat": float(lat), "lon": float(lon), "course": p.get("course"),
                    "speed": p.get("speed"), "rcv_ts": rcv.isoformat(timespec="seconds"), "source": "live"})
    return out


def freshness(rows: list[dict], now: datetime | None = None) -> dict:
    """화면 배지용. 가장 최근 수신이 24시간보다 오래되면 미갱신."""
    now = now or real_now()
    latest = max((datetime.fromisoformat(r["rcv_ts"]) for r in rows), default=None)
    return {"latest": latest.isoformat(timespec="seconds") if latest else None,
            "stale": latest is None or now - latest > STALE_AFTER}


async def fetch(eum: EumClient) -> list[dict]:
    return to_rows(await eum.positions())
