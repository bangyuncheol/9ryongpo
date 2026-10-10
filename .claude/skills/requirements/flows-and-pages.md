# 사용자 흐름과 페이지·라우트

## 사용자 흐름
설계 정본 `01_설계/01_설계.md` §2.2(어느 새벽)·§6(화면)을 따른다.

## 페이지 목록

| 경로 | 용도 | 접근 권한 |
|---|---|---|
| `/` | 한 페이지 화면(지도·알림함·입항 예보·어종·교통·알림 받기) | 공개 |
| `/?admin=1` | 위 화면 + 데모 진행 막대(조작은 서버가 토큰 검사) | 공개 |

## API 엔드포인트 목록

| 메서드 | 경로 | 용도 | 접근 권한 |
|---|---|---|---|
| GET | `/api/health` | 서버 상태·데이터 적재 수(명부 척수, 실적 행수, 센서 수) | 공개 |
| GET | `/api/place` | 위판장 이름·주소·좌표(E-UM S07_003) | 공개 |
| GET | `/api/fleet` | 어선 명부(번호·이름·어업종류·톤수) | 공개 |
| GET | `/api/sensors` | 교통 센서 목록, 위판장과 거리순 | 공개 |
| GET | `/api/traffic/now?sensor=교통센서3` | 위판장 앞 최근 9시간 교통량 + 24시간 혼잡율 요약. 5분 캐시, 실패 시 503(한국어 문구) | 공개 |
| GET | `/api/today` | 가상 시계 기준 입항 중·입항 완료 배(ETA순), 업종별·전체 어종 추정, 데이터 소스 배지 | 공개 |
| GET | `/api/ships` | 지도용 전체 배 위치와 상태(입항 중/입항/조업·대기) | 공개 |
| GET | `/api/sim/state` | 시계 상태(모드·현재 가상 시각·재생·배속)와 데이터 소스 | 공개 |
| POST | `/api/sim/play?speed=60` | 재생(배속 0~3600) | 공개(데모 진행용) |
| POST | `/api/sim/pause` | 일시정지 | 공개(데모 진행용) |
| POST | `/api/sim/seek?t=03:10` | 가상 시각 이동. 틱·알림 상태 초기화(같은 장면 재연) | 공개(데모 진행용) |
| POST | `/api/sim/feed?mode=sim\|live` | 데이터 소스 전환(데모 7번 장면) | 공개(데모 진행용) |
| GET | `/api/traffic/sensors` | 위판장 1km 안 교통 센서별 지난 1시간 트럭·전체 수(지도 트럭 아이콘). 트럭 위치가 아니라 그 지점을 지난 수 | 공개 |
| GET | `/api/visit?visitor=false` | 방문 권장 문구(경매 시각 + 위판장 앞 실측). 교통 실패 시에도 경매 기준 문구 | 공개 |
| POST | `/api/chat` | 질문창 SSE `{message}` → tool/tool_result/action/answer/error/done 이벤트. IP당 분당 8회, 하루 400회 | 공개 |
| GET | `/api/push/key` | VAPID 공개 키와 구독 가능한 어종 목록 | 공개 |
| POST | `/api/subscribe` | 브라우저 푸시 구독 저장 `{subscription, species}`(species 없으면 전체) | 공개 |
| POST | `/api/unsubscribe` | 구독 삭제 `{endpoint}` | 공개 |
| GET | `/api/notifications` | 화면 안 알림함(가상 시각 이전, 같은 장면 중복 제거) | 공개 |
| POST | `/api/push/test` | 구독한 모든 기기에 시험 알림(리허설 지연 측정) | 공개(데모 진행용) |
