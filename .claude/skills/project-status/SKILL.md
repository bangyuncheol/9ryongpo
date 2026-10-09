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
- 시뮬레이터 `app/feed/sim.py`(시각의 순수 함수, 대본 6척 + 실제 위치 44척, 시드 고정), 가상 시계 `app/feed/clock.py`, 실데이터 `app/feed/live.py`. 대본은 `KEY_SHIPS`.
- 엔진 `app/engine.py`: 시계·피드·룰 연결. 실제 3초마다 확인해 10분(가상) 경계에서 `ships_pos`·`forecast`·`events` 기록, 새로 입항 중이 된 배를 훅으로 넘김. 입항 판정 `rules/arrival.py`, 어종 추정 `rules/species.py`.
- API 추가: `/api/today` `/api/ships` `/api/sim/*`(조작은 `X-Admin-Token`).
- 확인된 데모 장면: 03:10에 연안자망 3척 ETA 04:25~04:35, 붉은대게 79%·골뱅이 10%.
- 화면 `src/web/` (Vite + React 19 + Tailwind 4 + react-leaflet 5): 지도(위판장★·센서▲·배●), 입항 예보·어종·교통 카드, 사장/구경 모드, sim/live 배지, `?admin=1` 진행 막대. 2초마다 `/api/today`·`/api/ships`, 1분마다 `/api/traffic/now`. 색은 `src/web/src/index.css` 토큰.
- 서버가 `src/web/dist`가 있으면 `/`에서 화면을 서빙.
- 테스트 28개 (`cd src/server && uv run pytest`). 외부 호출 없이 `tests/fixtures/`의 실제 응답 일부로 돈다.

**다음 할 일 (설계 §10 순서)**
1. 웹 푸시: `Engine.hooks`에 새 입항 알림 훅을 붙이면 된다(`app/engine.py` tick). 구독 조건 매칭 + 문장(LLM, 실패 시 템플릿).
2. 질문창(tool calling, SSE) — 도구 6개(설계 §4.2).
3. 방문 권장 문구 `rules/visit.py`(설계 §5.4) — 지금은 `/api/traffic/now`가 숫자만 준다.

**알아 둘 것**
- 어종 전체 비율은 어종을 말할 수 있는 업종끼리만 톤수 가중한다. 근해자망처럼 해마다 1위가 바뀌는 업종은 `category_only_biz`로 따로 알린다.
- 화면 디자인 확정 시 `index.css`의 `@theme` 토큰만 바꾸면 전체에 반영된다.
- 혼잡율 API는 23~25시간 범위를 들쭉날쭉 준다. 어제 같은 시각이 없으면 `vs_day`(24시간 중 위치)를 쓴다.
- E-UM 서비스 키가 URL에 들어가므로 URL을 로그·에러에 남기지 않는다(`app/eum.py`).
- VM 배포는 운영진 SSH 키 등록 대기(설계 §12).

## 미구현
- 위 "다음 할 일" 전부.

## 보류
- (없음)

## 기술부채
- 물량 상대 등급(설계 §5.2 '평소보다 적음/비슷/많음')은 기준이 없어 아직 척수·톤수만 낸다.
