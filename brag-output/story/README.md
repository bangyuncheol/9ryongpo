# 배마중 취재영상 (왜 만들었나)

기능 소개 영상(`../final/`)과 짝을 이루는 두 번째 영상. 위판장 두 번 방문 브이로그 + 몰래 찍은 인터뷰(추적 60분 톤)로 "어획량은 매일 다르고, 배는 다 채워야 들어온다 → 새벽까지 아무도 모른다"는 문제를 제기한다. 약 2분(촬영분 113.6초 + 아웃트로 5.5초).

| 순서 | 내용 |
|---|---|
| cold | 검은 카드 "경북 포항, 구룡포항." |
| v1a·v1b | 첫 방문 인사 · "문제점을 한번 찾아보도록" |
| mont1~3 | 첫 방문 분위기(폰을 눕혀 찍은 넓은 구도, 회전 보정) + 캡션 |
| v2 · dock | 두 번째 방문 + 홍게 하역(얼굴 모자이크) |
| q1 → i2a~d | "의문 1. 들어오는 양은 매일 같을까?" → 상인 인터뷰(얼굴 모자이크·음성변조) + 위판 실적 한 줄 |
| q2 → s1a~c | "의문 2. 그럼 배는 언제 들어오나?" → 판매과 인터뷰(음성변조) |
| end | 결론 카드 → "그래서 우리는 배마중을 만들었다." |
| leave | 떠나며 소감(차 안) |
| outro | 아이콘·워드마크·bmj.kr |

- 원본 영상 9개는 git 밖(오너 OneDrive). 파일 이름은 `timeline.json` 의 `src`.
- 인터뷰 자막은 위판장 소음 속 받아쓰기(whisper-1 + gpt-4o-transcribe 교차)라 **오너 확인 필요**.
- 데이터 한 줄 "하루 위판량 0t ~ 61t"은 `data/auction/구룡포수협_2025-10.csv` 일별 위판중량 합계(최소 0.0t, 최대 61.4t).

## 다시 만들기

```
cd brag-output/story
uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless python prep.py <원본 폴더> <blaze_face_short_range.tflite>
python build.py                      # NOTO_KR_TTF=<NotoSansKR[wght].ttf> 를 주면 글꼴 서브셋 갱신
cd composition
npx --yes hyperframes@0.8.146 check
npx --yes hyperframes@0.8.146 render --quality looks --output ../배마중_취재영상.mp4
```
