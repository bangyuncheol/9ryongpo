"""해수부 일자별 위탁판매현황(공공데이터 15102791)에서 구룡포수협 행을 받아 data/auction/ 에 월별 CSV로 저장한다.

매월 15일 전후 새 달이 등록된다. 맥·윈도우 공통 실행:
    cd src/server
    uv run python scripts/fetch_auction.py            # 저장소에 없는 달만 전부
    uv run python scripts/fetch_auction.py 2026-09    # 특정 달(이미 있으면 덮어씀)
받은 뒤 서버를 재시작하면 auction_stats 에 반영된다.

주의: 2024-12 파일처럼 모든 값이 작은따옴표로 감싸진 달이 있다(10/10 확인). 그래서 조합명은 부분 일치로 거르고 따옴표를 벗긴다.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

OAS = "https://infuser.odcloud.kr/oas/docs?namespace=15102791/v1"
UNION = "구룡포수산업협동조합"
COLUMNS = ["위판일자", "산지조합명", "위판장명", "업종명", "수산물표준코드", "수산물표준코드명", "어종상태명",
           "위판수량", "위판중량", "위판단가", "위판단가(1킬로그램)", "위판금액", "상품규격명", "상품단위명", "데이터기준일자"]


def get_json(url: str) -> dict:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # 공공 API가 가끔 끊긴다. 키가 든 URL은 출력하지 않는다.
            print(f"  재시도 {attempt + 1}/3 ({type(e).__name__})")
            time.sleep(3)
    raise SystemExit("API 호출에 세 번 실패했습니다. 잠시 후 다시 실행해 주세요.")


def month_paths() -> dict[str, str]:
    paths = get_json(OAS)["paths"]
    out = {}
    for p, v in paths.items():
        m = re.search(r"_(\d{4})(\d{2})\d{2}$", v["get"]["summary"])
        if m:
            out[f"{m.group(1)}-{m.group(2)}"] = p
    return out


def clean(v):
    if isinstance(v, str):
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] == "'":
            v = v[1:-1]
    return v


def fetch(ym: str, path: str, key: str) -> list[dict]:
    cond = urllib.parse.quote("cond[산지조합명::LIKE]") + "=" + urllib.parse.quote("구룡포")
    rows, page = [], 1
    while True:
        d = get_json(f"https://api.odcloud.kr/api{path}?serviceKey={key}&page={page}&perPage=5000&{cond}")
        rows += [{k.strip("'"): clean(v) for k, v in r.items()} for r in d.get("data", [])]
        if len(rows) >= d.get("matchCount", 0) or not d.get("data"):
            break
        page += 1
    return [r for r in rows if r.get("산지조합명") == UNION]


def main(args: list[str]) -> None:
    if not settings.data_go_kr_key:
        raise SystemExit(".env 의 DATA_GO_KR_KEY 가 비어 있습니다.")
    out_dir = settings.auction_dir
    paths = month_paths()
    have = {re.search(r"_(\d{4}-\d{2})\.csv$", f.name).group(1) for f in out_dir.glob("구룡포수협_*.csv")}
    targets = args or sorted(ym for ym in paths if ym not in have)
    if not targets:
        print("새로 받을 달이 없습니다. 최신 달:", max(paths))
        return
    for ym in targets:
        if ym not in paths:
            print(f"{ym}: 공공데이터에 아직 없습니다(매월 15일 전후 등록).")
            continue
        rows = fetch(ym, paths[ym], settings.data_go_kr_key)
        if not rows:
            print(f"{ym}: 구룡포수협 행이 0개라 저장하지 않았습니다. 원본 형식을 확인해 주세요.")
            continue
        with (out_dir / f"구룡포수협_{ym}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")  # 저장소 줄바꿈 규칙(LF)
            w.writeheader()
            w.writerows(rows)
        print(f"{ym}: {len(rows)}행 저장")


if __name__ == "__main__":
    main(sys.argv[1:])
