"""웹 푸시(설계 §5.3). 구독 저장, 새 입항 알림 발송, 화면 안 알림함용 기록."""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime

from pywebpush import WebPushException, webpush

from .config import Settings
from .db import tx
from .feed.clock import real_now
from .rules import brief, species

log = logging.getLogger(__name__)
MAIN_SPECIES = ["붉은대게", "살오징어", "골뱅이", "방어", "가자미류"]  # 10월 대표 어종(칩 고정, 10/11 오너)
# 다른 철 생선: 화면에선 접어 두고 펼치면 보인다(10/12 오너). 위판 실적 56개월 금액 상위 중 위 다섯을 뺀 것, 값은 많이 나는 달
OTHER_SEASON = {"꽃게": "12~2월", "청어": "4~6월", "문어": "1~3월", "아귀": "7~8월", "대문어": "6~8월", "삼치": "8~10월"}
ALLOWED_SPECIES = {None, *MAIN_SPECIES, *OTHER_SEASON}


def norm_species(v) -> list[str] | None:
    """구독 조건의 어종 → None(모두) 또는 중복 없는 목록(10/12 여러 개 고르기). 옛 형식 문자열 하나도 받는다.
    cond_json 의 species 는 이 함수를 거친 값만 저장하고, 읽을 때도 이 함수로 옛 문자열을 목록으로 맞춘다."""
    if v is None or v == "" or v == "전체":
        return None
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not v:
        raise ValueError("지원하지 않는 어종입니다. 목록에서 골라 주세요.")
    out: list[str] = []
    for s in v:
        if not isinstance(s, str) or s not in ALLOWED_SPECIES:
            raise ValueError("지원하지 않는 어종입니다. 목록에서 골라 주세요.")
        if s not in out:
            out.append(s)
    return out


class PushConfigError(Exception):
    pass


def save_subscription(conn: sqlite3.Connection, sub: dict, cond: dict) -> int:
    endpoint = sub.get("endpoint")
    keys = sub.get("keys") or {}
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("알림 구독 정보가 올바르지 않습니다. 알림 받기를 다시 눌러 주세요.")
    cond = {**cond, "species": norm_species(cond.get("species"))}
    with tx(conn):
        conn.execute(
            """INSERT INTO subs (endpoint, keys_json, cond_json, created_at) VALUES (?,?,?,?)
               ON CONFLICT(endpoint) DO UPDATE SET keys_json=excluded.keys_json, cond_json=excluded.cond_json""",
            (endpoint, json.dumps(keys), json.dumps(cond, ensure_ascii=False), real_now().isoformat(timespec="seconds")))
    return conn.execute("SELECT id FROM subs WHERE endpoint=?", (endpoint,)).fetchone()[0]


def delete_subscription(conn: sqlite3.Connection, endpoint: str) -> None:
    with tx(conn):
        conn.execute("DELETE FROM subs WHERE endpoint=?", (endpoint,))


class Pusher:
    def __init__(self, conn: sqlite3.Connection, settings: Settings, sender=webpush, llm=None):
        self.conn, self.s, self._send, self.llm = conn, settings, sender, llm
        self.listeners: list = []  # (vt, 본문, 어종 추정) — 전화 알림 등 같은 알림을 다른 경로로 보낼 때

    def _claims(self) -> dict:
        if not (self.s.vapid_private_key and self.s.vapid_subject.startswith(("mailto:", "https://"))):
            raise PushConfigError("VAPID_PRIVATE_KEY 또는 VAPID_SUBJECT(mailto:주소)가 비어 있음")
        return {"sub": self.s.vapid_subject}

    def _send_one(self, row: sqlite3.Row, payload: str) -> str:
        """'ok' | 'gone'(구독 만료) | 'fail'"""
        try:
            self._send(subscription_info={"endpoint": row["endpoint"], "keys": json.loads(row["keys_json"])},
                       data=payload, vapid_private_key=self.s.vapid_private_key, vapid_claims=self._claims(), ttl=3600)
            return "ok"
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):
                return "gone"
            log.warning("푸시 발송 실패(HTTP %s)", code)
            return "fail"

    async def notify(self, vt: datetime, title: str, body: str, est: dict, ship_ids: list[int],
                     everyone: bool = False) -> dict:
        subs = self.conn.execute("SELECT * FROM subs").fetchall()
        targets = subs if everyone else [r for r in subs if brief.matches(json.loads(r["cond_json"]), est)]
        payload = json.dumps({"title": title, "body": body, "url": "/"}, ensure_ascii=False)
        result = {"ok": 0, "gone": 0, "fail": 0, "skipped_config": False}
        if targets:
            try:
                self._claims()
            except PushConfigError as e:
                log.warning("푸시 설정 누락으로 발송 생략: %s", e)
                result["skipped_config"] = True
                targets = []
        for r in targets:
            status = await asyncio.to_thread(self._send_one, r, payload)
            result[status] += 1
            if status == "gone":
                delete_subscription(self.conn, r["endpoint"])
        with tx(self.conn):
            self.conn.execute("INSERT INTO events (ts, kind, payload) VALUES (?,?,?)", (
                real_now().isoformat(timespec="seconds"), "push",
                json.dumps({"vts": vt.isoformat(timespec="minutes"), "title": title, "body": body,
                            "ships": ship_ids, "targets": len(targets), **result}, ensure_ascii=False)))
        log.info("입항 알림 %s: 대상 %d, 결과 %s", vt.strftime("%H:%M"), len(targets), result)
        return result

    async def on_new_arrivals(self, vt: datetime, new: list[dict]) -> None:
        """Engine.tick 훅. 새로 '입항 중'이 된 배 묶음으로 알림 한 건."""
        est = species.estimate(self.conn, new, vt.month)
        title, body = brief.template(new, est)
        body, how = await brief.polish(self.llm, self.s.openai_model, body)
        log.info("알림 문장(%s): %s", how, body)
        await self.notify(vt, title, body, est, [a["ship_id"] for a in new])
        for fn in self.listeners:
            try:
                await fn(vt, body, est)
            except Exception:
                log.exception("알림 후속 처리 실패")


def recent_notifications(conn: sqlite3.Connection, until: datetime, limit: int = 5) -> list[dict]:
    """최근 5건만(화면 상한, 10/10 결정). 오래된 것부터 빠지는 큐."""
    """화면 안 알림함(푸시 지연 대비, 설계 §11). 가상 시각 until 이전 것만, 같은 장면 반복은 하나로."""
    last_reset = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events WHERE kind='reset'").fetchone()[0]
    rows = conn.execute("SELECT payload FROM events WHERE kind='push' AND id > ? ORDER BY id DESC LIMIT 200",
                        (last_reset,)).fetchall()
    seen, out = set(), []
    cut = until.isoformat(timespec="minutes")
    for (p,) in rows:
        d = json.loads(p)
        if d["vts"][:10] != cut[:10] or d["vts"] > cut or (d["vts"], d["body"]) in seen:
            continue
        seen.add((d["vts"], d["body"]))
        out.append({"vts": d["vts"], "title": d["title"], "body": d["body"]})
        if len(out) >= limit:
            break
    return out
