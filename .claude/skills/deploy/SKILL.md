---
name: deploy
description: 배포 절차·환경 변수 목록·프로덕션 마이그레이션 대기 목록. 배포 전 점검(/deploy-check)이나 환경 변수를 다룰 때 로드한다.
---

# 배포

## 0. 문서 목적
현행 배포 절차의 정본. 배포 환경이 정해지면 채운다.

## 참고 파일 안내
- **`migrations.md`** — 프로덕션 적용 대기 중인 마이그레이션 목록

## 배포 환경 (2026-10-09 결정, 설계 §1-9·§1-19)
- 대회 제공 GCP VM 1대(운영진이 만든 VM에 SSH 공개키로 접속). 프로젝트 권한이 아니라 Cloud Run은 못 쓴다.
- VM에서 FastAPI 프로세스 1개를 systemd로 상시 실행. 화면은 FastAPI가 `src/web/dist`를 서빙. DB는 VM 디스크 `data/app.db`.
- 파일: `src/deploy/setup_vm.sh`(첫 설치) · `update.sh`(갱신) · `wipan.service`(systemd) · `Caddyfile`(HTTPS). 모두 리눅스 VM 전용.

## 첫 설치 (VM 접속 후 1회)
1. `git clone https://github.com/bangyuncheol/9ryongpo.git ~/9ryongpo`
2. 로컬의 `.env`를 VM `~/9ryongpo/.env`로 복사(scp). 메신저·저장소로 보내지 않는다.
3. 외부 IP 확인 후 HTTPS 호스트 정하기: IP `34.64.1.2` → `34-64-1-2.sslip.io`.
4. `bash ~/9ryongpo/src/deploy/setup_vm.sh 34-64-1-2.sslip.io`
5. Kakao Developers > 플랫폼 키 > JavaScript SDK 도메인에 `https://<호스트>` 추가(카카오맵용)
6. 폰 크롬에서 `https://<호스트>/` 열기 → 알림 받기 → `/?admin=1`에서 "시험 알림".

## 배포 절차 (코드 갱신)
1. 로컬에서 테스트 통과 확인(`cd src/server && uv run pytest`) 후 `main`에 푸시
2. `.claude/skills/qa-regression/checklist.md` 관련 항목 확인
3. VM에서 `bash ~/9ryongpo/src/deploy/update.sh` (받기 → 의존성 → 테스트 → 화면 빌드 → 재시작 → health 확인)
4. 화면에서 핵심 흐름 1회 확인(03:10 재생 → 입항 카드 → 알림함)
- 되돌리기: VM에서 `git checkout <이전 커밋>` 후 `update.sh` 대신 `sudo systemctl restart wipan`. 원인 고친 뒤 `git checkout main`.
- 스키마는 `src/server/app/schema.sql`(CREATE IF NOT EXISTS)라 별도 마이그레이션 적용 단계가 없다.

## 위판 실적 월 갱신
- 해수부 일자별 위탁판매현황은 매월 15일 전후 새 달이 등록된다(다음: 2026-09분 10/15).
- 로컬에서 `cd src/server && uv run python scripts/fetch_auction.py` → 새 CSV 커밋·푸시 → VM에서 `update.sh`(재시작 시 자동 적재).

## HTTPS (웹 푸시 필수)
- **80·443 포트가 열린 경우**: Caddy가 sslip.io 호스트로 인증서를 자동 발급(`setup_vm.sh` 5단계).
- **포트가 막힌 경우 또는 로컬에서 폰 시험**: Cloudflare 임시 터널. 계정 불필요, 주소는 실행할 때마다 바뀐다.
  - 설치: 맥 `brew install cloudflared`, 윈도우 `winget install --id Cloudflare.cloudflared`, 리눅스 공식 .deb
  - 실행: `cloudflared tunnel --url http://localhost:8000` → 출력되는 `https://….trycloudflare.com` 을 폰에서 연다
  - 주소가 바뀌면 브라우저 입장에선 다른 사이트라 알림 받기를 다시 눌러야 한다.

## 환경 변수
값은 절대 적지 않는다. 이름과 용도만. 예시 파일은 루트 `.env.example`.

| 이름 | 용도 | 필수 |
|---|---|---|
| `EUM_SERVICE_KEY` | E-UM 디지털트윈 포항 API | 예 |
| `DATA_GO_KR_KEY` | 공공데이터포털(해수부 위탁판매 API, 실적 재수집 때만) | 아니오 |
| `OPENAI_API_KEY` | 질문창·알림 문장. 없거나 크레딧이 없으면 간단 모드·템플릿으로 동작 | 아니오 |
| `OPENAI_MODEL` | 기본 `gpt-6.1-sol` | 아니오 |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | 웹 푸시 키 쌍. 팀 공용 하나 | 예 |
| `VAPID_SUBJECT` | 푸시 연락 주소. 주소만 넣어도 `mailto:` 자동 | 예 |
| `FEED` | 시작 데이터 소스 `sim`/`live` | 아니오(기본 sim) |
| `DB_PATH` | SQLite 위치(기본 `./data/app.db`) | 아니오 |
| `PHONE_ENABLED` | `1`이면 전화 에이전트를 ClawOps 번호에 붙인다. **번호당 서버 하나만**(로컬과 VM 동시 금지) | 아니오(기본 0) |
| `CLAWOPS_API_KEY` / `CLAWOPS_ACCOUNT_ID` | ClawOps API 키·계정 ID | 전화 쓸 때 예 |
| `CLAWOPS_FROM_NUMBER` | 발급받은 070 번호(숫자만) | 전화 쓸 때 예 |
| `CALL_ALLOWED_NUMBERS` | 전화를 걸 수 있는 번호(쉼표 구분) | 전화 쓸 때 예 |
| `CLOVA_SECRET_KEY` | 전화 받아쓰기(CLOVA Speech). 없으면 OpenAI 받아쓰기로 동작 | 전화 쓸 때 권장 |
| `GEMINI_API_KEY` | 전화 음성 합성 키(하루 100회). 음성은 `data/tts_cache/`에 저장돼 재사용 | 전화 쓸 때 예 |
| `KAKAO_REST_KEY` | 카카오 REST API 키(지도 키와 같은 앱). 질문창·전화의 '어디서 출발하면 몇 시?' 답(장소 검색·자동차 길찾기). 서버 전용 — `VITE_` 를 붙이면 화면에 노출된다. 비우면 그 질문만 '계산할 수 없음' | 권장 |
| `VITE_KAKAO_MAP_KEY` | 카카오맵 JavaScript 키(화면 빌드 때 들어가는 공개 키). 운영 도메인을 Kakao Developers의 JavaScript SDK 도메인에 등록해야 지도가 뜸. 비우면 Leaflet 지도 | 아니오 |
