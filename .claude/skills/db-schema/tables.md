# 테이블 상세

테이블 전체 목록은 설계 정본 §7. 여기는 정본 승인 뒤 추가된 것만 상세히 적는다.

## subs (설계 §7, cond_json 형식 2026-10-12 확장)
- 용도: 웹 푸시 구독. 기기(endpoint)마다 한 줄, 같은 기기는 조건만 갱신.
- cond_json: `{"species": null | ["붉은대게", ...]}` — null=모두, 목록 중 하나라도 같은 달 비중 20% 이상이면 알림(입항 한 번에 한 번). 옛 형식 문자열도 읽는다. 저장은 `push.norm_species`를 거친 값만.

## call_subs (2026-10-11 승인)
- 용도: 전화 알림 구독. 입항 알림이 나갈 때 조건이 맞고 `CALL_ALLOWED_NUMBERS`에 있는 번호로 전화를 건다.
- 컬럼:

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | |
| phone | TEXT | NOT NULL UNIQUE | 숫자만(예: 01012345678). 개인정보 — 로그·화면에는 가운데를 가린다 |
| cond_json | TEXT | NOT NULL | `{"species": null \| ["붉은대게", "살오징어", ...]}` (`subs`와 같은 형식). null=모두. 2026-10-12 여러 개로 확장(/db-change-plan 승인) — 옛 형식 문자열 `"붉은대게"`도 같은 뜻으로 읽는다(`push.norm_species`) |
| created_at | TEXT | NOT NULL | 실제 시각 ISO |

- 관계: 없음. 통화 결과는 `events`(kind='call')에 남긴다.
- 인덱스: phone UNIQUE.

(새 테이블은 아래 형식으로 추가한다.)

## <table_name>
- 용도:
- 컬럼:

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|

- 관계:
- 인덱스:
