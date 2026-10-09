"""어선 명부(E-UM S03_001) → fleet 테이블. 어업종류는 표지판 문자열에서 복원한다."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from ..db import tx

# "0003005-6491102 근해자망어업(43톤)", "… 수하식양식업(4.97톤)", "… 연근해어획물운반업(19톤)"
SIGN_RE = re.compile(r"([가-힣]+업)\((\d+(?:\.\d+)?)톤\)")


def parse_sign(sign: str | None) -> tuple[str | None, float | None]:
    if not sign:
        return None, None
    m = SIGN_RE.search(sign)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def to_row(raw: dict, now_iso: str) -> tuple:
    biz, gt_sign = parse_sign(raw.get("sign"))
    biz = raw.get("type") or biz  # type 은 현재 전부 비어 있음(10/9 확인)
    gt = raw.get("gt") or gt_sign
    return (
        int(raw["id"]), raw.get("shipId"), raw.get("name") or "", biz,
        float(gt) if gt is not None else None, raw.get("sign"),
        json.dumps(raw, ensure_ascii=False), now_iso,
    )


def upsert_fleet(conn: sqlite3.Connection, items: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [to_row(x, now) for x in items if x.get("id") is not None]
    with tx(conn):
        conn.executemany(
            """INSERT INTO fleet (ship_id, reg_no, name, biz, gt, sign, raw_json, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(ship_id) DO UPDATE SET reg_no=excluded.reg_no, name=excluded.name,
                 biz=excluded.biz, gt=excluded.gt, sign=excluded.sign,
                 raw_json=excluded.raw_json, updated_at=excluded.updated_at""",
            rows,
        )
    return len(rows)


def fleet_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM fleet").fetchone()[0]
