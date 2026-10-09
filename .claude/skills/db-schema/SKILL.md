---
name: db-schema
description: 데이터베이스 테이블·컬럼·관계·접근 정책의 현행 스펙. 스키마를 읽거나 바꾸는 작업, DB 관련 쿼리를 작성할 때 로드한다.
---

# DB 스키마

## 0. 문서 목적
이 스킬은 **현행 스펙**이다. 변경 규칙은 여기 두지 않는다 → `.claude/rules/database.md`, `.claude/rules/permissions.md`.

## 참고 파일 안내
- **`tables.md`** — 테이블·컬럼·관계 상세
- **`rls-and-migrations.md`** — 접근 정책과 적용 완료된 마이그레이션 요약

## 요약
- 데이터베이스: SQLite 파일 1개. 테이블 정본은 `01_설계/01_설계.md` §7, 실제 정의는 `src/server/schema.sql`.
