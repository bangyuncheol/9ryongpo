"""위판 당직 FastAPI 진입점.

실행(저장소 루트 기준, 맥·윈도우 공통):
    cd src/server
    uv run uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import db, geo
from .collectors import auction, fleet
from .collectors.traffic import DEFAULT_SENSOR, TrafficService
from .config import settings
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
    log.info("서버 준비 완료 (FEED=%s, DB=%s)", settings.feed, settings.db_path)
    yield
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
