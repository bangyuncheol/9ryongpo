---
name: deploy
description: 배포 절차·환경 변수 목록·프로덕션 마이그레이션 대기 목록. 배포 전 점검(/deploy-check)이나 환경 변수를 다룰 때 로드한다.
---

# 배포

## 0. 문서 목적
현행 배포 절차의 정본. 배포 환경이 정해지면 채운다.

## 참고 파일 안내
- **`migrations.md`** — 프로덕션 적용 대기 중인 마이그레이션 목록

## 배포 환경 — Railway (2026-10-15 전환)
- 대회 제공 GCP VM이 만료돼 Railway로 옮겼다. 프로젝트 `independent-perfection` > 서비스 `9ryongpo`(GitHub `bangyuncheol/9ryongpo` `main` 자동 배포).
- 빌드: 루트 `Dockerfile`(1단계 Node 22로 `src/web` 빌드 → 2단계 Python 3.12 + uv로 `src/server` 설치, `data/auction/` CSV·`dist/` 포함). `railway.toml`이 Dockerfile 빌더와 `/api/health` 헬스체크를 지정한다. `.dockerignore`가 `.env`·문서·영상을 이미지에서 뺀다.
- 실행: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`. `DB_PATH` 기본값은 이미지 안 `/app/db/app.db`.
- 환경 변수: Railway 서비스 > Variables 에 `.env`의 값을 그대로 넣는다(아래 표). `VITE_KAKAO_MAP_KEY`는 빌드 인자로도 들어가므로 Variables에 넣으면 된다. 카카오 개발자 콘솔 JavaScript SDK 도메인에 Railway 도메인을 등록한다.
- **DB 지속성**: 컨테이너 파일시스템은 재배포 때 초기화된다(위판 실적은 CSV에서 다시 적재되지만 푸시 구독은 사라짐). 구독을 남기려면 서비스에 Volume을 만들어 마운트 경로 `/app/db`로 붙인다.
- 전화(`PHONE_ENABLED=1`)는 번호당 서버 하나만. Railway에서 켜려면 로컬·다른 서버에서 먼저 끈다.
- 배포 절차: 로컬 테스트 통과 → `main` 푸시 → Railway가 자동 빌드·배포 → 대시보드 Deployments에서 성공 확인 → 화면 핵심 흐름 1회 확인. 되돌리기는 대시보드에서 이전 배포 Rollback.

## (참고) 이전 배포 환경 — GCP VM (2026-10-09~10-15, 만료)
- 대회 제공 GCP VM 1대(운영진이 만든 VM에 SSH 공개키로 접속). 프로젝트 권한이 아니라 Cloud Run은 못 쓴다.
- VM에서 FastAPI 프로세스 1개를 systemd로 상시 실행. 화면은 FastAPI가 `src/web/dist`를 서빙. DB는 VM 디스크 `data/app.db`.
- 파일: `src/deploy/setup_vm.sh`(첫 설치) · `update.sh`(갱신) · `wipan.service`(systemd) · `Caddyfile`(HTTPS). 모두 리눅스 VM 전용.

## 현재 VM (2026-10-12 설치)
- 외부 IP `34.68.103.105`, 접속 `ssh -i ~/.ssh/9ryongpo_gcp bang-mac@34.68.103.105` (사용자 이름 = 전달한 공개 키 끝 주석). Debian 13.
- **여러 팀이 같이 쓰는 VM**: 7개 계정이 모두 sudo(`google-sudoers`)라 `.env`는 다른 팀 root가 읽을 수 있다(오너가 알고 전부 올리기로 결정). 대회 후 키 재발급.
- 80·443을 다른 팀과 다투지 않게 서버는 `127.0.0.1:8731`, 외부 공개는 Cloudflare 터널(`wipan-tunnel` 서비스). 주소 **https://bmj.kr** (가비아 구매 → 네임서버 Cloudflare, 계정 bang794613@gmail.com). 터널·Public Hostname(`bmj.kr`·`www` → `HTTP 127.0.0.1:8731`)은 대시보드에서 관리. `.env`에 `TUNNEL_TOKEN`이 없으면 trycloudflare 임시 주소로 뜬다.
- Cloudflare 계정 이메일 인증이 안 돼 `cloudflared tunnel login`(cert 방식)은 못 쓴다 → 대시보드 토큰 방식.
- 전화는 VM만 ClawOps 번호에 붙는다: `/etc/systemd/system/wipan.service.d/phone.conf`의 `Environment=PHONE_ENABLED=1`(시스템 환경 변수가 `.env`보다 우선이라 `.env`를 다시 올려도 유지). 로컬에서 전화 시험하려면 먼저 VM의 이 파일을 지우고 `sudo systemctl daemon-reload && sudo systemctl restart wipan`. 실제 발신은 전화 스위치(`calls_on`)가 켜져 있어야 한다. VM은 같은 파일에 `Environment=PHONE_CALLS_ON=1`을 둬 재시작·배포 뒤에도 켜진 채로 뜬다(10/13 오너). 잠시 끄려면 `/?admin=1` 진행 막대 스위치(재시작하면 다시 켜짐), 계속 끄려면 이 줄을 지우고 `daemon-reload`·재시작.
- VM에는 GitHub 인증을 두지 않는다. 코드는 로컬에서 `git push vm main`(VM 저장소가 `receive.denyCurrentBranch updateInstead`)으로 보낸다.

## 첫 설치 (VM 접속 후 1회)
1. 로컬: `git remote add vm bang-mac@<IP>:9ryongpo` / VM: `git init -b main ~/9ryongpo && git -C ~/9ryongpo config receive.denyCurrentBranch updateInstead` (git 없으면 `sudo apt-get install -y git`)
2. 로컬: `git push vm main` (키 지정: `GIT_SSH_COMMAND="ssh -i ~/.ssh/9ryongpo_gcp"`), `.env`는 scp로 `~/9ryongpo/.env`에 올리고 `chmod 600`. 메신저·저장소로 보내지 않는다.
3. VM: `bash ~/9ryongpo/src/deploy/setup_vm.sh` — 호스트를 안 주면 터널, `<호스트>`를 주면 Caddy(80·443 필요)
4. Kakao Developers > 플랫폼 키 > JavaScript SDK 도메인에 터널 주소 추가(카카오맵용)
5. 폰 크롬에서 주소 열기 → 알림 받기 → `/?admin=1`에서 "시험 알림".

## 배포 절차 (코드 갱신)
1. 로컬에서 테스트 통과 확인(`cd src/server && uv run pytest`) 후 `main`에 푸시
2. `.claude/skills/qa-regression/checklist.md` 관련 항목 확인
3. 로컬에서 `git push vm main` → VM에서 `bash ~/9ryongpo/src/deploy/update.sh` (받기 → 의존성 → 테스트 → 화면 빌드 → 재시작 → health 확인)
4. 화면에서 핵심 흐름 1회 확인(03:10 재생 → 입항 카드 → 알림함)
- 되돌리기: VM에서 `git checkout <이전 커밋>` 후 `update.sh` 대신 `sudo systemctl restart wipan`. 원인 고친 뒤 `git checkout main`.
- 스키마는 `src/server/app/schema.sql`(CREATE IF NOT EXISTS)라 별도 마이그레이션 적용 단계가 없다.

## 안드로이드 APK (TWA, 2026-10-13)
- `src/android/`는 `https://bmj.kr`을 크롬 엔진으로 띄우는 껍데기 앱(Bubblewrap 1.27.0, 패키지 `kr.bmj.twa`). 화면·기능은 웹 배포로 바뀌니 APK를 다시 만들 일은 거의 없다.
- 준비(1회): JDK 17 + 안드로이드 SDK(cmdline-tools, `build-tools;34.0.0`). `~/.bubblewrap/config.json`에 `jdkPath`·`androidSdkPath`. SDK 폴더에 `tools`가 없으면 Bubblewrap이 SDK를 거부하니 `cmdline-tools/latest`를 `tools`로 링크한다.
- 빌드: `.env`의 `BUBBLEWRAP_KEYSTORE_PASSWORD`·`BUBBLEWRAP_KEY_PASSWORD`를 환경에 올리고 `cd src/android` → `npx @bubblewrap/cli@1.27.0 build --skipPwaValidation` → `app-release-signed.apk`. `twa-manifest.json`을 고쳤으면 먼저 `update --skipVersionUpgrade`, 다시 배포할 땐 `appVersionCode`를 올린다.
- 서명 키 `src/android/android.keystore`는 커밋하지 않는다. 키를 잃으면 이미 설치된 앱을 업데이트할 수 없으니 오너가 따로 보관한다. 키를 바꾸면 `src/web/public/.well-known/assetlinks.json`의 SHA-256 지문도 바꿔야 한다. 지문이 안 맞으면 앱 위에 주소창이 보인다(동작은 함).

## 위판 실적 월 갱신
- 해수부 일자별 위탁판매현황은 매월 15일 전후 새 달이 등록된다(다음: 2026-09분 10/15).
- 로컬에서 `cd src/server && uv run python scripts/fetch_auction.py` → 새 CSV 커밋·푸시 → VM에서 `update.sh`(재시작 시 자동 적재).

## HTTPS (웹 푸시 필수)
- **80·443 포트가 열린 경우**: Caddy가 sslip.io 호스트로 인증서를 자동 발급(`setup_vm.sh` 5단계).
- **포트가 막힌 경우 또는 로컬에서 폰 시험**: Cloudflare 임시 터널. 계정 불필요, 주소는 실행할 때마다 바뀐다.
  - 설치: 맥 `brew install cloudflared`, 윈도우 `winget install --id Cloudflare.cloudflared`, 리눅스 공식 .deb
  - 실행: `cloudflared tunnel --url http://localhost:8000` (로컬 개발 서버 기준. VM은 8731) → 출력되는 `https://….trycloudflare.com` 을 폰에서 연다
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
| `PHONE_CALLS_ON` | `1`이면 입항 알림 전화 발신 스위치가 켜진 채로 뜬다(재시작·배포 뒤에도). 체험 발신 시간을 쓴다 | 아니오(기본 0) |
| `CLAWOPS_API_KEY` / `CLAWOPS_ACCOUNT_ID` | ClawOps API 키·계정 ID | 전화 쓸 때 예 |
| `CLAWOPS_FROM_NUMBER` | 발급받은 070 번호(숫자만) | 전화 쓸 때 예 |
| `CALL_ALLOWED_NUMBERS` | 전화를 걸 수 있는 번호(쉼표 구분) | 전화 쓸 때 예 |
| `CLOVA_SECRET_KEY` | 전화 받아쓰기(CLOVA Speech). 없으면 OpenAI 받아쓰기로 동작 | 전화 쓸 때 권장 |
| `GEMINI_API_KEY` | 전화 음성 합성 키(하루 100회). 음성은 `data/tts_cache/`에 저장돼 재사용 | 전화 쓸 때 예 |
| `KAKAO_REST_KEY` | 카카오 REST API 키(지도 키와 같은 앱). 질문창·전화의 '어디서 출발하면 몇 시?' 답(장소 검색·자동차 길찾기). 서버 전용 — `VITE_` 를 붙이면 화면에 노출된다. 비우면 그 질문만 '계산할 수 없음' | 권장 |
| `VITE_KAKAO_MAP_KEY` | 카카오맵 JavaScript 키(화면 빌드 때 들어가는 공개 키). 운영 도메인을 Kakao Developers의 JavaScript SDK 도메인에 등록해야 지도가 뜸. 비우면 Leaflet 지도 | 아니오 |
| `TUNNEL_TOKEN` | Cloudflare 터널 토큰(대시보드 Zero Trust > Networks > Tunnels의 `bmj`). VM `wipan-tunnel`이 읽는다. 있으면 `https://bmj.kr`·`www.bmj.kr` 고정, 없으면 trycloudflare 임시 주소 | VM 예 |
