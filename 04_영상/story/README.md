# 배마중 취재영상 (왜 만들었나)

기능 소개 영상(`../final/`)과 짝을 이루는 두 번째 영상. 위판장 두 번 방문 브이로그 + 몰래 찍은 인터뷰(추적 60분 톤)로 "어획량은 매일 다르고, 배는 다 채워야 들어온다 → 새벽까지 아무도 모른다"는 문제를 제기한다. 1분 6초, 로고 없이 떠나는 브이로그 페이드아웃으로 끝난다.

| 순서 | 내용 |
|---|---|
| open | 4칸(소리는 네 칸 모두): 위는 방문 인사(위치 핀 '활어 위판장'·'구룡포 수협 위판장'), 아래는 경매장 분위기(왼쪽: 첫 방문 넓은 구도, 오른쪽: 두 번째 방문 부두·얼굴 모자이크). 한가운데 "구룡포 수협 위판장 도착" |
| q1 → m1a·m1b·m2 | "의문 1." → 경매 중매상 답변만 컷 편집(화면 전체 흐림·음성변조). 우리 질문은 말소리 없이 자막에 [인터뷰브릿지] 이름표로(답변 이름표와 왼쪽 끝 맞춤) |
| q2 → p1a·p1b·p2 | "의문 2." → 수협 판매과 직원 답변만 컷 편집(음성변조), 질문도 같은 방식 |
| end | 결론 카드 "양은 매일 다르고, 배는 다 채워야 들어온다. 새벽까지, 아무도 모른다." |
| leave | 떠나며 소감(차 안), 끝 1.5초 화면·소리·자막 함께 페이드아웃 |

- 색은 서비스 색(`src/web/src/v4/v4.css` primary `#1a7f8a`·brand `#073f4c`). 질문자 이름표는 '인터뷰브릿지'.
- 원본 영상 9개는 git 밖(오너 OneDrive). 파일 이름은 `timeline.json` 의 `src`.
- 인터뷰 자막 문장은 오너가 준 문장. 컷 구간(in/out)은 소음 속 단어 시각(whisper-1)으로 잡은 것이라 말 앞뒤가 조금 잘리면 timeline.json 에서 0.1초 단위로 조정.

## 다시 만들기

```
cd 04_영상/story
uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless python prep.py <원본 폴더> <blaze_face_short_range.tflite>
python build.py                      # NOTO_KR_TTF=<NotoSansKR[wght].ttf> 를 주면 글꼴 서브셋 갱신
cd composition
npx --yes hyperframes@0.8.146 check
npx --yes hyperframes@0.8.146 render --quality looks --output ../배마중_문제인식영상.mp4
```
