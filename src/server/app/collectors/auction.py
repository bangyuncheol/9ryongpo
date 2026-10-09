"""해수부 일자별 위탁판매현황 CSV(data/auction/) → auction_stats 테이블.

kg가는 '위판단가(1킬로그램)' 열이 깨져 있어 쓰지 않고 금액÷중량으로 계산한다(설계 §1-8).
"""
from __future__ import annotations

import csv
import logging
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from ..db import tx

log = logging.getLogger(__name__)
MAIN_PLACE = "판매과(1계)"  # 구룡포항 본소
FILE_RE = re.compile(r"_(\d{4}-\d{2})\.csv$")


def aggregate_csv(path: Path) -> list[tuple]:
    m = FILE_RE.search(path.name)
    if not m:
        return []
    ym = m.group(1)
    acc: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, 0, set()])
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                weight = float(r["위판중량"] or 0)
                amount = float(r["위판금액"] or 0)
            except ValueError:
                continue
            if weight <= 0:
                continue
            key = (ym, r["위판장명"], r["업종명"], r["수산물표준코드명"])
            a = acc[key]
            a[0] += amount; a[1] += weight; a[2] += 1; a[3].add(r["위판일자"])
    return [(*k, v[0], v[1], v[2], len(v[3])) for k, v in acc.items()]


def load_dir(conn: sqlite3.Connection, auction_dir: Path) -> int:
    files = sorted(auction_dir.glob("*.csv"))
    if not files:
        log.warning("위판 실적 CSV가 없습니다: %s", auction_dir)
        return 0
    n = 0
    with tx(conn):
        for p in files:
            rows = aggregate_csv(p)
            conn.executemany(
                """INSERT OR REPLACE INTO auction_stats
                   (ym, place, biz, species, amount, weight, rows, days) VALUES (?,?,?,?,?,?,?,?)""",
                rows,
            )
            n += len(rows)
    log.info("auction_stats %d행 적재 (%d개 파일)", n, len(files))
    return n
