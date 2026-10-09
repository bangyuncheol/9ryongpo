"""E-UM 디지털트윈 포항 API 클라이언트.

주의: 서비스 키가 URL 쿼리에 들어가므로 URL을 로그·에러 문구에 절대 남기지 않는다.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings

log = logging.getLogger(__name__)
# httpx 기본 INFO 로그는 요청 URL(서비스 키 포함)을 찍는다.
logging.getLogger("httpx").setLevel(logging.WARNING)


class EumError(Exception):
    """E-UM 호출 실패. kind: timeout | http | invalid | config"""

    def __init__(self, kind: str, path: str, detail: str = ""):
        self.kind, self.path, self.detail = kind, path, detail
        super().__init__(f"E-UM {path} 호출 실패({kind}) {detail}".strip())


class EumClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._s = settings
        self._client = client or httpx.AsyncClient(timeout=settings.http_timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        if not self._s.eum_service_key:
            raise EumError("config", path, "EUM_SERVICE_KEY 가 비어 있음")
        url = f"{self._s.eum_base_url}/{path}"
        try:
            r = await self._client.get(url, params={"serviceKey": self._s.eum_service_key})
        except httpx.TimeoutException as e:
            raise EumError("timeout", path) from None
        except httpx.HTTPError as e:
            raise EumError("http", path, type(e).__name__) from None
        if r.status_code != 200:
            raise EumError("http", path, f"HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            raise EumError("invalid", path, "JSON 아님") from None
        if not isinstance(body, dict) or "data" not in body:
            raise EumError("invalid", path, "data 키 없음")
        return body["data"]

    async def fleet(self) -> list[dict]:
        return await self._get("ship/devices")

    async def positions(self) -> list[dict]:
        return await self._get("ship/devices/realtime")

    async def sensors(self) -> list[dict]:
        return await self._get("transp/devices/list")

    async def auction_place(self) -> dict:
        return await self._get("auctionPlace/Info")

    async def traffic_per_hour(self) -> dict[str, list[dict]]:
        return await self._get("statistics/trafficDatasPerHour")

    async def congestion(self) -> list[dict]:
        return await self._get("traffic/congestion")
