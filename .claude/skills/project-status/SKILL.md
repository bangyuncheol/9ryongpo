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
- 웹 푸시: `app/push.py`(구독 저장·검증, 조건 매칭, 만료 구독 삭제, 발송 기록), 알림 문구 템플릿 `rules/brief.py`, 서비스 워커 `src/web/public/sw.js`, 알림 받기·알림함 카드. 03:10 틱에 "04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성. 경매 09:00(기본값)" 확인.
- 질문창: `app/agent/tools.py`(도구 6개: 입항 예보·어종·교통·방문 권장·과거 실적·알림 준비), `app/agent/chat.py`(OpenAI Responses API, `gpt-6.1-sol` medium, 최대 5회 도구 왕복). LLM 실패 시 간단 모드, 크레딧·인증 오류면 5분 쿨다운. 화면 `ChatCard`(자주 묻는 질문 4개, 도구 호출 기록 스트리밍, '알려줘'면 알림 받기 버튼 준비).
- 방문 권장 `rules/visit.py` + `/api/visit`, 교통 카드에 표시.
- 알림 문장: 템플릿을 LLM(`reasoning low`)이 다듬되, 숫자 집합·'가능성'·길이가 템플릿과 다르면 버리고 템플릿 사용(`rules/brief.py accept`). 크레딧 쿨다운은 질문창과 공유.
- `VAPID_SUBJECT`는 주소만 넣어도 `mailto:`를 자동으로 붙인다.
- 배포 준비: `src/deploy/`(setup_vm.sh·update.sh·wipan.service·Caddyfile), deploy 스킬에 첫 설치·갱신·되돌리기·HTTPS(Caddy+sslip.io 또는 Cloudflare 터널)·환경 변수 표.
- 리허설 체크리스트 `qa-regression/checklist.md`(데모 장면·푸시·장애 대비).
- 실데이터 모드에서 위치가 24시간 넘게 미갱신이면 예보·기록·알림을 멈추고 `notice`("…이후 갱신되지 않아 입항 예보를 낼 수 없습니다")를 띄운다. 멈춘 위치로 엉터리 ETA·푸시가 나가던 문제 수정(10/9).
- 화면 One UI 1차 반영(`ui-design.md` 적용 상태 참고). 지도는 처음 한 번 위판장·배 전체에 맞춤.
- 틱: 배속이 높아 10분 경계를 여러 개 지나도 하나씩 처리(600배 재생에서 03:10 알림 누락 방지). 되감으면 `reset` 이벤트를 남기고 알림함은 그 이후만 보여 준다.
- 테스트 50개 (`cd src/server && uv run pytest`). 외부 호출 없이 `tests/fixtures/`의 실제 응답 일부로 돈다.

**다음 할 일 (설계 §10 순서)**
1. **폰 푸시 실기 시험**: HTTPS 주소 필요(로컬은 Cloudflare 임시 터널 또는 VM). `.env`의 `VAPID_SUBJECT=mailto:주소`가 비어 있으면 발송을 건너뛰고 알림함에만 남긴다.
2. **OpenAI 크레딧 충전 후 LLM 경로 실기 확인**: 지금 키는 `credit_balance_exhausted`(10/9). 그동안 질문창은 간단 모드(낱말 규칙)로 같은 도구를 불러 답한다.
3. VM 배포: SSH 키 등록 후 deploy 스킬 '첫 설치' 절차(`src/deploy/setup_vm.sh`). 리허설은 `qa-regression/checklist.md`.
4. UI 작업 단계: One UI 기준 정리(`.claude/rules/ui-design.md`) `rules/visit.py`(설계 §5.4) — 지금은 `/api/traffic/now`가 숫자만 준다.

**알아 둘 것**
- 어종 전체 비율은 어종을 말할 수 있는 업종끼리만 톤수 가중한다. 근해자망처럼 해마다 1위가 바뀌는 업종은 `category_only_biz`로 따로 알린다.
- 화면 디자인은 UI 작업 단계에서 One UI 기준으로 정리한다(`.claude/rules/ui-design.md`, `samsung-one-ui.md`). 토큰은 `index.css`의 `@theme`만 바꾸면 전체에 반영된다.
- 혼잡율 API는 23~25시간 범위를 들쭉날쭉 준다. 어제 같은 시각이 없으면 `vs_day`(24시간 중 위치)를 쓴다.
- E-UM 서비스 키가 URL에 들어가므로 URL을 로그·에러에 남기지 않는다(`app/eum.py`).
- VM 배포는 운영진 SSH 키 등록 대기(설계 §12).

## 미구현
- 위 "다음 할 일" 전부.

## 보류
- (없음)

## 기술부채
- 물량 상대 등급(설계 §5.2 '평소보다 적음/비슷/많음')은 기준이 없어 아직 척수·톤수만 낸다.
