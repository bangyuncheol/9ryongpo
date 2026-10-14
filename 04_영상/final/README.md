# 배마중 소개영상 최종 조립

실제 촬영분 `04_영상/배마중_소개영상.mp4`(94초, 720p HEVC) 위에 demo 의 그래픽(앱 화면·통화 처리 화면·자막·아웃트로)을 얹는다. 가로 1920×1080, 총 99초(촬영분 91초 + 아웃트로 8초).

## 구조

| 구간 | 절대 초 | 화면 |
|---|---|---|
| 새벽·하소연·청년 등장 | 0 ~ 19.4 | 촬영분 전체 + 자막 |
| 앱 설명 | 19.4 ~ 35.2 | **청년 왼쪽 · 그래픽 오른쪽**. 시작 1초 줌인(1.06배, 기준점 22% 52%), 끝 1초 줌아웃 |
| 허탕·침침·전화로도 | 35.2 ~ 49.0 | 촬영분 전체 + 자막 |
| 전화 | 49.0 ~ 90.0 | **할아버지 오른쪽 · 그래픽 왼쪽**. 1.2초 줌인 1.20배, 기준점을 화면 왼쪽 끝(0% 35%)에 두어 할아버지가 오른쪽으로 밀리게. **끝에 줌아웃 없이** 그대로 페이드(10/13 오너) |
| 페이드아웃 | 90.0 ~ 91.0 | 1초 검정으로 |
| 아웃트로 | 91.0 ~ 99.0 | 앱 아이콘 + 워드마크 · 'WEB / APP / 전화 모두 가능합니다' · WEB QR(bmj.kr)·APP QR(APK 릴리스)·전화번호 · 아래 검정 띠에 E-UM 디지털 트윈 포항 로고. QR을 찍을 시간이 있게 8초(10/13 오너) |

- 자막은 촬영 음성을 whisper-1(단어 타임스탬프)로 받아쓴 뒤 gpt-4o-transcribe 로 교차 확인해 `timeline.json` `subtitles` 에 절대 초로 적었다. 대사는 **실제로 말한 대로**(원래 대본과 다른 부분 포함).
- 통화 패널의 AI 문장은 촬영 때 폰에서 재생된 TTS 가 실제로 말한 시각(`call.events[].sents[].t`)에 한 문장씩 뜬다. 사람 대사는 자막으로, AI 대사는 패널로.
- **촬영분의 할아버지 머리는 백발 처리본**(10/13 오너): `hair_white.py`로 원본 `assets/live/footage_orig.mp4` → `footage.mp4`. 촬영분을 바꾸면 변환 뒤 이 스크립트를 다시 돌린다.
- **폰 화면은 실제 앱(버전 4) 캡처**(`assets/app/home.png`·`home-scrolled.png`·`alerts.png`·`toast.png`, 390×844 의 2배). 로컬 서버를 시연 03:10 으로 맞추고(`POST /api/sim/seek?t=03:10`) 헤드리스 크롬(playwright, 3배)으로 찍었다. 앱 화면이 바뀌면 다시 찍어 바꾼다 — 손가락·강조 테두리 좌표는 `build.py` 의 `TAB_*`·`BTN_*`·`HL_*`.
- API 그래픽: E-UM 줄은 **pohang-eum.kr/data 의 API 이름 그대로**(서버 `eum.py` 가 부르는 6종: 구룡포항_선박 실시간 위치 정보_전체 · 구룡포항_선박 기본정보_전체 · 구룡포 수산물 위탁판매장 정보 · 전체 교통감시 장비 정보 목록 · 시간대별/차종별 교통량 통계 · 시간대별 교통 혼잡율, 10/13 확인). 줄마다 이름 + 쓰임 두 단. 앱 구간은 E-UM 6종 · 외부 API 4종(OpenAI·카카오·웹 푸시·OpenStreetMap) 두 장이 폰 높이를 채우고 → 배마중 서버('API 데이터 기반 정보제공 및 대화') → 폰(`FLOWS_B`). 전화 구간은 E-UM 6종 · 전화 외부 API 4종(OpenAI·ClawOps 070·NAVER CLOVA Speech gRPC·Gemini TTS) 두 장이 통화 카드 높이를 채우고, 쓰는 줄에서 신호가 나간다(`FLOWS_F`).
- 아이콘은 각 서비스 사이트 파비콘(`assets/icons/`: pohang-eum.kr, clova.ai, gemini.google.com, chatgpt.com(cdn.oaistatic.com), claw-ops.com, openstreetmap.org, developers.kakao.com). 웹 푸시·전화는 앱의 선 아이콘(`Icon.tsx` 경로). 이모지는 쓰지 않는다.
- 브랜드 그림은 웹 앱 것 그대로(`assets/brand/icon.png`·`wordmark.png` = `src/web/public/`). 자막 '배마중'은 `timeline.json` 의 `wordmark: true` 줄에서 워드마크 그림으로 바뀐다. 자막 워드마크는 흰 배경 없이 흰 테두리만. 이름표(청년·할아버지) 바탕은 워드마크 청록 `#073f4c`, 글자는 흰색(10/13 오너). QR은 `assets/brand/qr-web.svg`·`qr-apk.svg`(segno 로 만들고 viewBox 추가: `uvx segno --scale 10 --border 2 --error m -o qr-web.svg https://bmj.kr`).
- 배경음악은 `music.file`. 영상(97초)보다 짧은 곡은 `ffmpeg acrossfade` 로 이어 붙여 100초로 만든 파일을 쓴다(`happy-beats-loop100.mp3`).

## 다시 만들기

```
cd 04_영상/final
python build.py                      # timeline.json → composition/index.html (+ 폰트 서브셋)
                                     # 맥: NOTO_KR_TTF=<구글 폰트 NotoSansKR[wght].ttf> python build.py
cd composition
npx hyperframes check                # 오류 0 이어야 함(대비 경고 8개는 앱 목업 색이라 무시)
npx hyperframes render --quality looks --output ../배마중_소개영상_최종.mp4
```

촬영분을 바꾸면 먼저 변환한다(1080p 30fps H.264, 음량 -16 LUFS):

```
ffmpeg -i 원본.mp4 -vf "scale=1920:1080:flags=lanczos" -r 30 -c:v libx264 -crf 18 -pix_fmt yuv420p -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -movflags +faststart composition/assets/live/footage.mp4
```

## 바꿔도 되는 것 (`timeline.json`)

- `subtitles[]` — `t`·`end`(절대 초)·`who`·`text`. 분할 구간은 `side: left|right` 로 사람이 있는 쪽 띠에 놓인다.
- `app.beats` — 폰 화면 단계(홈·입항 카드·알림 탭·푸시 띠·출발 카드·퇴장)가 시작되는 절대 초.
- `app.zoom`·`call.zoom` — 줌 배율·기준점·길이.
- `call.events[]` — 통화 패널 대사와 시각. `tools.gap` 은 도구 호출 줄 간격.
- `music.level`(본편)·`level_outro`(아웃트로). 촬영 대사가 묻히면 `level` 을 0.10 으로.
- `footage.fade_start`·`footage.end` — 페이드 시작과 검정 완료 시각. `outro.duration`.

## 파일

```
final/
  timeline.json      장면표(절대 초)
  build.py           timeline.json → composition/index.html
  hair_white.py      촬영분 할아버지 머리 백발 처리(footage_orig.mp4 → footage.mp4)
  README.md          이 문서
  composition/
    index.html       생성물(직접 고치지 말 것)
    assets/live/footage.mp4        백발 처리한 촬영분(git 제외). footage_orig.mp4 가 변환만 한 원본
    assets/app/      실제 앱 캡처(폰 화면)   assets/icons/  서비스 파비콘   assets/brand/  아이콘·워드마크·E-UM 로고
    assets/music, sfx, fonts  demo 와 동일(CC0 번들)
```
