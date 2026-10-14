"""timeline.json → composition/index.html 생성기 (배마중 소개영상 최종본, 가로 1920×1080).

실제 촬영분 한 개(footage.mp4, 할아버지 머리는 백발 처리본)를 바닥에 깔고, 그 위에
  · 자막(촬영 음성 기준 절대 초). '배마중'은 워드마크 그림으로(timeline 의 wordmark 표시)
  · 앱 설명 구간: 그래픽 오른쪽(청년은 왼쪽) + 살짝 줌인/줌아웃. 폰 화면은 실제 앱(버전 4) 캡처(assets/app/*.png)
      API 그래픽은 두 묶음 — E-UM 6종(pohang-eum.kr/data 이름 그대로) · 외부 API 4종(OpenAI·카카오·웹 푸시·OpenStreetMap). 폰 높이를 채우고 화면마다 쓰는 API 에 신호가 간다
  · 전화 구간:   그래픽 왼쪽(할아버지는 오른쪽) + 줌인(끝에 줌아웃 없음)
      E-UM 6종 + 전화 외부 API 4종(OpenAI · ClawOps 070 · NAVER CLOVA Speech gRPC · Gemini TTS). 통화 카드 높이를 채운다
  · 1:30 부터 1초 페이드아웃 → 아웃트로(앱 아이콘 + 워드마크 · WEB/APP QR·전화번호, 아래에 E-UM 디지털 트윈 포항 로고)
를 얹는다. 시각·자막·통화 대사는 timeline.json 에서만 고친다. 이 파일은 레이아웃·모션만 가진다.
아이콘은 각 서비스 사이트의 파비콘(assets/icons/), 브랜드 그림은 웹 앱의 것(assets/brand/ = src/web/public/).

실행: python build.py  →  cd composition && npx hyperframes check && npx hyperframes render --quality looks --output ../배마중_소개영상_최종.mp4
폰트: demo/build.py 와 같은 방식으로 Noto Sans KR 서브셋(윈도우 원본이 있을 때만 갱신).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
COMP = HERE / "composition"
OUT = COMP / "index.html"
FONT_SRC = Path(os.environ.get("NOTO_KR_TTF", r"C:/Windows/Fonts/NotoSansKR-VF.ttf"))   # 맥은 구글 폰트 NotoSansKR[wght].ttf 경로를 넘긴다
FONT_SUB = COMP / "assets" / "fonts" / "NotoSansKR-subset.ttf"
W, H = 1920, 1080
BAND = 864            # 사람이 있는 쪽 폭(px). 나머지 1056px 이 그래픽
PANEL = W - BAND      # 1056

cfg = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
FOOT = cfg["footage"]
APP, CALL = cfg["app"], cfg["call"]
FADE_T, FOOT_END = float(FOOT["fade_start"]), float(FOOT["end"])
OUTRO_T = FOOT_END
TOTAL = round(OUTRO_T + float(cfg["outro"]["duration"]), 3)
fmt = lambda x: f"{x:.3f}".rstrip("0").rstrip(".")
music = cfg["music"]
phone_no = escape(cfg.get("phone_number_text", "070-5276-7121"))

# 브랜드 색(src/web/src/v4/v4.css 의 토큰과 같게)
BRAND = "#073f4c"      # 워드마크 청록
PRIMARY = "#0c5560"    # 깊은 청록(제목·행동)
CORAL = "#cc3d29"      # 입항 시각·강조
SUNRISE = "#e8604c"    # 장식(점·띠)
INK = "#10232b"
MUTED = "#4f6169"
MINT = "#e0eceb"
SURFACE = "#f6f8f8"
PAGE = "#eef3f2"

ICON = "assets/brand/icon.png"
WORDMARK = "assets/brand/wordmark.png"
DT_LOGO = "assets/brand/dt-pohang.png"
BELL_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10.268 21a2 2 0 0 0 3.464 0M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/></svg>')
PHONE_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/></svg>')


# ---------------------------------------------------------------- 자막
def sub_text(ln) -> str:
    text = escape(ln["text"])
    if ln.get("wordmark"):   # '배마중' 글자를 시그니처 워드마크 그림으로
        text = text.replace("배마중", f'<img class="wm" src="{WORDMARK}" alt="배마중">')
    return text


def subtitle_tags() -> str:
    html = []
    for j, ln in enumerate(cfg["subtitles"]):
        side = ln.get("side", "")
        html.append(
            f'      <div id="sub-{j}" class="clip sub{(" " + side) if side else ""}" data-start="{fmt(ln["t"])}" '
            f'data-duration="{fmt(ln["end"] - ln["t"])}" data-track-index="1" data-layout-allow-caption-zone>\n'
            f'        <div class="band"><span class="who">{escape(ln["who"])}</span><span class="say">{sub_text(ln)}</span></div>\n'
            f'      </div>')
    return "\n".join(html)


# ---------------------------------------------------------------- 통화 패널
def call_tags() -> tuple[str, str, list[tuple[str, str, float, float]]]:
    """통화 패널 HTML, 절대 시각으로 쓴 GSAP 코드, 효과음 목록."""
    items, js, sfx = [], [], []
    n = 0
    for e in CALL["events"]:
        if e["who"] == "tools":
            gap = float(e.get("gap", 0.55))
            steps = "".join(f'<li id="tool-{k}"><span class="chk">✓</span>{escape(s)}</li>' for k, s in enumerate(e["steps"]))
            items.append(f'<ul id="tools" class="tools">{steps}</ul>')
            js.append('        gsap.set("#tools li", { opacity: 0, x: -14 }); gsap.set("#tools .chk", { scale: 0 });')
            for k in range(len(e["steps"])):
                t0 = e["t"] + gap * k
                js.append(f'        tl.to("#tool-{k}", {{ opacity: 1, x: 0, duration: 0.3, ease: OUI }}, {fmt(t0)});')
                js.append(f'        tl.to("#tool-{k} .chk", {{ scale: 1, duration: 0.25, ease: "back.out(2)" }}, {fmt(t0 + 0.35)});')
                sfx.append((f"sfx-tool{k}", "interface/drop_001.ogg", t0, 0.35))
            continue
        bid = f"bub-{n}"; n += 1
        if e["who"] == "ai":
            sents = e["sents"]
            spans = " ".join(f'<span class="s">{escape(s["text"])}</span>' for s in sents)
            items.append(f'<div id="{bid}" class="bub ai"><img class="av" src="{ICON}" alt=""><p>{spans}</p></div>')
            js.append(f'        tl.fromTo("#{bid}", {{ y: 18, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: OUI }}, {fmt(e["t"] - 0.15)});')
            if len(sents) > 1:  # TTS 가 실제로 말한 시각에 한 문장씩
                js.append(f'        gsap.set("#{bid} .s", {{ opacity: 0 }});')
                for k, s in enumerate(sents):
                    js.append(f'        tl.to("#{bid} .s:nth-child({k + 1})", {{ opacity: 1, duration: 0.25 }}, {fmt(s["t"])});')
            if sum(len(s["text"]) for s in sents) > 40 and n > 1:
                sfx.append(("sfx-answer", "impact/impactBell_heavy_000.ogg", e["t"], 0.4))
        else:
            items.append(f'<div id="{bid}" class="bub user"><p>{escape(e["text"])}</p><span class="stt">받아쓰기</span></div>')
            js.append(f'        tl.fromTo("#{bid}", {{ y: 18, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: OUI }}, {fmt(e["t"] + 0.5)});')
    return "\n            ".join(items), "\n".join(js), sfx


# ---------------------------------------------------------------- 데이터 흐름 그래픽
# 앱 구간(오른쪽 패널): API 묶음 두 장 → 배마중 서버 → 폰
NODE_X, NODE_W = 880, 352
HUB = (1266, 552, 186, 116)                    # 배마중 서버 허브 (left, top, w, h)
PHONE_LEFT, PHONE_TOP = 1486, 186
ROW_H, HEAD_H, PAD_V = 70, 52, 10              # 두 묶음(10줄)이 폰 높이(864px)를 채우게
# (id, 머리 아이콘, 머리 글, 부제, [(아이콘 또는 None, 줄 글, 쓰임)])
# E-UM 줄 글은 pohang-eum.kr/data 의 API 이름 그대로(서버 eum.py 가 부르는 6종, 10/13 확인)
EUM_ROWS = [
    ("구룡포항_선박 실시간 위치 정보_전체", "배 위치·속도 → 입항 예보"),
    ("구룡포항_선박 기본정보_전체", "어선명·어업방법 → 어종 추정"),
    ("구룡포 수산물 위탁판매장 정보", "위판장 위치"),
    ("전체 교통감시 장비 정보 목록", "위판장 앞 교통센서"),
    ("시간대별/차종별 교통량 통계", "센서별 시간당 통행량"),
    ("시간대별 교통 혼잡율", "혼잡 지수"),
]
EUM_GROUP = ("eum", "assets/icons/eum.png", "E-UM 디지털 트윈 포항", "API 6종 · pohang-eum.kr", [(None, r, u) for r, u in EUM_ROWS])
GROUPS_B = [
    EUM_GROUP,
    ("ext", None, "외부 API", "4종", [("assets/icons/openai.png", "OpenAI", "질문창 대화 · 도구 호출"),
                                     ("assets/icons/kakao.png", "카카오 로컬·모빌리티 길찾기", "출발지 → 위판장 소요 시간"),
                                     ("bell", "웹 푸시 (VAPID)", "입항 알림"), ("assets/icons/osm.png", "OpenStreetMap", "지도 타일")]),
]
TOP_B, GAP_B = PHONE_TOP, 18


def group_height(rows): return HEAD_H + PAD_V + len(rows) * ROW_H + PAD_V


def row_icon(ic):
    if ic is None: return '<span class="ri dot"></span>'
    if ic == "bell": return f'<span class="ri svg">{BELL_SVG}</span>'
    return f'<img class="ri" src="{ic}" alt="">'


def group_html(prefix, groups, left, w, top, gap):
    out, pos = [], {}
    y = top
    for gid, hic, name, sub, rows in groups:
        h = group_height(rows)
        head_ic = f'<img class="gi" src="{hic}" alt="">' if hic else '<span class="gi cloud"></span>'
        lines = "".join(f'<li id="{prefix}-{gid}-{k}">{row_icon(ic)}<span class="rt"><b>{escape(tx)}</b><small>{escape(use)}</small></span></li>'
                        for k, (ic, tx, use) in enumerate(rows))
        out.append(f'<div id="{prefix}-{gid}" class="group" style="left:{left}px; top:{y}px; width:{w}px; height:{h}px;">'
                   f'<div class="gh">{head_ic}<span class="gt"><b>{escape(name)}</b><small>{escape(sub)}</small></span></div><ul>{lines}</ul></div>')
        pos[gid] = (y, h)
        y += h + gap
    return "\n        ".join(out), pos


GROUPS_B_HTML, POS_B = group_html("gb", GROUPS_B, NODE_X, NODE_W, TOP_B, GAP_B)
ANC_B = {gid: (NODE_X + NODE_W, y + h // 2) for gid, (y, h) in POS_B.items()}      # 묶음 오른쪽 가장자리
HUB_L, HUB_R = (HUB[0], HUB[1] + HUB[3] // 2), (HUB[0] + HUB[2], HUB[1] + HUB[3] // 2)
PHONE_A = (PHONE_LEFT, 600)

# 전화 구간(왼쪽 패널): 통화 카드가 왼쪽 끝, 묶음 두 장(E-UM 6종 · 전화 외부 API 4종)이 그 오른쪽. 통화 카드 높이를 채운다
CALL_LEFT, CALL_W, CALL_TOP = 16, 600, 176
NODE_X_F, NODE_W_F, TOP_F, GAP_F = 636, 404, CALL_TOP + 6, 18
GROUPS_F = [
    EUM_GROUP,
    ("ext", None, "외부 API", "전화 4종", [("assets/icons/openai.png", "OpenAI", "범위 판정 · 도구 호출"),
                                        ("assets/icons/clawops.svg", "ClawOps 070", "전화 연결 · 통화 음성"),
                                        ("assets/icons/clova.png", "NAVER CLOVA Speech gRPC", "실시간 받아쓰기 · 키워드 부스팅"),
                                        ("assets/icons/gemini.png", "Gemini TTS", "문장 음성 합성")]),
]
GROUPS_F_HTML, POS_F = group_html("gf", GROUPS_F, NODE_X_F, NODE_W_F, TOP_F, GAP_F)
# 줄 왼쪽 가장자리. 신호는 쓰는 줄에서 나간다
row_a = lambda gid, k: (NODE_X_F, POS_F[gid][0] + HEAD_H + PAD_V + k * ROW_H + ROW_H // 2)
OPENAI_F, CLAW_F, CLOVA_F, GEMINI_F = (row_a("ext", k) for k in range(4))
CALL_A = (CALL_LEFT + CALL_W, 560)                                                 # 통화 카드 오른쪽 가장자리


def svg_lines(pairs):
    return "".join(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" />' for a, b in pairs)


LINES_B = svg_lines([(a, HUB_L) for a in ANC_B.values()] + [(HUB_R, PHONE_A)])
LINES_F = svg_lines([(row_a(g, k), CALL_A) for g, k in (("eum", 0), ("eum", 1), ("eum", 4), ("ext", 0), ("ext", 1), ("ext", 2), ("ext", 3))])

bt = APP["beats"]
# (절대 시각, 켜질 줄 id 들, 경로). 줄 id 는 "gb-<묶음>-<번호>"
TO_PHONE_EUM = [(ANC_B["eum"], HUB_L), (HUB_R, PHONE_A)]
TO_PHONE_EXT = [(ANC_B["ext"], HUB_L), (HUB_R, PHONE_A)]
FLOWS_B = [
    (bt["home"] + 1.0, ["gb-eum-0", "gb-eum-1"], TO_PHONE_EUM),          # 선박 위치·어선 명부 → 홈
    (bt["home"] + 1.6, ["gb-ext-3"], TO_PHONE_EXT),                      # 지도 타일(OpenStreetMap)
    (bt["forecast"] + 0.5, ["gb-eum-0", "gb-eum-2"], TO_PHONE_EUM),      # 선박 위치·위판장 → 입항 카드
    (bt["forecast"] + 2.0, ["gb-eum-1"], TO_PHONE_EUM),                  # 어선 명부(어업종류) → 어종 추정
    (bt["alerts"] + 2.0, [], [(PHONE_A, HUB_R)]),                        # 알림 신청 → 서버 저장
    (bt["toast"] - 0.6, ["gb-ext-2"], [(HUB_L, ANC_B["ext"]), (ANC_B["ext"], PHONE_A)]),  # 서버 → 웹 푸시 → 폰(띠)
    (bt["depart"] + 0.8, ["gb-eum-3", "gb-eum-4", "gb-eum-5"], TO_PHONE_EUM),  # 교통 센서·교통량·혼잡율 → 언제 가면 되나
    (bt["depart"] + 1.5, ["gb-ext-1"], TO_PHONE_EXT),                    # 카카오 길찾기
]
cs = float(CALL["start"])
FLOWS_F = [(cs + 0.5, ["gf-ext-1"], [(CLAW_F, CALL_A)])]                 # 전화 연결
for e in CALL["events"]:
    if e["who"] == "ai":
        FLOWS_F.append((e["t"] - 0.6, ["gf-ext-3"], [(GEMINI_F, CLAW_F), (CLAW_F, CALL_A)]))   # 음성 합성 → 통화
    elif e["who"] == "user":
        FLOWS_F.append((e["t"] - 0.1, ["gf-ext-1", "gf-ext-2"], [(CALL_A, CLAW_F), (CLAW_F, CLOVA_F), (CLOVA_F, CALL_A)]))  # 말 → 받아쓰기 → 글
    else:
        gap = float(e.get("gap", 0.55))
        FLOWS_F.append((e["t"] - 0.1, ["gf-ext-0"], [(CALL_A, OPENAI_F), (OPENAI_F, CALL_A)]))   # 판정·도구 호출(OpenAI)
        # 도구 줄 순서: 받아쓰기 · 범위 판정 · 입항 예보(선박 위치) · 어종 추정(선박 기본정보) · 방문 시각(교통량)
        for j, (rid, src) in enumerate((("gf-ext-2", CLOVA_F), ("gf-ext-0", OPENAI_F), ("gf-eum-0", row_a("eum", 0)),
                                         ("gf-eum-1", row_a("eum", 1)), ("gf-eum-4", row_a("eum", 4)))):
            FLOWS_F.append((e["t"] + gap * j + 0.2, [rid], [(src, CALL_A)]))


def flow_js(scene, flows):
    js, dots = [], []
    for k, (t, ids, path) in enumerate(flows):
        hold = 0.5 * len(path) + 0.8
        for rid in ids:
            js.append(f'        lit("#{rid}", {fmt(t)}, {fmt(hold)});')
        tt = t
        for j, (a, b) in enumerate(path):
            did = f"dot-{scene}-{k}-{j}"
            dots.append(f'<span id="{did}" class="dot"></span>')
            js.append(f'        flow("#{did}", [{a[0]}, {a[1]}], [{b[0]}, {b[1]}], {fmt(tt)});')
            if scene == "B" and (b == HUB_L or b == HUB_R or a == HUB_R or a == HUB_L):
                js.append(f'        lit("#hub", {fmt(tt + 0.45)}, 0.6);')
            tt += 0.5
    return "\n".join(js), "".join(dots)


FLOW_JS_B, DOTS_B = flow_js("B", FLOWS_B)
FLOW_JS_F, DOTS_F = flow_js("F", FLOWS_F)

# ---------------------------------------------------------------- 본문 조립
subs_html = subtitle_tags()
call_html, call_js, call_sfx = call_tags()
app_s, app_e = float(APP["start"]), float(APP["end"])
call_e = float(CALL["end"])
end_badge = float(CALL["end_badge_t"])
zA, zC = APP["zoom"], CALL["zoom"]

sfx = [  # (id, 파일, 절대 시각, 볼륨)
    ("sfx-land", "impact/impactSoft_medium_001.ogg", bt["home"] + 0.55, 0.6),
    ("sfx-slide1", "casino/card-slide-1.ogg", bt["forecast"], 0.4),
    ("sfx-num", "impact/impactSoft_medium_001.ogg", bt["forecast"] + 0.6, 0.5),
    ("sfx-tap1", "interface/click_003.ogg", bt["alerts"] + 0.3, 0.7), ("sfx-slide2", "casino/card-slide-1.ogg", bt["alerts"] + 0.35, 0.4),
    ("sfx-tap2", "interface/click_003.ogg", bt["alerts"] + 1.8, 0.7), ("sfx-toast", "impact/impactBell_heavy_000.ogg", bt["toast"], 0.45),
    ("sfx-tap3", "interface/click_003.ogg", bt["depart"], 0.6), ("sfx-slide3", "casino/card-slide-1.ogg", bt["depart"] + 0.05, 0.35),
    ("sfx-depart", "interface/drop_001.ogg", bt["depart"] + 1.3, 0.5),
    ("sfx-connect", "interface/switch_007.ogg", cs + 0.6, 0.5),
    ("sfx-logo", "impact/impactSoft_medium_001.ogg", OUTRO_T + 0.4, 0.6),
] + call_sfx
sfx_html = "\n".join(f'      <audio id="{i}" src="assets/sfx/{f}" data-start="{fmt(s)}" data-track-index="{30 + k}" data-volume="{v}"></audio>'
                     for k, (i, f, s, v) in enumerate(sfx))
lv, lo = music["level"], music["level_outro"]
music_auto = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [
    {"t": 0, "v": 0}, {"t": 1.5, "v": lv},
    {"t": FADE_T, "v": lv}, {"t": FOOT_END, "v": lv * 0.5},
    {"t": OUTRO_T + 0.6, "v": lo}, {"t": TOTAL - 1.5, "v": lo}, {"t": TOTAL, "v": 0}]}]}, ensure_ascii=False)

GLOW = "text-shadow:0 0 14px rgba(255,255,255,0.95), 0 0 4px rgba(255,255,255,0.95), 0 2px 10px rgba(255,255,255,0.9);"
IMG_GLOW = "filter:drop-shadow(0 0 6px rgba(255,255,255,0.95)) drop-shadow(0 0 2px rgba(255,255,255,0.95));"

# 폰 화면(390×844 기준) 안의 좌표: 실제 앱 캡처에서 잰 값
TAB_ALERTS_HOME = (204, 413)      # 홈 화면의 '알림' 탭
BTN_APPLY = (200, 775)            # 알림 장의 '휴대폰 알림 받기'
TAB_SHIPS_ALERTS = (86, 474)      # 알림 장의 '들어오는 배' 탭
HL_NEXT = (16, 446, 358, 196)     # 홈 '다음 배' 카드 (left, top, w, h)
HL_VISIT = (16, 537, 358, 102)    # 스크롤한 홈의 '언제 가면 되나' 카드

HTML = f"""<!doctype html>
<html lang="ko" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <title>배마중 소개영상 · 최종</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Noto Sans KR"; src: url("assets/fonts/NotoSansKR-subset.ttf") format("truetype"); font-weight: 100 900; font-display: block; }}
      :root {{ --page:{PAGE}; --card:#fff; --ink:{INK}; --muted:{MUTED}; --line:#e1e9e8; --chip:#e7eeed; --brand:{BRAND}; --primary:{PRIMARY};
              --coral:{CORAL}; --sunrise:{SUNRISE}; --sunrise-soft:#fdeeea; --mint:{MINT}; --surface:{SURFACE}; --on-primary:#fff; }}
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html, body {{ width:{W}px; height:{H}px; overflow:hidden; background:#000; font-family:"Noto Sans KR", system-ui, sans-serif; color:var(--ink); }}
      #root {{ position:relative; width:100%; height:100%; overflow:hidden; background:#000; }}
      .clip {{ position:absolute; inset:0; }}
      .center {{ text-align:center; }}
      #stage {{ position:absolute; inset:0; overflow:hidden; background:#000; }}
      #footage {{ position:absolute; top:0; left:0; width:{W}px; height:{H}px; object-fit:cover; background:#000; }}
      #fade {{ position:absolute; inset:0; background:#000; opacity:0; }}

      /* 자막: 기본은 가운데, 분할 구간은 사람이 있는 쪽(left/right 864px 띠). 이름표 바탕은 워드마크 청록, 글자는 흰색. 워드마크는 배경 없이 흰 테두리 */
      .sub .band {{ position:absolute; left:0; right:0; bottom:72px; display:flex; justify-content:center; }}
      .sub.left .band {{ right:auto; width:{BAND}px; }}
      .sub.right .band {{ left:1100px; right:24px; }}
      .sub .band > span {{ display:inline-block; }}
      .sub .who {{ background:var(--brand); color:#fff; font-weight:800; font-size:26px; padding:8px 16px; border-radius:12px 0 0 12px; white-space:nowrap; }}
      .sub .say {{ background:rgba(14,26,33,0.82); color:#fff; font-weight:700; font-size:34px; line-height:1.3; padding:8px 22px; border-radius:0 12px 12px 0; max-width:1400px; }}
      .sub.left .say, .sub.right .say {{ max-width:{BAND - 160}px; font-size:30px; }}
      .sub .wm {{ height:1.25em; vertical-align:-0.3em; margin:0 4px; filter:drop-shadow(1.5px 0 0 #fff) drop-shadow(-1.5px 0 0 #fff) drop-shadow(0 1.5px 0 #fff) drop-shadow(0 -1.5px 0 #fff); }}

      /* 브랜드 줄(아이콘 + 워드마크) */
      .brandrow {{ display:flex; align-items:center; justify-content:center; gap:12px; }}
      .brandrow .bi {{ height:56px; width:56px; border-radius:14px; {IMG_GLOW} }}
      .brandrow .bw {{ height:50px; {IMG_GLOW} }}
      .brandrow small {{ font-size:24px; font-weight:600; color:var(--muted); margin-left:6px; {GLOW} }}
      #brand {{ position:absolute; left:{BAND}px; width:{PANEL}px; top:36px; }}
      .cap {{ position:absolute; left:{BAND + 40}px; width:{PANEL - 80}px; top:108px; font-size:40px; font-weight:800; color:var(--brand); letter-spacing:-0.02em; line-height:1.3; {GLOW} }}

      /* 폰 목업: 실제 앱 캡처(390×844) */
      #phone {{ position:absolute; left:{PHONE_LEFT}px; top:{PHONE_TOP}px; width:410px; height:864px; }}
      .frame {{ position:absolute; inset:0; border:10px solid #10232b; border-radius:48px; overflow:hidden; background:#fff; box-shadow:0 24px 50px rgba(7,63,76,0.22); }}
      .screen {{ position:relative; width:390px; height:844px; overflow:hidden; background:var(--page); }}
      .scr {{ position:absolute; left:0; top:0; width:390px; height:844px; }}
      .scr img {{ display:block; width:390px; height:844px; }}
      #toast {{ position:absolute; left:6px; top:0; width:378px; }}
      #toast img {{ display:block; width:378px; }}
      .hl {{ position:absolute; border:3px solid var(--coral); border-radius:20px; box-shadow:0 0 0 4px rgba(204,61,41,0.18); opacity:0; }}
      #hl-next {{ left:{HL_NEXT[0]}px; top:{HL_NEXT[1]}px; width:{HL_NEXT[2]}px; height:{HL_NEXT[3]}px; }}
      #hl-visit {{ left:{HL_VISIT[0]}px; top:{HL_VISIT[1]}px; width:{HL_VISIT[2]}px; height:{HL_VISIT[3]}px; }}
      #finger {{ position:absolute; left:0; top:0; width:44px; height:44px; margin:-22px 0 0 -22px; border-radius:50%; background:rgba(12,85,96,0.32); border:2px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.25); }}

      /* 왼쪽 패널(전화 구간) */
      #brand2 {{ position:absolute; left:0; width:{PANEL}px; top:36px; }}
      #call-cap {{ position:absolute; left:0; width:{PANEL}px; top:104px; font-size:36px; font-weight:800; color:var(--brand); letter-spacing:-0.02em; {GLOW} }}
      #call {{ position:absolute; left:{CALL_LEFT}px; top:{CALL_TOP}px; width:{CALL_W}px; height:874px; border-radius:36px; background:#fff; box-shadow:0 24px 50px rgba(7,63,76,0.18); overflow:hidden; }}
      #call .hd {{ height:120px; background:var(--mint); color:var(--ink); padding:22px 26px; display:flex; align-items:center; justify-content:space-between; }}
      #call .hd .nm {{ display:flex; align-items:center; gap:10px; }} #call .hd .nm img.bi {{ width:44px; height:44px; border-radius:11px; }} #call .hd .nm img.bw {{ height:34px; }}
      #call .hd .no {{ font-size:20px; color:var(--muted); margin-top:6px; font-variant-numeric:tabular-nums; font-weight:600; }}
      #call .hd .st {{ position:relative; width:220px; height:60px; }}
      #call .hd .st > span {{ position:absolute; right:0; top:0; font-size:22px; font-weight:700; color:var(--coral); white-space:nowrap; font-variant-numeric:tabular-nums; }}
      #st-end {{ color:var(--muted) !important; }}
      #call .log {{ padding:16px 28px; display:flex; flex-direction:column; gap:10px; }}
      .bub {{ max-width:520px; display:flex; gap:12px; align-items:flex-start; }}
      .bub p {{ font-size:20px; line-height:1.38; padding:9px 16px; border-radius:20px; }}
      .bub.ai p {{ background:var(--chip); color:var(--ink); border-top-left-radius:6px; }}
      .bub.ai .av {{ flex:0 0 40px; width:40px; height:40px; border-radius:50%; object-fit:cover; }}
      .bub.user {{ align-self:flex-end; flex-direction:column; align-items:flex-end; gap:4px; }}
      .bub.user p {{ background:var(--primary); color:var(--on-primary); border-top-right-radius:6px; }}
      .bub.user .stt {{ font-size:14px; font-weight:700; color:var(--muted); }}
      .tools {{ list-style:none; margin:0 0 0 52px; display:flex; flex-direction:column; gap:6px; }}
      .tools li {{ display:flex; align-items:center; gap:10px; font-size:16px; font-weight:700; color:var(--primary); background:var(--mint); border-radius:10px; padding:6px 12px; width:fit-content; }}
      .tools .chk {{ width:24px; height:24px; border-radius:50%; background:var(--primary); color:#fff; display:grid; place-items:center; font-size:15px; }}

      /* 데이터 흐름 그래픽: API 묶음 카드 */
      .group {{ position:absolute; border-radius:18px; background:rgba(255,255,255,0.94); border:2px solid rgba(255,255,255,0); box-shadow:0 8px 20px rgba(7,63,76,0.16); padding:0 12px {PAD_V}px; overflow:hidden; }}
      .group .gh {{ height:{HEAD_H}px; display:flex; align-items:center; gap:10px; border-bottom:1px solid var(--line); margin-bottom:{PAD_V}px; }}
      .group .gi {{ width:32px; height:32px; border-radius:7px; object-fit:contain; flex:0 0 28px; }}
      .group .gi.cloud {{ background:var(--primary); border-radius:50%; width:14px; height:14px; flex:0 0 14px; margin:0 7px; }}
      .group .gt {{ display:flex; flex-direction:column; line-height:1.15; }}
      .group .gt b {{ font-size:20px; color:var(--brand); }} .group .gt small {{ font-size:14px; color:var(--muted); }}
      .group ul {{ list-style:none; display:flex; flex-direction:column; }}
      .group li {{ height:{ROW_H}px; display:flex; align-items:center; gap:10px; padding:0 8px; border-radius:10px; color:var(--ink); }}
      .group li .rt {{ display:flex; flex-direction:column; gap:3px; line-height:1.2; white-space:nowrap; }}
      .group li b {{ font-size:17px; font-weight:700; letter-spacing:-0.02em; }} .group li small {{ font-size:14px; font-weight:500; color:var(--muted); }}
      .group .ri {{ width:24px; height:24px; flex:0 0 24px; object-fit:contain; border-radius:4px; display:grid; place-items:center; color:var(--primary); }}
      .group .ri.dot {{ width:8px; height:8px; flex:0 0 8px; margin:0 8px; border-radius:50%; background:var(--primary); }}
      .group .ri.svg svg {{ width:24px; height:24px; }}
      #hub {{ position:absolute; left:{HUB[0]}px; top:{HUB[1]}px; width:{HUB[2]}px; height:{HUB[3]}px; border-radius:18px; background:rgba(12,85,96,0.96);
              border:2px solid rgba(255,255,255,0); color:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; box-shadow:0 10px 24px rgba(7,63,76,0.3); }}
      #hub .hb {{ display:flex; align-items:center; gap:8px; font-size:19px; font-weight:800; }} #hub .hb img {{ width:30px; height:30px; border-radius:8px; }}
      #hub small {{ font-size:14px; color:#cfe3e1; text-align:center; line-height:1.25; }}
      .wires {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; pointer-events:none; }}
      .wires line {{ stroke:rgba(255,255,255,0.75); stroke-width:2; stroke-dasharray:6 8; }}
      .dot {{ position:absolute; left:0; top:0; width:14px; height:14px; border-radius:50%; background:var(--sunrise); box-shadow:0 0 10px rgba(232,96,76,0.9), 0 0 2px #fff; opacity:0; }}

      /* 아웃트로: 앱 아이콘 + 워드마크 · WEB/APP/전화 세 갈래(QR 둘 + 번호), 아래 띠에 E-UM 디지털 트윈 포항 로고 */
      #outro-bg {{ position:absolute; inset:0; background:var(--page); }}
      #o-logo {{ position:absolute; left:0; right:0; top:56px; display:flex; align-items:center; justify-content:center; gap:24px; }}
      #o-logo .bi {{ width:116px; height:116px; border-radius:28px; box-shadow:0 12px 30px rgba(7,63,76,0.25); }}
      #o-logo .bw {{ height:100px; }}
      #o-sub {{ position:absolute; left:0; right:0; top:196px; font-size:36px; font-weight:500; color:var(--muted); }}
      #o-cta {{ position:absolute; left:0; right:0; top:256px; font-size:50px; font-weight:800; color:var(--coral); letter-spacing:-0.01em; }}
      #o-ways {{ position:absolute; left:0; right:0; top:352px; display:flex; justify-content:center; gap:72px; }}
      .way {{ width:340px; display:flex; flex-direction:column; align-items:center; gap:14px; }}
      .way .k {{ font-size:36px; font-weight:800; color:var(--brand); letter-spacing:0.02em; }}
      .way .box {{ width:340px; height:340px; border-radius:28px; background:#fff; box-shadow:0 12px 30px rgba(7,63,76,0.16); display:grid; place-items:center; }}
      .way .box img {{ width:300px; height:300px; }}
      .way .box.tel {{ background:var(--brand); color:#fff; align-content:center; gap:18px; }}
      .way .box.tel svg {{ width:96px; height:96px; }}
      .way .box.tel b {{ font-size:42px; font-weight:800; font-variant-numeric:tabular-nums; letter-spacing:-0.01em; }}
      .way .v {{ font-size:28px; font-weight:700; color:var(--ink); }}
      #o-credit {{ position:absolute; left:0; right:0; bottom:0; height:150px; background:#10232b; display:flex; align-items:center; justify-content:center; }}
      #o-credit img {{ height:64px; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{fmt(TOTAL)}" data-width="{W}" data-height="{H}">

      <!-- 촬영분: 한 파일을 바닥에. #stage 를 살짝 줌인/줌아웃 -->
      <div id="stage">
        <video id="footage" src="{FOOT['file']}" playsinline data-has-audio="true" data-start="0" data-duration="{fmt(FOOT_END)}" data-track-index="0"></video>
      </div>

      <!-- 앱 설명 패널 (오른쪽) -->
      <section id="app" class="clip" data-start="{fmt(app_s)}" data-duration="{fmt(app_e - app_s)}" data-track-index="2">
        <div id="brand" class="brandrow"><img class="bi" src="{ICON}" alt=""><img class="bw" src="{WORDMARK}" alt="배마중"></div>
        <div id="cap2" class="cap center">폰으로 열면, 오늘 새벽이 먼저 보여요</div>
        <div id="cap3" class="cap center">몇 시에, 어떤 배가, 뭘 싣고</div>
        <div id="cap4" class="cap center">기다리는 생선이 들어오면 휴대폰으로</div>
        <div id="cap5" class="cap center">언제 출발할지까지 한 줄로</div>
        <svg class="wires" id="wires-b" viewBox="0 0 {W} {H}" data-layout-ignore>{LINES_B}</svg>
        {GROUPS_B_HTML}
        <div id="hub" data-layout-allow-overlap><div class="hb"><img src="{ICON}" alt="">배마중 서버</div><small>API 데이터 기반<br>정보제공 및 대화</small></div>
        {DOTS_B}
        <div id="phone">
          <div class="frame" data-layout-allow-overflow>
            <div class="screen" data-layout-allow-overflow>
              <div id="scr-home" class="scr"><img src="assets/app/home.png" alt="배마중 홈: 다음 배 75분 뒤 도착 남진호"></div>
              <div id="scr-home2" class="scr"><img src="assets/app/home-scrolled.png" alt="배마중 홈: 언제 가면 되나"></div>
              <div id="scr-alerts" class="scr"><img src="assets/app/alerts.png" alt="배마중 알림: 기다리는 생선 고르기"></div>
              <div id="hl-next" class="hl" data-layout-ignore></div>
              <div id="hl-visit" class="hl" data-layout-ignore></div>
              <div id="toast" data-layout-allow-occlusion><img src="assets/app/toast.png" alt="새 입항 소식 띠"></div>
              <div id="finger" data-layout-ignore></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 통화 패널 (왼쪽) -->
      <section id="callscene" class="clip" data-start="{fmt(cs)}" data-duration="{fmt(call_e - cs)}" data-track-index="3">
        <div id="brand2" class="brandrow"><img class="bi" src="{ICON}" alt=""><img class="bw" src="{WORDMARK}" alt="배마중"><small>전화로 물어보기</small></div>
        <div id="call-cap" class="center">말로 물으면, 말로 알려 드려요</div>
        <svg class="wires" id="wires-f" viewBox="0 0 {W} {H}" data-layout-ignore>{LINES_F}</svg>
        {GROUPS_F_HTML}
        {DOTS_F}
        <div id="call">
          <div class="hd">
            <div><div class="nm"><img class="bi" src="{ICON}" alt=""><img class="bw" src="{WORDMARK}" alt="배마중"></div><div class="no">{phone_no}</div></div>
            <div class="st"><span id="st-live" data-layout-allow-overlap>통화 중 <span id="timer" data-layout-allow-overlap>0:00</span></span><span id="st-end" data-layout-allow-overlap>통화 종료</span></div>
          </div>
          <div class="log">
            {call_html}
          </div>
        </div>
      </section>

      <!-- 자막 -->
{subs_html}

      <!-- 1:30 페이드아웃 -->
      <div id="fade" class="clip" data-start="{fmt(FADE_T)}" data-duration="{fmt(TOTAL - FADE_T)}" data-track-index="5" data-layout-ignore></div>

      <!-- 아웃트로 -->
      <section id="outro" class="clip" data-start="{fmt(OUTRO_T)}" data-duration="{fmt(TOTAL - OUTRO_T)}" data-track-index="6">
        <div id="outro-bg"></div>
        <div id="o-logo"><img class="bi" src="{ICON}" alt=""><img class="bw" src="{WORDMARK}" alt="배마중"></div>
        <div id="o-sub" class="center">구룡포항 새벽 입항·어종 알림</div>
        <div id="o-cta" class="center">WEB / APP / 전화 모두 가능합니다</div>
        <div id="o-ways">
          <div class="way"><span class="k">WEB</span><div class="box"><img src="assets/brand/qr-web.svg" alt="bmj.kr QR 코드"></div><span class="v">bmj.kr</span></div>
          <div class="way"><span class="k">APP</span><div class="box"><img src="assets/brand/qr-apk.svg" alt="안드로이드 APK 내려받기 QR 코드"></div><span class="v">안드로이드 APK</span></div>
          <div class="way"><span class="k">전화</span><div class="box tel">{PHONE_SVG}<b>{phone_no}</b></div><span class="v">말로 물어보기</span></div>
        </div>
        <div id="o-credit"><img src="{DT_LOGO}" alt="E-UM 디지털 트윈 포항"></div>
      </section>

      <audio id="music" src="{music['file']}" data-start="0" data-duration="{fmt(TOTAL)}" data-track-index="10" data-automation='{music_auto}'></audio>
{sfx_html}
    </div>

    <script>
      // 모든 시각은 절대 초. timeline.json 에서 생성됨 — 직접 고치지 말고 build.py 를 다시 돌린다.
      const OUI = "power3.out";
      const pad = (n) => String(n).padStart(2, "0");

      document.fonts.ready.then(() => {{
        const tl = gsap.timeline({{ paused: true }});
        // 카드(묶음·허브)는 테두리, 줄(li)은 바탕을 켠다
        const lit = (sel, t, hold) => {{
          const el = document.querySelector(sel); if (!el) return;
          if (el.tagName === "LI") {{
            tl.to(sel, {{ backgroundColor: "#fdeeea", color: "{CORAL}", duration: 0.2 }}, t);
            tl.to(sel, {{ backgroundColor: "rgba(255,255,255,0)", color: "{INK}", duration: 0.35 }}, t + hold);
          }} else {{
            tl.to(sel, {{ borderColor: "{SUNRISE}", scale: 1.03, duration: 0.2 }}, t);
            tl.to(sel, {{ borderColor: "rgba(255,255,255,0)", scale: 1, duration: 0.35 }}, t + hold);
          }}
        }};
        const flow = (sel, from, to, t) => {{
          tl.fromTo(sel, {{ x: from[0] - 7, y: from[1] - 7, opacity: 0 }}, {{ opacity: 1, duration: 0.08, immediateRender: false }}, t);
          tl.to(sel, {{ x: to[0] - 7, y: to[1] - 7, duration: 0.45, ease: "power1.inOut" }}, t);
          tl.to(sel, {{ opacity: 0, duration: 0.1 }}, t + 0.45);
        }};
        const tap = (x, y, t) => {{   // 손가락이 x,y 로 가서 누른다
          tl.to("#finger", {{ x, y, duration: 0.45, ease: "power2.inOut" }}, t - 0.5);
          tl.to("#finger", {{ scale: 0.82, duration: 0.1 }}, t);
          tl.to("#finger", {{ scale: 1, duration: 0.18, ease: "back.out(2)" }}, t + 0.1);
        }};
        const ring = (sel, t, hold) => {{
          tl.fromTo(sel, {{ opacity: 0, scale: 1.04 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: OUI }}, t);
          tl.to(sel, {{ opacity: 0, duration: 0.3 }}, t + hold);
        }};

        /* 초기 상태 */
        gsap.set("#stage", {{ scale: 1, transformOrigin: "{zA['origin']}" }});
        gsap.set(["#brand", "#cap2", "#cap3", "#cap4", "#cap5", "#call-cap", "#brand2"], {{ opacity: 0 }});
        gsap.set("#phone", {{ y: 900, opacity: 0 }});
        gsap.set(["#scr-home2", "#scr-alerts"], {{ opacity: 0 }});
        gsap.set("#scr-alerts", {{ x: 390 }});
        gsap.set("#toast", {{ yPercent: -130, opacity: 0 }});
        gsap.set("#finger", {{ opacity: 0, x: {TAB_ALERTS_HOME[0]}, y: {TAB_ALERTS_HOME[1]} }});
        gsap.set("#call", {{ y: 60, opacity: 0 }});
        gsap.set("#st-end", {{ opacity: 0 }});
        gsap.set(".bub", {{ opacity: 0 }});
        gsap.set(["#wires-b", "#wires-f"], {{ opacity: 0 }});
        gsap.set([".group", "#hub"], {{ opacity: 0, x: -20 }});
        gsap.set("#fade", {{ opacity: 0 }});
        gsap.set(["#outro-bg", "#o-logo", "#o-sub", "#o-cta", ".way", "#o-credit"], {{ opacity: 0 }});
        document.querySelectorAll(".sub .band").forEach((b) => gsap.set(b, {{ opacity: 0, y: 16 }}));

        /* 자막: 시작에서 올라오고 끝에서 사라진다 */
        document.querySelectorAll(".sub").forEach((el) => {{
          const s = parseFloat(el.dataset.start), d = parseFloat(el.dataset.duration), band = el.querySelector(".band");
          tl.to(band, {{ opacity: 1, y: 0, duration: 0.25, ease: OUI }}, s);
          tl.to(band, {{ opacity: 0, duration: 0.2 }}, s + d - 0.25);
        }});

        /* 줌: 앱 설명 구간은 들어갔다 돌아오고, 전화 구간은 들어간 채로 끝난다(마지막 줌아웃 없음) */
        tl.set("#stage", {{ transformOrigin: "{zA['origin']}" }}, {fmt(app_s)});
        tl.to("#stage", {{ scale: {zA['scale']}, duration: {zA['dur']}, ease: "power2.inOut" }}, {fmt(app_s)});
        tl.to("#stage", {{ scale: 1, duration: {zA['dur']}, ease: "power2.inOut" }}, {fmt(app_e - zA['dur'])});
        tl.set("#stage", {{ transformOrigin: "{zC['origin']}" }}, {fmt(cs)});
        tl.to("#stage", {{ scale: {zC['scale']}, duration: {zC['dur']}, ease: "power2.inOut" }}, {fmt(cs)});

        /* 앱 설명 구간 */
        const h = {fmt(bt['home'])}, f = {fmt(bt['forecast'])}, a = {fmt(bt['alerts'])}, to = {fmt(bt['toast'])}, d = {fmt(bt['depart'])}, o = {fmt(bt['out'])};
        tl.to("#wires-b", {{ opacity: 1, duration: 0.6 }}, {fmt(app_s + 0.5)});
        tl.to(["#gb-eum", "#gb-ext"], {{ opacity: 1, x: 0, duration: 0.4, ease: OUI, stagger: 0.1 }}, {fmt(app_s + 0.4)});
        tl.to("#hub", {{ opacity: 1, x: 0, duration: 0.4, ease: OUI }}, {fmt(app_s + 0.7)});
{FLOW_JS_B}
        tl.to(["#wires-b", "#gb-eum", "#gb-ext", "#hub"], {{ opacity: 0, duration: 0.7 }}, o);
        tl.to("#brand", {{ opacity: 1, duration: 0.4 }}, h - 0.1);
        tl.to("#phone", {{ y: 0, opacity: 1, duration: 0.75, ease: OUI }}, h);
        tl.fromTo("#cap2", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, h + 0.6);
        // 몇 시에, 어떤 배가, 뭘 싣고 — 다음 배 카드를 짚는다
        tl.to("#cap2", {{ opacity: 0, y: -12, duration: 0.3 }}, f - 0.2);
        tl.fromTo("#cap3", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, f + 0.2);
        ring("#hl-next", f + 0.5, 2.3);
        // 알림 탭 → 휴대폰 알림 받기
        tl.to("#cap3", {{ opacity: 0, y: -12, duration: 0.3 }}, a - 0.2);
        tl.to("#finger", {{ opacity: 1, duration: 0.2 }}, a - 0.3);
        tap({TAB_ALERTS_HOME[0]}, {TAB_ALERTS_HOME[1]}, a + 0.3);
        tl.to("#scr-home", {{ x: -390, opacity: 0, duration: 0.4, ease: "power2.inOut" }}, a + 0.35);
        tl.to("#scr-alerts", {{ x: 0, opacity: 1, duration: 0.4, ease: "power2.inOut" }}, a + 0.35);
        tl.fromTo("#cap4", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, a + 0.5);
        tl.to("#finger", {{ opacity: 0, duration: 0.2 }}, a + 0.6);   // 알림 장은 탭 줄이 더 아래라 손가락을 새로 놓는다
        tl.set("#finger", {{ x: {BTN_APPLY[0]}, y: {BTN_APPLY[1] - 70}, scale: 1 }}, a + 1.2);
        tl.to("#finger", {{ opacity: 1, duration: 0.2 }}, a + 1.25);
        tap({BTN_APPLY[0]}, {BTN_APPLY[1]}, a + 1.8);
        tl.to("#finger", {{ opacity: 0, duration: 0.25 }}, a + 2.2);
        // 새 입항 소식 띠
        tl.to("#toast", {{ yPercent: 0, opacity: 1, duration: 0.45, ease: OUI }}, to);
        // 들어오는 배 탭으로 돌아와 '언제 가면 되나'
        tl.to("#cap4", {{ opacity: 0, y: -12, duration: 0.3 }}, d - 0.2);
        tl.set("#finger", {{ x: {TAB_SHIPS_ALERTS[0]}, y: {TAB_SHIPS_ALERTS[1]}, scale: 1 }}, d - 0.5);
        tl.to("#finger", {{ opacity: 1, duration: 0.2 }}, d - 0.5);
        tap({TAB_SHIPS_ALERTS[0]}, {TAB_SHIPS_ALERTS[1]}, d);
        tl.to("#finger", {{ opacity: 0, duration: 0.25 }}, d + 0.3);
        tl.to("#scr-alerts", {{ x: 390, opacity: 0, duration: 0.4, ease: "power2.inOut" }}, d + 0.05);
        tl.to("#scr-home", {{ x: 0, opacity: 1, duration: 0.4, ease: "power2.inOut" }}, d + 0.05);
        tl.to("#toast", {{ yPercent: -130, opacity: 0, duration: 0.35, ease: "power2.in" }}, d + 0.2);
        tl.fromTo("#cap5", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, d + 0.5);
        tl.to("#scr-home", {{ y: -40, opacity: 0, duration: 0.45, ease: "power2.inOut" }}, d + 0.6);
        tl.fromTo("#scr-home2", {{ y: 40 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: "power2.inOut" }}, d + 0.6);
        ring("#hl-visit", d + 1.2, 1.6);
        tl.to(["#phone", "#brand", "#cap5"], {{ opacity: 0, duration: 0.7 }}, o);

        /* 전화 구간 */
        tl.to("#wires-f", {{ opacity: 1, duration: 0.6 }}, {fmt(cs + 0.5)});
        tl.to(["#gf-eum", "#gf-ext"], {{ opacity: 1, x: 0, duration: 0.4, ease: OUI, stagger: 0.1 }}, {fmt(cs + 0.3)});
{FLOW_JS_F}
        tl.to(["#wires-f", "#gf-eum", "#gf-ext"], {{ opacity: 0, duration: 0.6 }}, {fmt(FADE_T - 0.6)});
        tl.to(["#brand2", "#call-cap"], {{ opacity: 1, duration: 0.4 }}, {fmt(cs + 0.2)});
        tl.to("#call", {{ y: 0, opacity: 1, duration: 0.6, ease: OUI }}, {fmt(cs + 0.4)});
        const timer = {{ s: 0 }};
        tl.to(timer, {{ s: {fmt(end_badge - cs)}, duration: {fmt(end_badge - cs)}, ease: "none", onUpdate() {{ const s = Math.floor(timer.s); document.getElementById("timer").textContent = Math.floor(s / 60) + ":" + pad(s % 60); }} }}, {fmt(cs)});
{call_js}
        tl.to("#st-live", {{ opacity: 0, duration: 0.25 }}, {fmt(end_badge)});
        tl.to("#st-end", {{ opacity: 1, duration: 0.25 }}, {fmt(end_badge)});

        /* 1:30 페이드아웃 → 아웃트로 */
        tl.to("#fade", {{ opacity: 1, duration: {fmt(FOOT_END - FADE_T)}, ease: "power1.inOut" }}, {fmt(FADE_T)});
        tl.to("#outro-bg", {{ opacity: 1, duration: 0.6, ease: "power2.inOut" }}, {fmt(OUTRO_T)});
        tl.fromTo("#o-logo", {{ scale: 0.82 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.4)" }}, {fmt(OUTRO_T + 0.4)});
        tl.fromTo("#o-sub", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, {fmt(OUTRO_T + 0.8)});
        tl.fromTo("#o-cta", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, {fmt(OUTRO_T + 1.1)});
        tl.fromTo(".way", {{ y: 24 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: OUI, stagger: 0.15 }}, {fmt(OUTRO_T + 1.3)});
        tl.fromTo("#o-credit", {{ y: 20 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: OUI }}, {fmt(OUTRO_T + 1.9)});

        window.__timelines["main"] = tl;
        if (window.__hfForceTimelineRebind) window.__hfForceTimelineRebind();
      }});
    </script>
  </body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"index.html 생성 — 총 {TOTAL:.1f}초 (촬영분 {FOOT_END:g}초 + 아웃트로 {cfg['outro']['duration']:g}초), "
      f"앱 {app_s:g}~{app_e:g}, 전화 {cs:g}~{call_e:g}, 페이드 {FADE_T:g}")


# ---------------------------------------------------------------- 폰트 서브셋
def subset_font() -> None:
    body = HTML.split("<body>", 1)[1].split("<script>", 1)[0]
    text = re.sub(r"<[^>]+>", " ", body)
    extra = "0123456789:·~%.,!?→✓ ()tkm통화종료중"
    chars = {c for c in (set(text) | set(extra)) if not c.isspace()}
    if not FONT_SRC.exists():
        print("폰트 원본 없음(윈도우가 아니면 NOTO_KR_TTF 로 지정): " + ("기존 서브셋 사용" if FONT_SUB.exists() else "시스템 폰트로 대체됨 — 렌더 글꼴이 달라질 수 있음"))
        return
    glyphs = HERE / ".glyphs.txt"
    glyphs.write_text("".join(sorted(chars)), encoding="utf-8")
    FONT_SUB.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["uvx", "--from", "fonttools", "pyftsubset", str(FONT_SRC), f"--text-file={glyphs}", f"--output-file={FONT_SUB}",
                        "--layout-features=*", "--name-IDs=*"], check=True, capture_output=True)
        print(f"폰트 서브셋 {FONT_SUB.stat().st_size // 1024}KB ({len(chars)}자)")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"폰트 서브셋 실패({e.__class__.__name__}): uv 가 있으면 `uvx --from fonttools pyftsubset` 로 직접 만들 수 있음")
    finally:
        glyphs.unlink(missing_ok=True)


subset_font()
