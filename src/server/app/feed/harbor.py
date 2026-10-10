"""구룡포항 입항 경로와 정박 자리(시뮬레이터용, 2026-10-10 위성 사진으로 보정).

근거
- 항구 구조: OpenStreetMap(ⓒ OpenStreetMap contributors, ODbL) 구룡포북방파제(way 1479639578)·남방파제(way 1492205516)·해안선.
- 정박 자리·입구 지점: 카카오맵 스카이뷰(위성 사진)에서 실제로 배가 붙어 있는 곳을 찍어 위경도로 변환(10/10).
  · 위판장 부두(바다 쪽으로 튀어나온 사각형 부두) 남동쪽 면과 남쪽 끝: 배가 부두와 나란히 붙어 있음 → 하역(1순위)
  · 북쪽 해안: 배가 뱃머리를 해안에 대고 나란히 붙어 있음 → 넘칠 때(2순위)
E-UM 선박 위치는 과거 항적을 주지 않아(2025-04-27 한 장, 모두 바다 위) 실제 정박 위치를 데이터로 알 수 없다.
위성 사진은 촬영 순간의 모습이라 새벽 경매 때와 다를 수 있다. 실데이터가 들어오면 실제 위치를 그대로 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 바다 → 입구(북방파제 끝과 남방파제 머리 사이) → 북방파제 끝 안쪽 → 위판장 부두 동쪽 수면 (위도, 경도)
APPROACH: tuple[tuple[float, float], ...] = (
    (35.986241, 129.560359),  # 입구 바깥(북방파제 동쪽 바다)
    (35.985420, 129.558496),  # 입구 틈
    (35.985600, 129.556955),  # 북방파제 끝 안쪽
    (35.988379, 129.556861),  # 위판장 부두 동쪽 수면
)
BASIN_NORTH = (35.989859, 129.556583)  # 위판장 부두 북쪽 수면(북쪽 해안 자리로 갈 때 거침)
HARBOR_KN = 3.0  # 입구부터 3노트로 감속


@dataclass(frozen=True)
class Berth:
    lat: float
    lon: float
    heading: float      # 정박한 배의 방향(°)
    via_north: bool     # 부두 북쪽 수면을 거쳐 가는 자리


_PIER = 222.0   # 위판장 부두 남동쪽 면 방향(부두와 나란히)
_NORTH = 330.0  # 북쪽 해안: 뱃머리를 해안(북서)에 댐
_BASE: tuple[Berth, ...] = (
    # 1순위: 위판장 부두 남동쪽 면 → 남쪽 끝
    Berth(35.989262, 129.556323, _PIER, False),
    Berth(35.989195, 129.556236, _PIER, False),
    Berth(35.989124, 129.556137, _PIER, False),
    Berth(35.988940, 129.556016, _PIER, False),
    Berth(35.988867, 129.555959, _PIER, False),
    Berth(35.988795, 129.555903, _PIER, False),
    # 2순위: 북쪽 해안
    Berth(35.990578, 129.556353, _NORTH, True),
    Berth(35.990649, 129.556476, _NORTH, True),
    Berth(35.990696, 129.556599, _NORTH, True),
    Berth(35.990683, 129.556810, _NORTH, True),
    Berth(35.990670, 129.557021, _NORTH, True),
)


def _raft(b: Berth, row: int) -> Berth:
    """넘치면 이미 붙은 배 바깥에 한 겹 더(약 6m씩 바다 쪽, 남동)."""
    return Berth(b.lat - 0.00004 * row, b.lon + 0.00005 * row, b.heading, b.via_north)


SLOTS: tuple[Berth, ...] = tuple(_raft(b, row) for row in range(3) for b in _BASE)
