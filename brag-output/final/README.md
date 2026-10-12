# 배마중 소개영상 최종 조립

실제 촬영분 `brag-output/배마중_소개영상.mp4`(94초, 720p HEVC) 위에 demo 의 그래픽(앱 화면·통화 처리 화면·자막·아웃트로)을 얹는다. 가로 1920×1080, 총 97초(촬영분 91초 + 아웃트로 6초).

## 구조

| 구간 | 절대 초 | 화면 |
|---|---|---|
| 새벽·하소연·청년 등장 | 0 ~ 19.4 | 촬영분 전체 + 자막 |
| 앱 설명 | 19.4 ~ 35.2 | **청년 왼쪽 · 그래픽 오른쪽**. 시작 1초 줌인(1.06배, 기준점 22% 52%), 끝 1초 줌아웃 |
| 허탕·침침·전화로도 | 35.2 ~ 49.0 | 촬영분 전체 + 자막 |
| 전화 | 49.0 ~ 90.0 | **할아버지 오른쪽 · 그래픽 왼쪽**(demo 좌표를 좌우 반전). 줌인/줌아웃 동일 |
| 페이드아웃 | 90.0 ~ 91.0 | 1초 검정으로 |
| 아웃트로 | 91.0 ~ 97.0 | 로고 · 한 줄 설명 · 대회명 |

- 자막은 촬영 음성을 whisper-1(단어 타임스탬프)로 받아쓴 뒤 gpt-4o-transcribe 로 교차 확인해 `timeline.json` `subtitles` 에 절대 초로 적었다. 대사는 **실제로 말한 대로**(원래 대본과 다른 부분 포함).
- 통화 패널의 AI 문장은 촬영 때 폰에서 재생된 TTS 가 실제로 말한 시각(`call.events[].sents[].t`)에 한 문장씩 뜬다. 사람 대사는 자막으로, AI 대사는 패널로.
- 배경음악은 `music.file`. 영상(97초)보다 짧은 곡은 `ffmpeg acrossfade` 로 이어 붙여 100초로 만든 파일을 쓴다(`happy-beats-loop100.mp3`).

## 다시 만들기

```
cd brag-output/final
python build.py                      # timeline.json → composition/index.html (+ 폰트 서브셋)
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
  README.md          이 문서
  composition/
    index.html       생성물(직접 고치지 말 것)
    assets/live/footage.mp4   변환한 촬영분(git 제외)
    assets/music, sfx, fonts  demo 와 동일(CC0 번들)
```
