import shutil

import pytest

from app.config import settings

# 테스트는 데모 기준 달(4개년 10월 + 최신 2026-08)만 쓴다. 56개월 전체를 매번 읽으면 느리고,
# '없는 달이면 가까운 달' 같은 규칙을 시험할 수 없다.
TEST_MONTHS = ["2022-10", "2023-10", "2024-10", "2025-10", "2026-08"]


@pytest.fixture(scope="session")
def auction_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("auction")
    for ym in TEST_MONTHS:
        shutil.copy(settings.auction_dir / f"구룡포수협_{ym}.csv", d)
    return d
