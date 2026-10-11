-- 배마중 SQLite 스키마. 정본: 01_설계/01_설계.md §7 (2026-10-09 1회 승인).
-- 변경은 /db-change-plan 승인 후에만. 마이그레이션 도구 없이 이 파일 하나로 관리한다.

CREATE TABLE IF NOT EXISTS fleet (
    ship_id     INTEGER PRIMARY KEY,     -- E-UM 장비 고유번호(id). 선박 위치 devId 와 같다
    reg_no      TEXT,                    -- 어선번호(shipId)
    name        TEXT NOT NULL,
    biz         TEXT,                    -- 어업종류(표지판에서 복원)
    gt          REAL,                    -- 총톤수
    sign        TEXT,
    raw_json    TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ships_pos (
    ship_id     INTEGER NOT NULL,
    ts          TEXT NOT NULL,           -- 위치 시각(ISO, sim 은 가상 시계)
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    course      REAL,
    speed       REAL,                    -- knot
    rcv_ts      TEXT,                    -- E-UM 수신 시각(live)
    source      TEXT NOT NULL CHECK (source IN ('live', 'sim')),
    PRIMARY KEY (ship_id, ts, source)
);

CREATE TABLE IF NOT EXISTS auction_stats (
    ym          TEXT NOT NULL,           -- YYYY-MM
    place       TEXT NOT NULL,           -- 위판장명(본소 = 판매과(1계))
    biz         TEXT NOT NULL,           -- 업종명
    species     TEXT NOT NULL,           -- 수산물표준코드명
    amount      REAL NOT NULL,           -- 위판금액 합(원)
    weight      REAL NOT NULL,           -- 위판중량 합(kg)
    rows        INTEGER NOT NULL,
    days        INTEGER NOT NULL,        -- 거래일 수
    PRIMARY KEY (ym, place, biz, species)
);

CREATE TABLE IF NOT EXISTS forecast (
    ts          TEXT NOT NULL,           -- 예보 계산 시각(가상 시계)
    ship_id     INTEGER NOT NULL,
    d_km        REAL NOT NULL,
    eta         TEXT,
    confidence  TEXT,
    species_json TEXT,
    PRIMARY KEY (ts, ship_id)
);

CREATE TABLE IF NOT EXISTS subs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint    TEXT NOT NULL UNIQUE,
    keys_json   TEXT NOT NULL,
    cond_json   TEXT NOT NULL,           -- {"species": null | ["붉은대게", ...]} (10/12 여러 개, 옛 문자열도 읽음)
    created_at  TEXT NOT NULL
);

-- 전화 알림 구독(10/11 /db-change-plan 승인). 시연 중에는 CALL_ALLOWED_NUMBERS 에 있는 번호만 저장·발신한다.
CREATE TABLE IF NOT EXISTS call_subs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT NOT NULL UNIQUE,    -- 숫자만, 예: 01012345678
    cond_json   TEXT NOT NULL,           -- {"species": null | ["붉은대게", ...]} (subs 와 같은 형식)
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,           -- push | forecast | chat | call | error
    payload     TEXT NOT NULL
);
