---
name: project-history
description: 작업 로그·버그 수정 장부·폐기 경위·완료된 계획 원문의 아카이브. 과거 결정의 경위를 찾을 때만 로드한다.
---

# 프로젝트 이력

## 0. 문서 목적
이 스킬의 문서들은 **이력 보존용**이다. 현행 기준이 아니므로 여기 내용을 근거로 코드를 수정하지 않는다.
현행 기준은 `CLAUDE.md` · `.claude/rules/` · 스펙 스킬(`db-schema`, `requirements`)이다.

## 참고 파일 안내
- **`bug-fix.md`** — 유형별 버그 수정 장부
- **`resolved-items.md`** — 완료·폐기된 과제와 경위
- **`legacy-docs-note.md`** — 구 문서 → 새 구조 이관 매핑표
- **`work-log-YYYY-MM-DD.md`** — 날짜별 작업 로그

## 운영 규칙
- 새 버그 수정 → `bug-fix.md` 에 추가
- 기능 완료·폐기 → `project-status` 에서 내리고 `resolved-items.md` 또는 날짜별 로그에 기록
- 오너 결정은 결정일과 함께 기록
