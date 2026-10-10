"""01_설계/01_아키텍처.svg 생성기. 그림을 고칠 때는 이 파일을 고쳐 다시 만든다(손으로 SVG 좌표를 고치지 않는다).

실행(저장소 루트, 맥·윈도우 공통):  python src/docs/make_architecture_svg.py 01_설계/01_아키텍처.svg
"""
import sys
from xml.sax.saxutils import escape as E
W, H = 1200, 960
INK, MUTED, WARN, TEAL, BG = "#1c2733", "#6b7280", "#b9541a", "#0e7c7b", "#faf8f3"
o = []
def t(x, y, s, size=11, w=None, fill=None, anchor="start"):
    a = f' font-weight="{w}"' if w else ""
    f = f' fill="{fill}"' if fill else ""
    o.append(f'<text x="{x}" y="{y}" font-size="{size}"{a}{f} text-anchor="{anchor}">{E(s)}</text>')
def r(x, y, w, h, rx=6, fill="none", stroke="currentColor", sw=1.1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def arrow(d, color="currentColor", marker="ah", dash=None, sw=1.2):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    o.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{ds} marker-end="url(#{marker})"/>')
def card(x, y, w, h, title, sub, body, stroke="currentColor", dash=None):
    r(x, y, w, h, 5, "#ffffff", stroke, 1.1, dash)
    cx = x + w / 2
    t(cx, y + 21, title, 13, 600, anchor="middle")
    t(cx, y + 35, sub, 11, fill=MUTED, anchor="middle")
    t(cx, y + 49, body, 11, anchor="middle")
def panel(x, y, w, h, title, note=None):
    r(x, y, w, h, 6, "none", "currentColor", 1)
    t(x + 14, y + 22, title, 13, 600)
    if note: t(x + w - 14, y + 22, note, 11, fill=MUTED, anchor="end")
def item(x, y, w, name, desc, stroke=MUTED, fill="none"):
    r(x, y, w, 24, 4, fill, stroke, 0.8)
    t(x + 10, y + 16, name, 11, 600)
    t(x + 10 + 7.2 * len(name) + 6, y + 16, desc, 11, fill=MUTED)

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="배마중 아키텍처(2026-10-10 현행): E-UM 실시간 데이터와 해수부 위판 실적 56개월이 대회 제공 GCP VM의 FastAPI 서버에서 피드·규칙·에이전트를 거쳐 SQLite에 기록되고, React 화면과 웹 푸시로 사용자에게 간다. 선박 위치는 FEED 스위치로 실제 API와 시뮬레이터를 바꾼다." style="color:{INK};font-family:IBM Plex Sans KR,Apple SD Gothic Neo,Malgun Gothic,sans-serif">')
o.append(f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker><marker id="ahw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{WARN}"/></marker><marker id="aha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{TEAL}"/></marker></defs>')
r(0, 0, W, H, 0, BG, "none", 0)

# ── 외부 데이터 ─────────────────────────────
r(40, 30, 1120, 132, 8, "none", "currentColor", 1.2)
t(55, 52, "외부 데이터", 13, 600)
t(1145, 52, "E-UM: genix.pohang-eum.kr/dpg · 해수부: data.go.kr 15102791 · OpenAI", 11, fill=MUTED, anchor="end")
X = [60, 214, 368, 522, 676, 830, 984]
card(X[0], 72, 144, 62, "어선 명부", "E-UM S03_001", "202척 · 표지판에 어업종류")
card(X[1], 72, 144, 62, "위판장 좌표", "E-UM S07_003", "35.9895 / 129.5558")
card(X[2], 72, 144, 62, "교통량", "E-UM S07_001·004", "센서3(80m) · 최근 9h")
card(X[3], 72, 144, 62, "혼잡율", "E-UM S07_005", "최근 24h 상대 지수")
card(X[4], 72, 144, 62, "선박 실시간 위치", "E-UM S03_007", "2025-04-27에 멈춤", WARN, "5 3")
card(X[5], 72, 144, 62, "해수부 위탁판매", "15102791 · odcloud", "56개월 · 매월 15일 등록")
card(X[6], 72, 144, 62, "OpenAI", "gpt-6.1-sol", "질문창 · 알림 문장", TEAL)
t(X[0], 152, "기동 시 1회", 10, fill=MUTED); t(X[2] + 78, 152, "요청 시 · 5분 캐시", 10, fill=MUTED)
t(X[4] + 66, 152, "10분 (FEED=live)", 10, fill=WARN, anchor="end"); t(X[5] + 78, 152, "월 1회 스크립트", 10, fill=MUTED)

# ── 서버 ─────────────────────────────────
r(40, 196, 1120, 512, 8, "none", "currentColor", 1.2)
t(55, 220, "FastAPI 서버 · GCP VM", 13, 600)
t(1145, 220, "systemd 상시 실행 · HTTPS: Caddy/터널", 11, fill=MUTED, anchor="end")

panel(60, 250, 350, 170, "collectors/ 수집")
item(74, 282, 322, "fleet.py", "명부 → 어업종류(표지판 정규식)·톤수")
item(74, 312, 322, "traffic.py", "센서3 교통량·혼잡율 실시간 + 5분 캐시")
item(74, 342, 322, "auction.py", "56개월 CSV → 월·위판장·업종·어종 집계")
item(74, 372, 322, "scripts/fetch_auction.py", "새 달 받기(맥·윈도우)")

panel(425, 250, 350, 170, "feed/ 선박 위치 피드", "FEED = live | sim")
item(439, 282, 322, "live.py", "E-UM 10분 · 24h 미갱신이면 예보 중지", WARN)
item(439, 312, 322, "sim.py", "대본 6척 + 실좌표 44척(시드 고정)")
item(439, 342, 322, "clock.py", "가상 시계: 재생·배속·되감기")
t(439, 392, "가짜는 '배의 움직임'뿐. 같은 스키마로 ships_pos에 기록", 10, fill=MUTED)

panel(790, 250, 350, 170, "rules/ 계산 (결정론)")
item(804, 282, 322, "arrival.py", "입항 판정(15km·2kn·35°·거리 감소)·ETA")
item(804, 312, 322, "species.py", "같은 달 여러 해 평균 · 해마다 바뀌는 업종 제외")
item(804, 342, 322, "visit.py", "지금 교통 + 경매 시각(기본 09:00) 권장")
item(804, 372, 322, "brief.py", "알림 문장: LLM → 숫자 검증 실패 시 템플릿")

panel(60, 436, 350, 150, "engine.py 엔진")
t(74, 476, "today · ships: 지금 위치 → 판정 → 어종", 11)
t(74, 494, "tick(실제 3초마다 확인): 지나간 10분 경계마다", 11)
t(88, 510, "ships_pos · forecast · events 기록", 11)
t(74, 528, "새 '입항 중' 배 묶음 → 알림(백그라운드)", 11)
t(74, 548, "실데이터가 24h 넘게 멈추면 예보·알림 중지", 11, fill=WARN)
t(74, 568, "되감기 → reset 이벤트(알림함은 그 이후만)", 10, fill=MUTED)

r(425, 436, 350, 150, 6, "#ffffff", "currentColor", 1.1)
t(439, 458, "SQLite (VM 디스크, 재배포해도 유지)", 13, 600)
t(439, 482, "fleet · ships_pos · auction_stats", 11)
t(439, 500, "forecast · subs · events", 11)
t(439, 524, "source 열로 live / sim 구분", 10, fill=MUTED)
t(439, 540, "스키마 정본 schema.sql (마이그레이션 도구 없음)", 10, fill=MUTED)
t(439, 556, "명부·실적은 기동 시 다시 채움, 교통은 저장 안 함", 10, fill=MUTED)

panel(790, 436, 350, 150, "agent/ 질문창 (tool calling)")
item(804, 466, 322, "tools.py", "도구 6개: 예보·어종·교통·권장·과거 실적·알림")
item(804, 496, 322, "chat.py", "SSE 스트리밍 · 이전 2개 질문 맥락")
t(804, 540, "LLM 실패 → 간단 모드(낱말 규칙, 같은 도구)", 10, fill=TEAL)
t(804, 556, "숫자는 도구에서만 · 호출 제한(분당 8, 하루 400)", 10, fill=MUTED)
t(804, 572, "데이터 소스는 말하지 않음(화면 배지가 표시)", 10, fill=MUTED)

r(60, 600, 715, 94, 6, "none", "currentColor", 1)
t(74, 622, "api/ 라우트 (모두 /api/…)", 13, 600)
t(74, 644, "/today  /ships  /traffic/now  /visit  /place  /notifications  /chat (SSE)", 11)
t(74, 662, "/push/key  /subscribe  /unsubscribe", 11)
t(74, 682, "관리자 토큰: /sim/state·play·pause·seek·feed  /push/test   ·   / ← Vite dist 정적 서빙", 11, fill=WARN)

r(790, 600, 350, 94, 6, "#ffffff", "currentColor", 1.1)
t(804, 622, "push.py 웹 푸시 (VAPID)", 13, 600)
t(804, 644, "구독 조건(어종) 매칭 → 발송, 만료 구독 삭제", 11)
t(804, 662, "발송 기록 = 화면 알림함(최근 5건)", 11)
t(804, 682, "제목 '배마중 · 구룡포 입항 예보'", 10, fill=MUTED)

# ── 화면 ─────────────────────────────────
r(40, 740, 1120, 158, 8, "none", "currentColor", 1.2)
t(55, 762, "Vite + React SPA (PWA) · 배마중", 13, 600)
t(1145, 762, "구룡포 새벽 입항·어종 알림 · 갤럭시 크롬 · 폰 폭 우선 · One UI · 모드 구분 없이 한 화면", 11, fill=MUTED, anchor="end")
C = [(60, "지도 (카카오맵)", "고정 · 범례 · 실패 시 Leaflet"), (240, "알림", "알림 켜기 + 보낸 알림"),
     (420, "오늘 입항 예보", "척별 ETA · 5척 + 더보기"), (600, "오늘 뭐가 들어오나", "지금 들어오는 배 N척 기준"),
     (780, "위판장 앞 지금", "실측 교통 · 도착 권장"), (960, "물어보기", "조회 기록 · 최근 3개")]
for x, a, b in C:
    r(x, 778, 170, 52, 5, "#ffffff", "currentColor", 1.1)
    t(x + 85, 799, a, 12, 600, anchor="middle"); t(x + 85, 816, b, 10, fill=MUTED, anchor="middle")
t(60, 852, "오른쪽 위 배지: 선박 위치 시뮬레이션 / 실시간 / 미갱신", 11)
t(60, 870, "?admin=1 → 진행 막대(관리자 토큰): 03:00·03:10·재생·일시정지·실데이터 전환·시험 알림", 11, fill=WARN)
t(60, 888, "폰: 하단 바(알림 받기 · 물어보기) · 600px 이상 두 칸(42:58), 960px 이상 38:62", 10, fill=MUTED)

# ── 화살표 ───────────────────────────────
# 명부·위판장·교통량·혼잡율 → 한 줄로 모아 collectors/
for x in (X[0], X[1], X[2], X[3]):
    o.append(f'<path d="M{x+72} 134 V172" fill="none" stroke="currentColor" stroke-width="1.2"/>')
o.append(f'<path d="M{X[0]+72} 172 H{X[3]+72}" fill="none" stroke="currentColor" stroke-width="1.2"/>')
arrow("M380 172 V248")
# 해수부 → 저장소 CSV → collectors/
arrow(f"M{X[5]+72} 134 V184 H395 V248")
# 선박 위치 → feed/
arrow(f"M{X[4]+72} 134 V248", WARN, "ahw", "5 3")
# OpenAI ↔ agent/
arrow(f"M{X[6]+72} 134 V170 H1150 V500 H1142", TEAL, "aha")
t(1146, 186, "tool calling", 10, fill=TEAL, anchor="end")
arrow("M235 420 V434")            # collectors → engine
arrow("M600 420 V434")            # feed → SQLite(ships_pos)
arrow("M410 511 H423")            # engine → SQLite
arrow("M790 511 H777")            # agent → SQLite
arrow("M965 420 V434", TEAL, "aha")
t(972, 431, "도구가 rules 호출", 10, fill=TEAL)
arrow("M235 586 V598")            # engine → api
arrow("M405 586 V593 H782 V647 H788")   # engine → push (칸 사이 빈 공간)
arrow("M418 694 V738")            # api → 화면
t(426, 722, "JSON · SSE", 10, fill=MUTED)
arrow("M965 694 V738")            # push → 화면
t(973, 722, "웹 푸시 → 서비스 워커", 10, fill=MUTED)

t(600, 935, "가짜는 '배의 움직임'(sim)뿐. 어선 명부·위판장·교통·위판 실적 56개월은 실데이터. 숫자는 규칙이 내고 LLM은 문장만 쓴다. (2026-10-10 현행)", 11, fill=MUTED, anchor="middle")
o.append("</svg>")
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(o))
print("ok", len("\n".join(o)))
