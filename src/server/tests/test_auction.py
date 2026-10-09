import csv
import sqlite3

from app import db
from app.collectors.auction import aggregate_csv, load_dir

HEADER = ["위판일자", "산지조합명", "위판장명", "업종명", "수산물표준코드명", "위판중량", "위판금액"]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def test_aggregate_sums_and_counts_days(tmp_path):
    p = tmp_path / "구룡포수협_2025-10.csv"
    write_csv(p, [
        ["2025-10-01", "구룡포", "판매과(1계)", "연안자망어업", "붉은대게", "100", "500000"],
        ["2025-10-01", "구룡포", "판매과(1계)", "연안자망어업", "붉은대게", "50", "300000"],
        ["2025-10-02", "구룡포", "판매과(1계)", "연안자망어업", "붉은대게", "10", "60000"],
        ["2025-10-02", "구룡포", "판매과(1계)", "연안자망어업", "붉은대게", "0", "1000"],  # 중량 0 제외
    ])
    rows = aggregate_csv(p)
    assert rows == [("2025-10", "판매과(1계)", "연안자망어업", "붉은대게", 860000.0, 160.0, 3, 2)]


def test_load_dir_into_db(tmp_path):
    write_csv(tmp_path / "구룡포수협_2024-10.csv",
              [["2024-10-03", "구룡포", "판매과(1계)", "근해채낚기어업", "살오징어", "20", "400000"]])
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    assert load_dir(conn, tmp_path) == 1
    r = conn.execute("SELECT ym, biz, species, amount, weight, days FROM auction_stats").fetchone()
    assert tuple(r) == ("2024-10", "근해채낚기어업", "살오징어", 400000.0, 20.0, 1)
