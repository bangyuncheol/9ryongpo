"""구룡포항 입항 경로와 정박 자리(시뮬레이터용, 2026-10-10).

출처: OpenStreetMap(ⓒ OpenStreetMap contributors, ODbL) — 구룡포북방파제(way 1479639578),
남쪽 방파제(way 1492205516), 해안선(way 576653270)의 위판장 앞 부두 구간.
E-UM 선박 위치는 과거 항적을 주지 않아(2025-04-27 한 장뿐, 모두 바다 위) 정박 위치를 데이터로 알 수 없다.
그래서 지도 모양으로 정한 값이다. 실제 정박 위치는 실데이터가 들어오면 그대로 쓴다.
"""
from __future__ import annotations

import math

# 바다 → 수로 → 북방파제 끝 → 항구 안 (위도, 경도)
APPROACH: tuple[tuple[float, float], ...] = (
    (35.98700, 129.56400),  # 입구 바깥(남방파제 동쪽 끝의 동쪽)
    (35.98616, 129.55970),  # 두 방파제 사이 수로
    (35.98580, 129.55700),  # 북방파제 남서쪽 끝을 막 지난 곳
    (35.98760, 129.55550),  # 항구 안
)
HARBOR_KN = 3.0  # 수로부터는 3노트로 감속

# 위판장 앞 부두: 해안선 점 286(위판장 옆) → 285(남서쪽 315m)
_QUAY_A = (35.989388, 129.555154)
_QUAY_B = (35.987393, 129.552660)
_M_LAT, _M_LON = 111_000.0, 90_000.0  # 북위 36° 부근 1도당 미터


def _slot(i: int) -> tuple[float, float]:
    """정박 자리 i(0이 위판장에 가장 가까움). 부두에서 바다 쪽(남동)으로 25m, 22m 간격. 14칸 넘으면 한 줄 더 바깥."""
    north = (_QUAY_B[0] - _QUAY_A[0]) * _M_LAT
    east = (_QUAY_B[1] - _QUAY_A[1]) * _M_LON
    length = math.hypot(north, east)
    un, ue = north / length, east / length          # 부두 방향(남서)
    nn, ne = -ue, un                                # 직각, 남동(바다) 쪽
    if nn > 0:
        nn, ne = -nn, -ne
    row, k = divmod(i, 14)
    along, off = 20 + 20 * k, 25 + 22 * row
    return (_QUAY_A[0] + (un * along + nn * off) / _M_LAT,
            _QUAY_A[1] + (ue * along + ne * off) / _M_LON)


SLOTS: tuple[tuple[float, float], ...] = tuple(_slot(i) for i in range(28))
