# 배마중 취재영상 (왜 만들었나)

기능 소개 영상(`../final/`)과 짝을 이루는 두 번째 영상. 위판장 두 번 방문 브이로그 + 몰래 찍은 인터뷰(추적 60분 톤)로 "어획량은 매일 다르고, 배는 다 채워야 들어온다 → 새벽까지 아무도 모른다"는 문제를 제기한다. 1분 26초, 로고 없이 떠나는 브이로그 페이드아웃으로 끝난다.

| 순서 | 내용 |
|---|---|
| open | 4칸: 위는 첫 번째·두 번째 방문 인사(소리는 첫 방문), 아래는 경매장 분위기(폰을 눕혀 찍은 넓은 구도, 회전 보정). 한가운데 "(새벽 경매, 오늘은 뭐가 얼마나 들어올까?)" |
| q1 → i2a~d | "의문 1." → 경매 참여 상인 인터뷰(화면 전체 흐림·음성변조) |
| q2 → s1a~c | "의문 2." → 수협 판매과 직원 인터뷰(음성변조) |
| end | 결론 카드 "양은 매일 다르고, 배는 다 채워야 들어온다. 새벽까지, 아무도 모른다." |
| leave | 떠나며 소감(차 안), 끝 1.5초 페이드아웃 |

- 색은 서비스 색(`src/web/src/v4/v4.css` primary `#1a7f8a`·brand `#073f4c`). 질문자 이름표는 '인터뷰브릿지'.
- 원본 영상 9개는 git 밖(오너 OneDrive). 파일 이름은 `timeline.json` 의 `src`.
- 인터뷰 자막은 위판장 소음 속 받아쓰기(whisper-1 + gpt-4o-transcribe 교차)라 **오너 확인 필요**.

## 다시 만들기

```
cd brag-output/story
uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless python prep.py <원본 폴더> <blaze_face_short_range.tflite>
python build.py                      # NOTO_KR_TTF=<NotoSansKR[wght].ttf> 를 주면 글꼴 서브셋 갱신
cd composition
npx --yes hyperframes@0.8.146 check
npx --yes hyperframes@0.8.146 render --quality looks --output ../배마중_취재영상.mp4
```
