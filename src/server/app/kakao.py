"""카카오 장소 검색(로컬 API)·자동차 길찾기(카카오모빌리티) 클라이언트(10/11, 설계 §4.2 출발 시각 안내).

REST 키는 Authorization 헤더에만 싣는다. URL·로그·에러 문구에 남기지 않는다.
같은 질문이 반복되기 쉬워(전화 되물음) 결과를 10분 동안 기억해 호출 한도를 아낀다.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
NAVI_URL = "https://apis-navi.kakaomobility.com/v1/directions"
FUTURE_URL = "https://apis-navi.kakaomobility.com/v1/future/directions"
CACHE_S = 600


class KakaoError(Exception):
    """카카오 호출 실패. kind: config | timeout | http | invalid | noroute"""

    def __init__(self, kind: str, what: str, detail: str = ""):
        self.kind, self.what, self.detail = kind, what, detail
        super().__init__(f"카카오 {what} 실패({kind}) {detail}".strip())


class KakaoClient:
    def __init__(self, rest_key: str, client: httpx.AsyncClient | None = None, timeout_s: float = 6.0):
        self._key = rest_key
        # 전화 응답이 늦어지지 않게 짧게 기다린다. 실패하면 규칙(rules/travel)이 대략 계산으로 넘어간다
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._cache: dict[tuple, tuple[float, Any]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, what: str, url: str, params: dict) -> Any:
        if not self._key:
            raise KakaoError("config", what, "KAKAO_REST_KEY 가 비어 있음")
        ck = (url, tuple(sorted(params.items())))
        hit = self._cache.get(ck)
        if hit and time.monotonic() - hit[0] < CACHE_S:
            return hit[1]
        try:
            r = await self._client.get(url, params=params, headers={"Authorization": f"KakaoAK {self._key}"})
        except httpx.TimeoutException:
            raise KakaoError("timeout", what) from None
        except httpx.HTTPError as e:
            raise KakaoError("http", what, type(e).__name__) from None
        if r.status_code != 200:
            raise KakaoError("http", what, f"HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            raise KakaoError("invalid", what, "JSON 아님") from None
        self._cache[ck] = (time.monotonic(), body)
        return body

    async def search(self, query: str, near: tuple[float, float]) -> list[dict]:
        """키워드 장소 검색. near=(lon, lat) 기준 거리(distance, m)가 함께 온다."""
        body = await self._get("장소 검색", LOCAL_URL, {"query": query, "x": f"{near[0]:.6f}", "y": f"{near[1]:.6f}",
                                                    "sort": "accuracy", "size": 5})
        docs = body.get("documents") if isinstance(body, dict) else None
        if not isinstance(docs, list):
            raise KakaoError("invalid", "장소 검색", "documents 없음")
        return docs

    async def address(self, query: str) -> list[dict]:
        """주소 검색(동·읍·면·도로명). 장소 이름 검색은 '양덕동'을 동 안의 아무 시설로 잡아서(10/11) 주소 꼴이면 먼저 쓴다."""
        body = await self._get("주소 검색", ADDRESS_URL, {"query": query, "size": 5})
        docs = body.get("documents") if isinstance(body, dict) else None
        if not isinstance(docs, list):
            raise KakaoError("invalid", "주소 검색", "documents 없음")
        return docs

    async def region(self, at: tuple[float, float]) -> str | None:
        """좌표(lon, lat) → '포항시 남구 구룡포읍' 같은 행정동 이름(10/13, '내 위치에서' 답에 동네를 붙인다)."""
        body = await self._get("행정구역 조회", REGION_URL, {"x": f"{at[0]:.6f}", "y": f"{at[1]:.6f}"})
        docs = body.get("documents") if isinstance(body, dict) else None
        if not isinstance(docs, list):
            raise KakaoError("invalid", "행정구역 조회", "documents 없음")
        d = next((d for d in docs if d.get("region_type") == "H"), docs[0] if docs else None)
        if not d:
            return None
        return " ".join(x for x in (d.get("region_2depth_name"), d.get("region_3depth_name")) if x) or d.get("address_name")

    async def route(self, origin: tuple[float, float], dest: tuple[float, float], depart: datetime | None = None) -> dict:
        """자동차 길찾기. depart 를 주면 그 출발 시각의 예측 교통(미래 운행), 없으면 실제 지금 도로 상황.
        반환 {'distance_m', 'duration_s'}."""
        params = {"origin": f"{origin[0]:.6f},{origin[1]:.6f}", "destination": f"{dest[0]:.6f},{dest[1]:.6f}",
                  "priority": "RECOMMEND"}
        url = NAVI_URL
        if depart is not None:
            url = FUTURE_URL
            params["departure_time"] = depart.strftime("%Y%m%d%H%M")
        body = await self._get("길찾기", url, params)
        try:
            rt = body["routes"][0]
        except (KeyError, IndexError, TypeError):
            raise KakaoError("invalid", "길찾기", "routes 없음") from None
        if rt.get("result_code") != 0:
            raise KakaoError("noroute", "길찾기", str(rt.get("result_msg", "")))
        s = rt["summary"]
        return {"distance_m": int(s["distance"]), "duration_s": int(s["duration"])}
