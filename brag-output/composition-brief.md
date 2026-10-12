# Hyperframes Composition Brief: 배마중

## Objective
배마중(구룡포항 새벽 입항·어종 알림)의 **모바일 웹 사용 설명 영상**. 폰 화면을 그대로 재현해 "이렇게 쓴다"를 22초 안에 보여 준다.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: vertical — 1080x1920, 30fps
- Duration: 22초

## Source Material
- Project root: `9ryongpo/` (화면은 `src/web/`, 3차 시안 `src/web/src/v3/AppV3.tsx` + `src/web/src/v2/`)
- Primary files read: `index.html`, `src/index.css`(@theme 토큰), `src/v2/v2.css`(.v2 토큰), `AppV2.tsx`(Header·NextShip·Depart·Toast), `AppV3.tsx`(폰 홈+탭 4개), `WaitFish.tsx`(알림 카드), `manifest.webmanifest`, `public/icon.svg`
- Product name: 배마중
- Tagline / strongest claim: "구룡포 새벽 입항·어종 알림" / "어떤 배가 몇 시에 무엇을 싣고 들어오는지"
- Key UI or visual moment to recreate: '곧 들어오는 배' 카드(40px 주황 시각 `04:25`), 알림 띠 `📣 입항 알림을 보냈어요`, 네이비 '언제 가면 될까요' 카드, 아래 탭 4개
- Copy that must appear verbatim (앱 문구 그대로):
  - 좋은 새벽이에요. 오늘도 배가 들어오고 있어요.
  - 곧 들어오는 배 / 다음 입항까지 약 75분 / 예측 · 신뢰도 높음
  - 남진호 / 자망선 5t · 위판장까지 11.7km / 붉은대게 가능성 높음 추정 79%
  - 기다리는 생선이 있나요? / 원하는 생선이 들어오면 먼저 알려 드릴게요. / 알림 신청하기
  - 📣 03:10 입항 알림을 보냈어요 / 04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성. 경매 09:00
  - 언제 가면 될까요? / 경매 09:00 · 08:30까지 도착하면 돼요 / 지금 위판장 앞은 비슷 · 실측
  - 탭: 홈 · 들어오는 배 · 알림 · 물어보기

## Creative Direction
- Tone preset: app-store
- Creative direction: 폰 하나로 새벽을 미리 보는 사용 설명서
- Interpretation: 장면마다 기능 캡션 한 줄 + 실제 화면 한 덩어리. 깔끔한 슬라이드(0.35~0.45s), 탭 제스처 시뮬레이션, 과장 없음.
- Angle: 질문("새벽 4시, 어떤 배가 뭘 싣고 올까?")으로 열고 앱이 답하는 구조. 실제 앱의 로딩 → 데이터 도착 → 탭 이동 → 알림 띠까지 실제 동작 순서대로.
- Hook: 네이비 바탕 큰 질문 → 해 뜨듯 아이보리로 밝아지며 ⚓ 배마중
- Outro / punchline: ⚓ 배마중 / 구룡포항 새벽 입항·어종 알림 / 폰 브라우저에서 바로. 설치 없이.
- Avoid: 일반 SaaS 문구, 추상 배경, 앱과 다른 디자인, 전화번호·키·관리자 주소

## Visual Identity
- Background: `#f7f8f5`(아이보리) · 훅 바탕 `#193b50`(딥 네이비)
- Text: `#263238` · muted `#55636b` · 제목·강조 `#193b50` · 입항 시각 `#b4501d`
- Accent: `#f18a54`(선라이즈 오렌지, 장식 전용) · 연바탕 `#fdf0e8` · chip `#edf1ee` · line `#e3e7e4`
- Display font / Body font: 앱은 Pretendard Variable(CDN). 렌더 결정성을 위해 로컬에 설치된 **Noto Sans KR 가변 폰트**를 `assets/fonts/`에 복사해 `@font-face`로 임베드(같은 계열 산세리프).
- Visual references from the project: 라운드 20px 카드, 버튼 18px, 모션 ease `cubic-bezier(0.22,0.25,0,1)` 100~500ms, 탭 상단 오렌지 표시줄(3px), 알림 띠 왼쪽 오렌지 테두리 8px

## Storyboard
`brag-output/brag-plan.md`의 스토리보드가 계약. 요약:
1. 훅 — 3.4s — 질문 두 줄 → 해 뜸 → ⚓ 배마중
2. 폰 등장(홈) — 4s — 오늘 카드 + 칩 3개 순차 등장(4.2/4.7/5.2, 비트), 카드는 실제 '불러오는 중입니다' 상태
3. 곧 들어오는 배 — 5s — 스크롤 업, 로딩 → 데이터 도착, `04:25` 카운트업(7.8→8.4), 세 줄 순차(8.96/9.5/10.0)
4. 알림 신청 — 4s — '알림' 탭 터치 → 화면 전환 → '알림 신청하기' 터치 → 띠 드롭(14.7)
5. 언제 가면 될까요 — 3.5s — 홈 복귀, 네이비 카드 슬라이드업(17.4→17.9)
6. 아웃트로 — 2.2s — 로고·한 줄·CTA

## Audio
- Audio role: warm bed
- Audio arc: 낮게 시작 → 폰 등장에서 또렷 → 띠에서 벨 한 번 → 로고 뒤 페이드아웃
- Music: `assets/music/happy-beats-business-moves-vol-11-by-ende-dot-app.mp3` (114.8 BPM, 번들 프리셋 큐 사용)
- Music treatment: 볼륨 레인 0.22 → 0.38(2s) → 유지 → 20.5s부터 0으로
- Music cue guidance: 비트 그리드 4.23/4.75/5.28(칩), 8.44(숫자 착지), 8.96/9.50/10.01(세 줄), 14.76(띠), 17.91(네이비 카드 착지)
- Audio-reactive treatment: none
- Audio-coupled moments: 칩 3회 drop, 숫자 착지 impactSoft, 탭 2회 click, 띠 impactBell, 로고 impactSoft
- SFX selection guidance: 저위험(HF low) 파일만. `interface/click_003`, `interface/drop_001/002`, `impact/impactSoft_medium_001`, `impact/impactBell_heavy_000`(띠 1회), `casino/card-slide-1`(화면 전환)
- Exact SFX choice: 위 파일을 `assets/sfx/`에 복사해 각각 `<audio>`로 절대 시각에 배치, 볼륨 0.45~0.8

## Hyperframes Instructions
- 단일 paused GSAP 타임라인, `window.__timelines["main"]`, `document.fonts.ready` 뒤 등록
- 루트 클립 3개: `#hook`(0~3.4) · `#app`(3.0~20.2, 폰 프레임 + 캡션) · `#outro`(19.9~22)
- 폰 화면은 390×844 CSS로 앱 레이아웃을 재현하고 정적 `scale(1.75)` 래퍼로 키운다(GSAP는 바깥 래퍼만 움직임)
- 세로 1080×1920, 루트 `data-duration="22"`
- `npx hyperframes check` 오류 0이 게이트
