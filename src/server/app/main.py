"""위판 당직 FastAPI 진입점.

실행(저장소 루트 기준, 맥·윈도우 공통):
    cd src/server
    uv run uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import db, geo
from .collectors import auction, fleet
from .collectors.traffic import DEFAULT_SENSOR, TrafficService
from .config import settings
from .engine import Engine
from . import push as pushmod
from .agent import chat as chatmod
from .agent.tools import ToolContext
from .eum import EumClient, EumError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("wipan")


async def bootstrap(app: FastAPI) -> None:
    """기동 시 1회: 위판장 좌표, 어선 명부, 교통 센서, 위판 실적. 외부 실패는 기록하고 계속한다."""
    conn, eum = app.state.db, app.state.eum
    place = geo.AUCTION_PLACE
    try:
        p = await eum.auction_place()
        place = (float(p["latitude"]), float(p["longitude"]))
        app.state.place_info = {"name": p.get("name"), "address": p.get("address"), "lat": place[0], "lon": place[1]}
    except (EumError, KeyError, TypeError, ValueError) as e:
        log.warning("위판장 정보 조회 실패, 기본 좌표 사용: %s", e)
    app.state.place = place

    try:
        n = fleet.upsert_fleet(conn, await eum.fleet())
        log.info("어선 명부 %d척 갱신", n)
    except EumError as e:
        log.warning("어선 명부 조회 실패, DB에 남은 %d척 사용: %s", fleet.fleet_count(conn), e)

    app.state.traffic = TrafficService(eum=eum, place=place)
    try:
        await app.state.traffic.load_sensors()
    except EumError as e:
        log.warning("교통 센서 목록 조회 실패: %s", e)

    auction.load_dir(conn, settings.auction_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = db.connect(settings.db_path)
    db.init_schema(app.state.db)
    app.state.eum = EumClient(settings)
    app.state.place_info = None
    await bootstrap(app)
    engine = Engine(app.state.db, app.state.eum, app.state.place, settings.feed)
    engine.reload_fleet()
    app.state.engine = engine
    app.state.llm = None
    if settings.openai_api_key:
        from openai import AsyncOpenAI
        app.state.llm = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=1)
    else:
        log.warning("OPENAI_API_KEY 가 없어 질문창은 간단 모드로, 알림은 템플릿으로만 만듭니다.")
    app.state.pusher = pushmod.Pusher(app.state.db, settings, llm=app.state.llm)
    engine.hooks.append(app.state.pusher.on_new_arrivals)
    sched = AsyncIOScheduler()
    # 실제 3초마다 가상 시계를 확인하고, 10분(가상) 경계를 넘었을 때만 기록·알림한다.
    sched.add_job(engine.tick, "interval", seconds=3, max_instances=1, coalesce=True)
    sched.start()
    log.info("서버 준비 완료 (FEED=%s, DB=%s)", settings.feed, settings.db_path)
    yield
    sched.shutdown(wait=False)
    await app.state.eum.aclose()
    app.state.db.close()


app = FastAPI(title="위판 당직", lifespan=lifespan)


@app.exception_handler(EumError)
async def eum_error_handler(_: Request, e: EumError) -> JSONResponse:
    log.warning("요청 처리 중 E-UM 실패: %s", e)
    msg = {
        "timeout": "디지털트윈 데이터 응답이 늦습니다. 잠시 후 다시 시도해 주세요.",
        "config": "서버 설정이 빠져 있어 데이터를 불러올 수 없습니다. 관리자에게 알려 주세요.",
    }.get(e.kind, "디지털트윈 데이터를 지금 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.")
    return JSONResponse(status_code=503, content={"error": e.kind, "message": msg})


@app.get("/api/health")
def health(request: Request) -> dict:
    conn = request.app.state.db
    return {
        "ok": True,
        "feed": settings.feed,
        "fleet": fleet.fleet_count(conn),
        "auction_rows": conn.execute("SELECT COUNT(*) FROM auction_stats").fetchone()[0],
        "sensors": len(request.app.state.traffic.sensors),
    }


@app.get("/api/place")
def place(request: Request) -> dict:
    lat, lon = request.app.state.place
    return request.app.state.place_info or {"name": "구룡포수산업협동조합위판장", "lat": lat, "lon": lon}


@app.get("/api/fleet")
def fleet_list(request: Request) -> list[dict]:
    rows = request.app.state.db.execute("SELECT ship_id, name, biz, gt FROM fleet ORDER BY ship_id").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/sensors")
def sensors(request: Request) -> list[dict]:
    return request.app.state.traffic.sensors


@app.get("/api/traffic/now")
async def traffic_now(request: Request, sensor: str = DEFAULT_SENSOR) -> dict:
    return await request.app.state.traffic.now(sensor)


@app.get("/api/visit")
async def visit_advice(request: Request, visitor: bool = False) -> dict:
    """방문 권장 문구(설계 §5.4). 교통 조회가 실패해도 경매 시각 기준 문구는 준다."""
    from .rules import visit
    try:
        t = await request.app.state.traffic.now()
    except EumError:
        t = None
    return visit.recommend(t, visitor=visitor)


# --- 입항 예보 ---
@app.get("/api/today")
async def today(request: Request) -> dict:
    return await request.app.state.engine.today()


@app.get("/api/ships")
async def ships(request: Request) -> dict:
    return await request.app.state.engine.ships()


# --- 시뮬레이터 시계·데이터 소스 제어 (관리자 토큰, 설계 §1-18) ---
def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not settings.sim_admin_token:
        raise HTTPException(503, detail="관리자 토큰이 서버에 설정되지 않았습니다. .env 의 SIM_ADMIN_TOKEN 을 확인해 주세요.")
    if not hmac.compare_digest(x_admin_token, settings.sim_admin_token):
        raise HTTPException(403, detail="관리자만 시계를 조작할 수 있습니다. 관리자 토큰을 확인해 주세요.")


@app.get("/api/sim/state")
def sim_state(request: Request) -> dict:
    e = request.app.state.engine
    return {**e.clock.state(), "feed": e.feed}


@app.post("/api/sim/play", dependencies=[Depends(require_admin)])
def sim_play(request: Request, speed: float | None = Query(default=None)) -> dict:
    e = request.app.state.engine
    try:
        e.clock.play(speed)
    except ValueError as err:
        raise HTTPException(422, detail=str(err)) from None
    return {**e.clock.state(), "feed": e.feed}


@app.post("/api/sim/pause", dependencies=[Depends(require_admin)])
def sim_pause(request: Request) -> dict:
    e = request.app.state.engine
    e.clock.pause()
    return {**e.clock.state(), "feed": e.feed}


@app.post("/api/sim/seek", dependencies=[Depends(require_admin)])
def sim_seek(request: Request, t: str = Query(..., description="HH:MM")) -> dict:
    e = request.app.state.engine
    try:
        e.clock.seek(t)
    except ValueError as err:
        raise HTTPException(422, detail=str(err)) from None
    e.reset_tick()
    return {**e.clock.state(), "feed": e.feed}


@app.post("/api/sim/feed", dependencies=[Depends(require_admin)])
def sim_feed(request: Request, mode: str = Query(..., pattern="^(sim|live)$")) -> dict:
    e = request.app.state.engine
    e.set_feed(mode)
    return {**e.clock.state(), "feed": e.feed}


# --- 웹 푸시 (설계 §5.3) ---
@app.get("/api/push/key")
def push_key() -> dict:
    return {"publicKey": settings.vapid_public_key, "species": sorted(s for s in pushmod.ALLOWED_SPECIES if s)}


@app.post("/api/subscribe")
async def subscribe(request: Request) -> dict:
    body = await request.json()
    try:
        sub_id = pushmod.save_subscription(request.app.state.db, body.get("subscription") or {},
                                           {"species": body.get("species") or None})
    except ValueError as err:
        raise HTTPException(422, detail=str(err)) from None
    return {"ok": True, "id": sub_id}


@app.post("/api/unsubscribe")
async def unsubscribe(request: Request) -> dict:
    body = await request.json()
    pushmod.delete_subscription(request.app.state.db, str(body.get("endpoint", "")))
    return {"ok": True}


@app.get("/api/notifications")
def notifications(request: Request) -> list[dict]:
    return pushmod.recent_notifications(request.app.state.db, request.app.state.engine.clock.now())


@app.post("/api/push/test", dependencies=[Depends(require_admin)])
async def push_test(request: Request) -> dict:
    """리허설용: 구독한 폰 전부에 시험 알림. 지연 측정에 쓴다(설계 §11)."""
    e = request.app.state.engine
    return await request.app.state.pusher.notify(e.clock.now(), "위판 당직 시험 알림",
                                                 f"시험 발송 {real_now_str()}", {"overall": []}, [], everyone=True)


def real_now_str() -> str:
    from .feed.clock import real_now
    return real_now().strftime("%H:%M:%S")


# --- 질문창 (설계 §4.2) ---
import json as _json  # noqa: E402
import time as _time  # noqa: E402
from collections import defaultdict, deque  # noqa: E402

from fastapi.responses import StreamingResponse  # noqa: E402

_PER_IP_PER_MIN = 8
_PER_DAY = 400
_hits: dict[str, deque] = defaultdict(deque)
_day = {"date": "", "count": 0}


def _rate_limit(ip: str) -> str | None:
    """OpenAI 지원금(20만원) 보호. 넘으면 한국어 안내 문구를 돌려준다."""
    now = _time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    today_s = _time.strftime("%Y-%m-%d")
    if _day["date"] != today_s:
        _day.update(date=today_s, count=0)
    if len(q) >= _PER_IP_PER_MIN:
        return "질문이 너무 잦습니다. 1분 뒤에 다시 물어봐 주세요."
    if _day["count"] >= _PER_DAY:
        return "오늘 질문 한도를 넘었습니다. 내일 다시 이용해 주세요."
    q.append(now)
    _day["count"] += 1
    return None


@app.post("/api/chat")
async def chat(request: Request) -> StreamingResponse:
    body = await request.json()
    question = str(body.get("message", ""))
    ip = request.client.host if request.client else "?"
    limited = _rate_limit(ip)
    ctx = ToolContext(engine=request.app.state.engine, traffic=request.app.state.traffic)

    async def stream():
        if limited:
            yield f"data: {_json.dumps({'type': 'error', 'message': limited}, ensure_ascii=False)}\n\n"
            return
        answer_text = None
        try:
            async for ev in chatmod.answer(request.app.state.llm, settings.openai_model, ctx, question, body.get("history")):
                if ev["type"] == "answer":
                    answer_text = ev["text"]
                yield f"data: {_json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception:
            log.exception("질문창 처리 실패")
            yield "data: " + _json.dumps({"type": "error", "message": "답을 만들지 못했습니다. 잠시 후 다시 물어봐 주세요."}, ensure_ascii=False) + "\n\n"
        request.app.state.engine.log_event("chat", {"q": question[:300], "a": (answer_text or "")[:500]})
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- 화면(Vite 빌드 결과) 정적 서빙. API 라우트보다 뒤에 둔다. ---
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .config import REPO_ROOT  # noqa: E402

WEB_DIST = REPO_ROOT / "src" / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    log.info("화면 빌드(src/web/dist)가 없어 API만 제공합니다. 화면은 'cd src/web && npm run build'.")
