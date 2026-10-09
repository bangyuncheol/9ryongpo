---
name: project-status
description: 미구현·보류·기술부채·진행 중 과제의 현재 상태와 인수인계 메모. 지금 무엇이 남았는지 확인하거나 작업을 이어받을 때 로드한다.
---

# 프로젝트 현황

## 0. 문서 목적
**아직 안 된 것**만 둔다. 완료·폐기된 항목은 여기서 내리고 `.claude/skills/project-history/resolved-items.md` 로 옮긴다.
의도적으로 안 하는 것은 여기가 아니라 `CLAUDE.md` 에 둔다.

## 참고 파일 안내
- 설계 정본: `01_설계/01_설계.md` (§10 일정, §4 모듈 구조). 실행 방법: 루트 `README.md` "실행 방법".

## 진행 상황 (마지막 갱신 2026-10-09 밤)

**끝난 것**
- 서버 뼈대 `src/server/` (uv, Python 3.12, FastAPI). 기동 시 위판장 좌표·어선 명부 202척·교통 센서 11대·위판 실적(`data/auction/`) 적재.
- API: `/api/health` `/api/place` `/api/fleet` `/api/sensors` `/api/traffic/now` (목록은 requirements 스킬 `flows-and-pages.md`).
- 테스트 12개 (`cd src/server && uv run pytest`). 외부 호출 없이 `tests/fixtures/`의 실제 응답 일부로 돈다.

**다음 할 일 (설계 §10 순서)**
1. 시뮬레이터 v0 `app/feed/sim.py` + 가상 시계 `app/feed/clock.py` → `ships_pos` 적재. 핵심 배는 대본(§1-13).
2. 입항 판정 `app/rules/arrival.py`(§5.1) → `forecast`, 어종 추정 `app/rules/species.py`(§5.2, 4개년 10월 평균).
3. `/api/today`(입항 카드 + 어종 + 교통 현황) — 화면이 붙을 API.
4. 화면 뼈대 `src/web/` (Vite + React + Tailwind + Leaflet).
5. 웹 푸시, 질문창(tool calling), 관리자 토큰 걸린 `/sim/*`.

**알아 둘 것**
- 혼잡율 API는 23~25시간 범위를 들쭉날쭉 준다. 어제 같은 시각이 없으면 `vs_day`(24시간 중 위치)를 쓴다.
- E-UM 서비스 키가 URL에 들어가므로 URL을 로그·에러에 남기지 않는다(`app/eum.py`).
- VM 배포는 운영진 SSH 키 등록 대기(설계 §12).

## 미구현
- 위 "다음 할 일" 전부.

## 보류
- (없음)

## 기술부채
- (없음)
