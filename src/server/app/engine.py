"""시계·피드·룰을 묶는 엔진. 화면 API와 10분(가상) 틱이 같은 계산을 쓴다."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from .db import tx
from .eum import EumClient, EumError
from .feed import live as live_feed
from .feed.clock import VirtualClock, real_now
from .feed.sim import Simulator
from .rules import arrival, species

log = logging.getLogger(__name__)
TICK = timedelta(minutes=10)
LIVE_REFRESH = timedelta(minutes=10)

NewArrivalHook = Callable[[datetime, list[dict]], Awaitable[None]]


def floor_tick(t: datetime) -> datetime:
    return t.replace(minute=t.minute - t.minute % 10, second=0, microsecond=0)


class Engine:
    def __init__(self, conn: sqlite3.Connection, eum: EumClient, place: tuple[float, float], feed: str):
        self.conn, self.eum, self.place = conn, eum, place
        self.feed = feed
        self.clock = VirtualClock(mode=feed)
        self.sim = Simulator(place)
        self.fleet: dict[int, dict] = {}
        self._live_rows: list[dict] = []
        self._live_prev: list[dict] = []
        self._live_at: datetime | None = None
        self._last_tick: datetime | None = None
        self._announced: set[int] = set()
        self.hooks: list[NewArrivalHook] = []

    # --- 데이터 ---
    def reload_fleet(self) -> None:
        rows = self.conn.execute("SELECT ship_id, name, biz, gt FROM fleet").fetchall()
        self.fleet = {r["ship_id"]: dict(r) for r in rows}

    async def _refresh_live(self, force: bool = False) -> None:
        now = real_now()
        if not force and self._live_at and now - self._live_at < LIVE_REFRESH:
            return
        try:
            rows = await live_feed.fetch(self.eum)
        except EumError as e:
            log.warning("선박 위치(live) 조회 실패, 이전 값 유지: %s", e)
            return
        self._live_prev, self._live_rows, self._live_at = self._live_rows, rows, now

    async def snapshots(self, t: datetime) -> tuple[list[dict], list[dict]]:
        """(지금, 10분 전) 위치."""
        if self.feed == "sim":
            return self.sim.snapshot(t), self.sim.snapshot(t - TICK)
        await self._refresh_live()
        return self._live_rows, self._live_prev

    def source_badge(self) -> dict:
        if self.feed == "sim":
            return {"feed": "sim", "label": "시뮬레이션", "stale": False, "latest": None}
        f = live_feed.freshness(self._live_rows)
        return {"feed": "live", "label": "실시간" if not f["stale"] else "미갱신", **f}

    # --- 화면용 ---
    async def today(self) -> dict:
        t = self.clock.now()
        cur, prev = await self.snapshots(t)
        judged = arrival.judge(cur, prev, self.fleet, t, self.place)
        est = species.estimate(self.conn, judged["arriving"], t.month)
        return {"clock": self.clock.state(), "source": self.source_badge(), **judged, "species": est}

    async def ships(self) -> dict:
        t = self.clock.now()
        cur, prev = await self.snapshots(t)
        judged = arrival.judge(cur, prev, self.fleet, t, self.place)
        status = {s["ship_id"]: s["status"] for s in judged["arriving"] + judged["arrived"]}
        out = []
        for p in cur:
            info = self.fleet.get(p["ship_id"], {})
            out.append({"ship_id": p["ship_id"], "name": info.get("name"), "biz": info.get("biz"), "gt": info.get("gt"),
                        "lat": p["lat"], "lon": p["lon"], "course": p.get("course"), "speed": p.get("speed"),
                        "status": status.get(p["ship_id"], "조업·대기")})
        return {"clock": self.clock.state(), "source": self.source_badge(), "ships": out}

    # --- 제어 ---
    def set_feed(self, feed: str) -> None:
        if feed not in ("sim", "live"):
            raise ValueError("데이터 소스는 sim 또는 live 입니다.")
        self.feed = feed
        self.clock.mode = feed
        self.reset_tick()

    def reset_tick(self) -> None:
        """되감기·소스 전환 시 틱 상태를 지워, 같은 장면에서 푸시가 다시 나가게 한다."""
        self._last_tick = None
        self._announced.clear()

    # --- 10분(가상) 틱: 기록 + 새로 입항 중이 된 배 알림 ---
    async def tick(self) -> None:
        t = floor_tick(self.clock.now())
        if self._last_tick is not None and t <= self._last_tick:
            if t < self._last_tick:  # 되감김
                self.reset_tick()
            else:
                return
        self._last_tick = t
        cur, prev = await self.snapshots(t)
        judged = arrival.judge(cur, prev, self.fleet, t, self.place)
        ts = t.isoformat(timespec="seconds")
        with tx(self.conn):
            self.conn.executemany(
                """INSERT OR REPLACE INTO ships_pos (ship_id, ts, lat, lon, course, speed, rcv_ts, source)
                   VALUES (:ship_id, :ts, :lat, :lon, :course, :speed, :rcv_ts, :source)""", cur)
            self.conn.execute("DELETE FROM forecast WHERE ts = ?", (ts,))
            self.conn.executemany(
                "INSERT INTO forecast (ts, ship_id, d_km, eta, confidence, species_json) VALUES (?,?,?,?,?,?)",
                [(ts, a["ship_id"], a["d_km"], a["eta"], a["confidence"], None) for a in judged["arriving"]])
        new = [a for a in judged["arriving"] if a["ship_id"] not in self._announced]
        self._announced.update(a["ship_id"] for a in judged["arriving"])
        if new:
            self.log_event("forecast", {"ts": ts, "new": [a["ship_id"] for a in new]})
            for hook in self.hooks:
                try:
                    await hook(t, new)
                except Exception:  # 알림 실패가 틱을 멈추면 안 된다. 기록하고 계속.
                    log.exception("새 입항 알림 처리 실패")

    def log_event(self, kind: str, payload: dict) -> None:
        with tx(self.conn):
            self.conn.execute("INSERT INTO events (ts, kind, payload) VALUES (?,?,?)",
                              (real_now().isoformat(timespec="seconds"), kind, json.dumps(payload, ensure_ascii=False)))
