"""timeline.json → composition/index.html 생성기 (배마중 소개영상 최종본, 가로 1920×1080).

실제 촬영분 한 개(footage.mp4)를 바닥에 깔고, 그 위에
  · 자막(촬영 음성 기준 절대 초)
  · 앱 설명 구간: 그래픽 오른쪽(청년은 왼쪽) + 살짝 줌인/줌아웃
  · 전화 구간:   그래픽 왼쪽(할아버지는 오른쪽) + 살짝 줌인/줌아웃
  · 1:30 부터 1초 페이드아웃 → 아웃트로
를 얹는다. 시각·자막·통화 대사는 timeline.json 에서만 고친다. 이 파일은 레이아웃·모션만 가진다.

실행: python build.py  →  cd composition && npx hyperframes check && npx hyperframes render --quality looks --output ../배마중_소개영상_최종.mp4
폰트: demo/build.py 와 같은 방식으로 Noto Sans KR 서브셋(윈도우 원본이 있을 때만 갱신).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
COMP = HERE / "composition"
OUT = COMP / "index.html"
FONT_SRC = Path(r"C:/Windows/Fonts/NotoSansKR-VF.ttf")
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
phone_no = escape(cfg.get("phone_number_text", "070-0000-0000"))


# ---------------------------------------------------------------- 자막
def subtitle_tags() -> str:
    html = []
    for j, ln in enumerate(cfg["subtitles"]):
        side = ln.get("side", "")
        html.append(
            f'      <div id="sub-{j}" class="clip sub{(" " + side) if side else ""}" data-start="{fmt(ln["t"])}" '
            f'data-duration="{fmt(ln["end"] - ln["t"])}" data-track-index="1" data-layout-allow-caption-zone>\n'
            f'        <div class="band"><span class="who">{escape(ln["who"])}</span><span class="say">{escape(ln["text"])}</span></div>\n'
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
            items.append(f'<div id="{bid}" class="bub ai"><span class="av">⚓</span><p>{spans}</p></div>')
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
# 앱 구간(오른쪽 패널): demo 와 같은 좌표
NODE_X, NODE_W = 896, 300
HUB = (1246, 476, 190, 104)                    # 배마중 서버 허브 (left, top, w, h)
PHONE_LEFT, PHONE_TOP = 1486, 186
NODES_B = [
    ("🛰", "E-UM 선박 위치", "디지털트윈 포항 · 10분마다"),
    ("📋", "E-UM 어선 명부", "202척 · 어업종류·톤수"),
    ("📊", "해수부 위판 실적", "구룡포수협 · 최근 4년 10월"),
    ("🚚", "E-UM 교통 센서", "위판장 80m 앞 · 실측"),
    ("🔔", "웹 푸시 (VAPID)", "조건이 맞으면 폰으로"),
]
NODE_H_B, GAP_B, TOP_B = 104, 16, 236
# 전화 구간(왼쪽 패널): demo 좌표를 좌우 반전. 통화 카드가 왼쪽 끝, 노드 열이 그 오른쪽
CALL_LEFT, CALL_W = 16, 600
NODE_X_F, NODE_W_F, NODE_H_F, GAP_F, TOP_F = 636, 280, 96, 12, 206
NODES_F = [
    ("☎", "ClawOps 070", "전화 연결 · 통화 음성"),
    ("🎙", "CLOVA Speech", "실시간 받아쓰기"),
    ("🧠", "OpenAI", "범위 판정 · 도구 호출"),
    ("🛰", "E-UM 선박 위치", "입항 예보"),
    ("📊", "해수부 위판 실적", "어종 추정"),
    ("🚚", "E-UM 교통 센서", "방문 시각"),
    ("🔊", "Gemini TTS", "문장 음성 합성"),
]


def node_html(prefix, nodes, left, w, h, gap, top):
    out = []
    for i, (ic, nm, sub) in enumerate(nodes):
        out.append(f'<div id="{prefix}{i}" class="node" style="left:{left}px; top:{top + i * (h + gap)}px; width:{w}px; height:{h}px;">'
                   f'<span class="ic">{ic}</span><span class="tx"><b>{escape(nm)}</b><small>{escape(sub)}</small></span></div>')
    return "\n        ".join(out)


def anchors(nodes, x, h, gap, top):
    return [(x, top + i * (h + gap) + h // 2) for i in range(len(nodes))]


ANC_B = anchors(NODES_B, NODE_X + NODE_W, NODE_H_B, GAP_B, TOP_B)           # 노드 오른쪽 가장자리
HUB_L, HUB_R = (HUB[0], HUB[1] + HUB[3] // 2), (HUB[0] + HUB[2], HUB[1] + HUB[3] // 2)
PHONE_A = (PHONE_LEFT, 600)
ANC_F = anchors(NODES_F, NODE_X_F, NODE_H_F, GAP_F, TOP_F)                  # 노드 왼쪽 가장자리
CALL_A = (CALL_LEFT + CALL_W, 560)                                           # 통화 카드 오른쪽 가장자리


def svg_lines(pairs):
    return "".join(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" />' for a, b in pairs)


LINES_B = svg_lines([(a, HUB_L) for a in ANC_B] + [(HUB_R, PHONE_A)])
LINES_F = svg_lines([(a, CALL_A) for a in ANC_F])

bt = APP["beats"]
FLOWS_B = [  # (절대 시각, 켜질 노드, 경로)
    (bt["home"] + 1.3, 1, [(ANC_B[1], HUB_L), (HUB_R, PHONE_A)]),        # 어선 명부 → 칩
    (bt["forecast"] + 0.5, 0, [(ANC_B[0], HUB_L), (HUB_R, PHONE_A)]),    # 선박 위치 → 입항 카드
    (bt["forecast"] + 2.3, 2, [(ANC_B[2], HUB_L), (HUB_R, PHONE_A)]),    # 위판 실적 → 어종 줄
    (bt["toast"] - 0.5, 4, [(HUB_L, ANC_B[4]), (ANC_B[4], PHONE_A)]),    # 서버 → 웹 푸시 → 폰(띠)
    (bt["depart"] + 0.9, 3, [(ANC_B[3], HUB_L), (HUB_R, PHONE_A)]),      # 교통 센서 → 출발 카드
]
cs = float(CALL["start"])
FLOWS_F = [(cs + 0.5, 0, [(ANC_F[0], CALL_A)])]                            # 전화 연결
for e in CALL["events"]:
    if e["who"] == "ai":
        FLOWS_F.append((e["t"] - 0.1, 6, [(ANC_F[6], CALL_A)]))             # 음성 합성 → 통화
    elif e["who"] == "user":
        FLOWS_F.append((e["t"] - 0.1, 1, [(CALL_A, ANC_F[1]), (ANC_F[1], CALL_A)]))  # 말 → 받아쓰기 → 글
    else:
        gap = float(e.get("gap", 0.55))
        FLOWS_F.append((e["t"] - 0.1, 2, [(CALL_A, ANC_F[2]), (ANC_F[2], CALL_A)]))  # 판정·도구 호출
        for j, ni in enumerate((3, 4, 5)):
            FLOWS_F.append((e["t"] + gap * (2 + j), ni, [(ANC_F[ni], CALL_A)]))


def flow_js(scene, flows, node_prefix, hub=False):
    js, dots = [], []
    for k, (t, ni, path) in enumerate(flows):
        js.append(f'        lit("#{node_prefix}{ni}", {fmt(t)}, {fmt(0.5 * len(path) + 0.8)});')
        tt = t
        for j, (a, b) in enumerate(path):
            did = f"dot-{scene}-{k}-{j}"
            dots.append(f'<span id="{did}" class="dot"></span>')
            js.append(f'        flow("#{did}", [{a[0]}, {a[1]}], [{b[0]}, {b[1]}], {fmt(tt)});')
            if hub and (b == HUB_L or a == HUB_R):
                js.append(f'        lit("#hub", {fmt(tt + 0.45)}, 0.6);')
            tt += 0.5
    return "\n".join(js), "".join(dots)


FLOW_JS_B, DOTS_B = flow_js("B", FLOWS_B, "nb", hub=True)
FLOW_JS_F, DOTS_F = flow_js("F", FLOWS_F, "nf")
NODES_B_HTML = node_html("nb", NODES_B, NODE_X, NODE_W, NODE_H_B, GAP_B, TOP_B)
NODES_F_HTML = node_html("nf", NODES_F, NODE_X_F, NODE_W_F, NODE_H_F, GAP_F, TOP_F)

# ---------------------------------------------------------------- 본문 조립
subs_html = subtitle_tags()
call_html, call_js, call_sfx = call_tags()
app_s, app_e = float(APP["start"]), float(APP["end"])
call_e = float(CALL["end"])
end_badge = float(CALL["end_badge_t"])
zA, zC = APP["zoom"], CALL["zoom"]

sfx = [  # (id, 파일, 절대 시각, 볼륨)
    ("sfx-land", "impact/impactSoft_medium_001.ogg", bt["home"] + 0.55, 0.6),
    ("sfx-chip1", "interface/drop_001.ogg", bt["home"] + 1.6, 0.45), ("sfx-chip2", "interface/drop_001.ogg", bt["home"] + 2.1, 0.45),
    ("sfx-chip3", "interface/drop_001.ogg", bt["home"] + 2.6, 0.45), ("sfx-slide1", "casino/card-slide-1.ogg", bt["forecast"], 0.4),
    ("sfx-num", "impact/impactSoft_medium_001.ogg", bt["forecast"] + 1.25, 0.5), ("sfx-l3", "interface/drop_002.ogg", bt["forecast"] + 2.4, 0.45),
    ("sfx-tap1", "interface/click_003.ogg", bt["alerts"] + 0.3, 0.7), ("sfx-slide2", "casino/card-slide-1.ogg", bt["alerts"] + 0.35, 0.4),
    ("sfx-tap2", "interface/click_003.ogg", bt["alerts"] + 1.8, 0.7), ("sfx-toast", "impact/impactBell_heavy_000.ogg", bt["toast"], 0.45),
    ("sfx-slide3", "casino/card-slide-1.ogg", bt["depart"], 0.35), ("sfx-depart", "interface/drop_001.ogg", bt["depart"] + 1.3, 0.5),
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

HTML = f"""<!doctype html>
<html lang="ko" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <title>배마중 소개영상 · 최종</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Noto Sans KR"; src: url("assets/fonts/NotoSansKR-subset.ttf") format("truetype"); font-weight: 100 900; font-display: block; }}
      :root {{ --page:#f7f8f5; --card:#fff; --ink:#263238; --muted:#55636b; --line:#e3e7e4; --chip:#edf1ee; --navy:#193b50; --on-navy:#fff;
              --soft:#d9eae5; --arriving:#b4501d; --on-soft:#9a4116; --sun:#f18a54; --sun-soft:#fdf0e8; }}
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html, body {{ width:{W}px; height:{H}px; overflow:hidden; background:#000; font-family:"Noto Sans KR", system-ui, sans-serif; color:var(--ink); }}
      #root {{ position:relative; width:100%; height:100%; overflow:hidden; background:#000; }}
      .clip {{ position:absolute; inset:0; }}
      .center {{ text-align:center; }}
      #stage {{ position:absolute; inset:0; overflow:hidden; background:#000; }}
      #footage {{ position:absolute; top:0; left:0; width:{W}px; height:{H}px; object-fit:cover; background:#000; }}
      #fade {{ position:absolute; inset:0; background:#000; opacity:0; }}

      /* 자막: 기본은 가운데, 분할 구간은 사람이 있는 쪽(left/right 864px 띠) */
      .sub .band {{ position:absolute; left:0; right:0; bottom:72px; display:flex; justify-content:center; }}
      .sub.left .band {{ right:auto; width:{BAND}px; }}
      .sub.right .band {{ left:1000px; right:24px; }}
      .sub .band > span {{ display:inline-block; }}
      .sub .who {{ background:var(--sun); color:#1a1a1a; font-weight:800; font-size:26px; padding:8px 16px; border-radius:12px 0 0 12px; white-space:nowrap; }}
      .sub .say {{ background:rgba(14,26,33,0.82); color:#fff; font-weight:700; font-size:34px; line-height:1.3; padding:8px 22px; border-radius:0 12px 12px 0; max-width:1400px; }}
      .sub.left .say, .sub.right .say {{ max-width:{BAND - 160}px; font-size:30px; }}

      /* 오른쪽 패널 공통(앱 구간) */
      #brand {{ position:absolute; left:{BAND}px; width:{PANEL}px; top:44px; font-size:38px; font-weight:900; color:var(--navy); letter-spacing:-0.02em; {GLOW} }}
      #brand small {{ font-size:24px; font-weight:500; color:var(--muted); margin-left:8px; letter-spacing:0; }}
      .cap {{ position:absolute; left:{BAND + 40}px; width:{PANEL - 80}px; top:104px; font-size:40px; font-weight:800; color:var(--navy); letter-spacing:-0.02em; line-height:1.3; {GLOW} }}

      /* 폰 목업 (390×844) */
      #phone {{ position:absolute; left:{PHONE_LEFT}px; top:{PHONE_TOP}px; width:410px; height:864px; }}
      .frame {{ position:absolute; inset:0; border:10px solid var(--navy); border-radius:48px; overflow:hidden; background:var(--card); box-shadow:0 24px 50px rgba(25,59,80,0.18); }}
      .screen {{ position:relative; width:390px; height:844px; overflow:hidden; background:var(--page); }}
      .appbar {{ position:absolute; left:0; right:0; top:0; height:56px; padding:0 16px; display:flex; align-items:center; justify-content:space-between; }}
      .appbar .name {{ font-size:18px; font-weight:800; color:var(--navy); }}
      .appbar .name small {{ font-size:14px; font-weight:500; color:var(--muted); margin-left:6px; }}
      .tag {{ display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:13px; font-weight:700; background:var(--chip); color:var(--muted); }}
      .tag.sun {{ background:var(--sun-soft); color:var(--on-soft); }}
      .scr {{ position:absolute; left:0; right:0; top:56px; bottom:56px; overflow:hidden; }}
      .scroll {{ position:absolute; left:0; right:0; top:0; padding:20px 16px 0; }}
      .card {{ background:var(--card); border-radius:20px; padding:20px; }}
      .today {{ background:linear-gradient(180deg, var(--sun-soft) 0%, var(--card) 100%); border-radius:20px; padding:20px; }}
      .today .date {{ font-size:14px; color:var(--muted); }} .today .date b {{ color:var(--ink); font-variant-numeric:tabular-nums; }}
      .today .greet {{ margin-top:4px; font-size:20px; line-height:1.4; font-weight:700; color:var(--navy); }}
      .chips {{ margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; }}
      .pill {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 12px; font-size:14px; font-weight:700; background:var(--card); color:var(--ink); }}
      .next {{ margin-top:16px; position:relative; }} .next .head {{ display:flex; align-items:center; justify-content:space-between; }}
      .h2 {{ font-size:19px; font-weight:700; color:var(--navy); }}
      .box {{ margin-top:12px; border-radius:20px; padding:16px; background:var(--sun-soft); }}
      .eta-row {{ display:flex; align-items:flex-end; gap:12px; }}
      #eta {{ font-size:40px; line-height:1; font-weight:800; color:var(--arriving); font-variant-numeric:tabular-nums; min-width:112px; }}
      .eta-row small {{ font-size:13px; color:var(--muted); padding-bottom:4px; }}
      .name-line {{ margin-top:8px; font-size:20px; font-weight:700; }} .biz-line {{ font-size:14px; color:var(--muted); }}
      .sp-line {{ margin-top:8px; font-size:16px; font-weight:700; }} .sp-line small {{ font-size:13px; font-weight:500; color:var(--muted); margin-left:4px; }}
      .more {{ margin-top:12px; display:flex; align-items:center; justify-content:space-between; min-height:44px; padding:0 16px; border-radius:18px; background:var(--chip); font-size:15px; font-weight:700; }}
      #loading {{ position:absolute; inset:0; }} #loading .card {{ height:100%; color:var(--muted); font-size:16px; }}
      .depart {{ margin-top:16px; background:var(--navy); border-radius:20px; padding:20px; color:var(--on-navy); }}
      .depart .q {{ font-size:14px; color:#d5dde2; }} .depart .a {{ margin-top:4px; font-size:20px; line-height:1.4; font-weight:700; }} .depart .t {{ margin-top:4px; font-size:14px; color:#e4eaee; }}
      .mapsec {{ margin-top:16px; }} .maphead {{ display:flex; align-items:baseline; justify-content:space-between; padding:0 4px 8px; }} .maphead .link {{ font-size:14px; font-weight:700; color:var(--navy); }}
      .map {{ position:relative; height:200px; border-radius:20px; background:var(--soft); overflow:hidden; }}
      .map .land {{ position:absolute; left:-40px; top:-20px; width:120px; height:240px; border-radius:0 60px 60px 0; background:#e9ede7; }}
      .map .star {{ position:absolute; left:64px; top:92px; font-size:18px; color:#0072de; line-height:1; }}
      .map .dot {{ position:absolute; width:8px; height:8px; border-radius:50%; background:#8a9099; }} .map .dot.red {{ width:10px; height:10px; background:#d32f2f; }}
      .map .legend {{ position:absolute; left:10px; bottom:10px; display:flex; gap:6px; }}
      .map .legend span {{ font-size:11px; font-weight:700; color:var(--muted); background:rgba(255,255,255,0.85); border-radius:999px; padding:2px 8px; }}
      .title {{ font-size:20px; font-weight:700; color:var(--navy); }} .subt {{ margin-top:4px; font-size:14px; line-height:1.45; color:var(--muted); }}
      .wait {{ margin-top:16px; }} .fish {{ margin-top:16px; display:flex; flex-wrap:wrap; gap:8px; }}
      .fchip {{ display:inline-flex; align-items:center; min-height:44px; padding:0 16px; border-radius:18px; font-size:15px; font-weight:700; background:var(--chip); color:var(--ink); }}
      .fchip.on {{ background:var(--navy); color:var(--on-navy); }}
      .check {{ margin-top:16px; display:flex; align-items:center; gap:8px; min-height:44px; font-size:16px; }}
      .check .bx {{ width:20px; height:20px; border-radius:4px; background:var(--navy); color:#fff; font-size:14px; display:grid; place-items:center; }}
      .btn {{ margin-top:16px; width:100%; min-height:44px; display:flex; align-items:center; justify-content:center; border-radius:18px; background:var(--navy); color:var(--on-navy); font-size:15px; font-weight:700; }}
      .tabbar {{ position:absolute; left:0; right:0; bottom:0; height:56px; border-top:1px solid var(--line); background:var(--card); display:flex; }}
      .tab {{ flex:1; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; color:var(--muted); }} .tab.on {{ color:var(--navy); }}
      #tab-ind {{ position:absolute; left:24px; top:0; width:49px; height:3px; border-radius:2px; background:var(--sun); }}
      #toast {{ position:absolute; left:16px; right:16px; top:12px; background:var(--card); border-radius:20px; border-left:8px solid var(--sun); padding:16px; box-shadow:0 10px 24px rgba(25,59,80,0.18); }}
      #toast .t1 {{ font-size:14px; font-weight:700; color:var(--arriving); }} #toast .t2 {{ margin-top:4px; font-size:16px; line-height:1.45; }}
      #finger {{ position:absolute; left:222px; top:794px; width:44px; height:44px; border-radius:50%; background:rgba(25,59,80,0.32); border:2px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.25); }}

      /* 왼쪽 패널(전화 구간) */
      #brand2 {{ position:absolute; left:0; width:{PANEL}px; top:44px; font-size:38px; font-weight:900; color:var(--navy); letter-spacing:-0.02em; {GLOW} }}
      #brand2 small {{ font-size:24px; font-weight:500; color:var(--muted); margin-left:8px; letter-spacing:0; }}
      #call-cap {{ position:absolute; left:0; width:{PANEL}px; top:100px; font-size:36px; font-weight:800; color:var(--navy); letter-spacing:-0.02em; {GLOW} }}
      #call {{ position:absolute; left:{CALL_LEFT}px; top:176px; width:{CALL_W}px; height:874px; border-radius:36px; background:var(--card); box-shadow:0 24px 50px rgba(25,59,80,0.16); overflow:hidden; }}
      #call .hd {{ height:120px; background:var(--navy); color:var(--on-navy); padding:24px 26px; display:flex; align-items:center; justify-content:space-between; }}
      #call .hd .nm {{ font-size:30px; font-weight:800; }} #call .hd .no {{ font-size:20px; color:#cfd9e0; margin-top:4px; font-variant-numeric:tabular-nums; }}
      #call .hd .st {{ position:relative; width:220px; height:60px; }}
      #call .hd .st > span {{ position:absolute; right:0; top:0; font-size:22px; font-weight:700; color:#ffd7bf; white-space:nowrap; font-variant-numeric:tabular-nums; }}
      #st-end {{ color:#cfd9e0 !important; }}
      #call .log {{ padding:16px 28px; display:flex; flex-direction:column; gap:10px; }}
      .bub {{ max-width:520px; display:flex; gap:12px; align-items:flex-start; }}
      .bub p {{ font-size:20px; line-height:1.38; padding:9px 16px; border-radius:20px; }}
      .bub.ai p {{ background:var(--chip); color:var(--ink); border-top-left-radius:6px; }}
      .bub.ai .av {{ flex:0 0 40px; width:40px; height:40px; border-radius:50%; background:var(--navy); color:#fff; display:grid; place-items:center; font-size:22px; }}
      .bub.user {{ align-self:flex-end; flex-direction:column; align-items:flex-end; gap:4px; }}
      .bub.user p {{ background:var(--navy); color:var(--on-navy); border-top-right-radius:6px; }}
      .bub.user .stt {{ font-size:14px; font-weight:700; color:var(--muted); }}
      .tools {{ list-style:none; margin:0 0 0 52px; display:flex; flex-direction:column; gap:6px; }}
      .tools li {{ display:flex; align-items:center; gap:10px; font-size:16px; font-weight:700; color:var(--navy); background:var(--sun-soft); border-radius:10px; padding:6px 12px; width:fit-content; }}
      .tools .chk {{ width:24px; height:24px; border-radius:50%; background:var(--sun); color:#1a1a1a; display:grid; place-items:center; font-size:15px; }}

      /* 데이터 흐름 그래픽 */
      .node {{ position:absolute; display:flex; align-items:center; gap:12px; padding:10px 14px; border-radius:16px; background:rgba(255,255,255,0.92);
               border:2px solid rgba(255,255,255,0); box-shadow:0 8px 20px rgba(25,59,80,0.14); }}
      .node .ic {{ font-size:30px; line-height:1; width:40px; text-align:center; }}
      .node .tx {{ display:flex; flex-direction:column; gap:2px; }}
      .node b {{ font-size:18px; color:var(--navy); line-height:1.2; }}
      .node small {{ font-size:13px; color:var(--muted); line-height:1.2; }}
      #hub {{ position:absolute; left:{HUB[0]}px; top:{HUB[1]}px; width:{HUB[2]}px; height:{HUB[3]}px; border-radius:18px; background:rgba(25,59,80,0.96);
              border:2px solid rgba(255,255,255,0); color:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; box-shadow:0 10px 24px rgba(25,59,80,0.25); }}
      #hub b {{ font-size:19px; }} #hub small {{ font-size:12px; color:#cfd9e0; text-align:center; line-height:1.25; }}
      .wires {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; pointer-events:none; }}
      .wires line {{ stroke:rgba(255,255,255,0.75); stroke-width:2; stroke-dasharray:6 8; }}
      .dot {{ position:absolute; left:0; top:0; width:14px; height:14px; border-radius:50%; background:var(--sun); box-shadow:0 0 10px rgba(241,138,84,0.9), 0 0 2px #fff; opacity:0; }}

      /* 아웃트로 */
      #outro-bg {{ position:absolute; inset:0; background:var(--page); }}
      #o-logo {{ position:absolute; left:0; right:0; top:330px; font-size:120px; font-weight:900; color:var(--navy); letter-spacing:-0.02em; }}
      #o-sub {{ position:absolute; left:0; right:0; top:510px; font-size:44px; font-weight:500; color:var(--muted); }}
      #o-cta {{ position:absolute; left:0; right:0; top:595px; font-size:48px; font-weight:800; color:var(--arriving); }}
      #o-credit {{ position:absolute; left:0; right:0; top:720px; font-size:26px; font-weight:500; color:var(--muted); }}
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
        <div id="brand" class="center">⚓ 배마중<small>구룡포항</small></div>
        <div id="cap2" class="cap center">폰으로 열면, 오늘 새벽이 먼저 보여요</div>
        <div id="cap3" class="cap center">몇 시에, 어떤 배가, 뭘 싣고</div>
        <div id="cap4" class="cap center">기다리는 생선이 들어오면 휴대폰으로</div>
        <div id="cap5" class="cap center">언제 출발할지까지 한 줄로</div>
        <svg class="wires" id="wires-b" viewBox="0 0 {W} {H}" data-layout-ignore>{LINES_B}</svg>
        {NODES_B_HTML}
        <div id="hub" data-layout-allow-overlap><b>⚓ 배마중 서버</b><small>숫자는 룰이 계산<br>LLM은 문장만</small></div>
        {DOTS_B}
        <div id="phone">
          <div class="frame" data-layout-allow-overflow>
            <div class="screen" data-layout-allow-overflow>
              <div class="appbar"><span class="name" data-layout-allow-overlap>⚓ 배마중<small data-layout-allow-overlap>구룡포항</small></span><span class="tag" data-layout-allow-overlap>선박 위치 시연</span></div>
              <div id="scr-home" class="scr">
                <div id="home-scroll" class="scroll">
                  <div class="today" data-layout-allow-occlusion>
                    <p class="date" data-layout-allow-occlusion>10월 11일 토요일 · <b data-layout-allow-occlusion>03:10</b></p>
                    <p class="greet" data-layout-allow-occlusion>좋은 새벽이에요. 오늘도 배가 들어오고 있어요.</p>
                    <div class="chips"><span id="chip1" class="pill" data-layout-allow-occlusion>🚢 입항 예정 3척</span><span id="chip2" class="pill" data-layout-allow-occlusion>붉은대게 가능성 높음</span><span id="chip3" class="pill" data-layout-allow-occlusion>🚗 위판장 앞 비슷</span></div>
                  </div>
                  <div class="next">
                    <div id="next-card" class="card">
                      <div class="head"><span class="h2" data-layout-allow-occlusion data-layout-allow-overlap>곧 들어오는 배</span><span class="tag sun" data-layout-allow-occlusion>다음 입항까지 약 75분</span></div>
                      <div class="box">
                        <div class="eta-row"><span id="eta">04:25</span><small>예측 · 신뢰도 높음</small></div>
                        <p id="l1" class="name-line">남진호</p>
                        <p id="l2" class="biz-line">자망선 5t · 위판장까지 11.7km</p>
                        <p id="l3" class="sp-line">붉은대게 가능성 높음<small>추정 79%</small></p>
                      </div>
                      <div class="more"><span>들어오는 배 3척 모두 보기</span><span>→</span></div>
                    </div>
                    <div id="loading"><div class="card">불러오는 중입니다</div></div>
                  </div>
                  <div id="depart" class="depart"><p class="q">언제 가면 될까요?</p><p class="a">경매 09:00 · 08:30까지 도착하면 돼요</p><p class="t">지금 위판장 앞은 비슷 · 실측</p></div>
                  <div class="mapsec">
                    <div class="maphead"><span class="h2">구룡포항 지금</span><span class="link">크게 보기 →</span></div>
                    <div class="map" data-layout-ignore><div class="land"></div><span class="star">★</span>
                      <span class="dot" style="left:210px;top:60px"></span><span class="dot" style="left:236px;top:92px"></span><span class="dot" style="left:262px;top:70px"></span>
                      <span class="dot" style="left:290px;top:110px"></span><span class="dot" style="left:318px;top:84px"></span><span class="dot" style="left:344px;top:124px"></span>
                      <span class="dot red" style="left:150px;top:104px"></span><span class="dot red" style="left:176px;top:118px"></span><span class="dot red" style="left:198px;top:132px"></span>
                      <div class="legend"><span>★ 위판장</span><span>● 들어오는 배</span><span>○ 조업·대기</span></div></div>
                  </div>
                </div>
              </div>
              <div id="scr-alerts" class="scr">
                <div class="scroll">
                  <p class="title">알림</p><p class="subt">원하는 생선이 들어오면 휴대폰이나 전화로 먼저 알려 드려요</p>
                  <div class="card wait">
                    <p class="h2">기다리는 생선이 있나요?</p><p class="subt">원하는 생선이 들어오면 먼저 알려 드릴게요.</p>
                    <div class="fish"><span class="fchip on">🦀 붉은대게</span><span class="fchip">🦑 살오징어</span><span class="fchip">🐚 골뱅이</span><span class="fchip">🚢 어떤 배든</span></div>
                    <div class="check"><span class="bx">✓</span><span>🔔 휴대폰 알림</span></div>
                    <div id="apply" class="btn">알림 신청하기</div>
                  </div>
                </div>
              </div>
              <nav class="tabbar"><div id="tab-ind"></div><span id="tab0" class="tab on">홈</span><span id="tab1" class="tab">들어오는 배</span><span id="tab2" class="tab">알림</span><span id="tab3" class="tab">물어보기</span></nav>
              <div id="toast" data-layout-allow-occlusion><p class="t1" data-layout-allow-overlap>📣 03:10 입항 알림을 보냈어요</p><p class="t2" data-layout-allow-overlap>04:25~04:35 자망선 3척 입항 예정 · 붉은대게·골뱅이 가능성. 경매 09:00</p></div>
              <div id="finger" data-layout-ignore></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 통화 패널 (왼쪽) -->
      <section id="callscene" class="clip" data-start="{fmt(cs)}" data-duration="{fmt(call_e - cs)}" data-track-index="3">
        <div id="brand2" class="center">⚓ 배마중<small>전화로 물어보기</small></div>
        <div id="call-cap" class="center">말로 물으면, 말로 알려 드려요</div>
        <svg class="wires" id="wires-f" viewBox="0 0 {W} {H}" data-layout-ignore>{LINES_F}</svg>
        {NODES_F_HTML}
        {DOTS_F}
        <div id="call">
          <div class="hd">
            <div><div class="nm">📞 배마중</div><div class="no">{phone_no}</div></div>
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
        <div id="o-logo" class="center">⚓ 배마중</div>
        <div id="o-sub" class="center">구룡포항 새벽 입항·어종 알림</div>
        <div id="o-cta" class="center">폰 브라우저에서 바로. 전화로도.</div>
        <div id="o-credit" class="center">2026 디지털 트윈 구룡포 AI 해커톤</div>
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
        const lit = (sel, t, hold) => {{
          tl.to(sel, {{ borderColor: "#f18a54", scale: 1.04, duration: 0.2 }}, t);
          tl.to(sel, {{ borderColor: "rgba(255,255,255,0)", scale: 1, duration: 0.35 }}, t + hold);
        }};
        const flow = (sel, from, to, t) => {{
          tl.fromTo(sel, {{ x: from[0] - 7, y: from[1] - 7, opacity: 0 }}, {{ opacity: 1, duration: 0.08, immediateRender: false }}, t);
          tl.to(sel, {{ x: to[0] - 7, y: to[1] - 7, duration: 0.45, ease: "power1.inOut" }}, t);
          tl.to(sel, {{ opacity: 0, duration: 0.1 }}, t + 0.45);
        }};

        /* 초기 상태 */
        gsap.set("#stage", {{ scale: 1, transformOrigin: "{zA['origin']}" }});
        gsap.set(["#brand", "#cap2", "#cap3", "#cap4", "#cap5", "#call-cap", "#brand2"], {{ opacity: 0 }});
        gsap.set("#phone", {{ y: 900, opacity: 0 }});
        gsap.set(["#chip1", "#chip2", "#chip3"], {{ opacity: 0, scale: 0.6 }});
        gsap.set("#next-card", {{ opacity: 0 }});
        gsap.set(["#eta", "#l1", "#l2", "#l3"], {{ opacity: 0 }});
        gsap.set("#scr-alerts", {{ x: 390, opacity: 0 }});
        gsap.set("#toast", {{ yPercent: -140, opacity: 0 }});
        gsap.set("#finger", {{ opacity: 0 }});
        gsap.set("#call", {{ y: 60, opacity: 0 }});
        gsap.set("#st-end", {{ opacity: 0 }});
        gsap.set(".bub", {{ opacity: 0 }});
        gsap.set(["#wires-b", "#wires-f"], {{ opacity: 0 }});
        gsap.set([".node", "#hub"], {{ opacity: 0, x: -20 }});
        gsap.set("#fade", {{ opacity: 0 }});
        gsap.set(["#outro-bg", "#o-logo", "#o-sub", "#o-cta", "#o-credit"], {{ opacity: 0 }});
        document.querySelectorAll(".sub .band").forEach((b) => gsap.set(b, {{ opacity: 0, y: 16 }}));

        /* 자막: 시작에서 올라오고 끝에서 사라진다 */
        document.querySelectorAll(".sub").forEach((el) => {{
          const s = parseFloat(el.dataset.start), d = parseFloat(el.dataset.duration), band = el.querySelector(".band");
          tl.to(band, {{ opacity: 1, y: 0, duration: 0.25, ease: OUI }}, s);
          tl.to(band, {{ opacity: 0, duration: 0.2 }}, s + d - 0.25);
        }});

        /* 줌: 앱 설명·전화 구간 시작에 살짝 들어가고 끝에 돌아온다 */
        tl.set("#stage", {{ transformOrigin: "{zA['origin']}" }}, {fmt(app_s)});
        tl.to("#stage", {{ scale: {zA['scale']}, duration: {zA['dur']}, ease: "power2.inOut" }}, {fmt(app_s)});
        tl.to("#stage", {{ scale: 1, duration: {zA['dur']}, ease: "power2.inOut" }}, {fmt(app_e - zA['dur'])});
        tl.set("#stage", {{ transformOrigin: "{zC['origin']}" }}, {fmt(cs)});
        tl.to("#stage", {{ scale: {zC['scale']}, duration: {zC['dur']}, ease: "power2.inOut" }}, {fmt(cs)});
        tl.to("#stage", {{ scale: 1, duration: {zC['dur']}, ease: "power2.inOut" }}, {fmt(FADE_T - 1.2 - zC['dur'])});

        /* 앱 설명 구간 */
        const h = {fmt(bt['home'])}, f = {fmt(bt['forecast'])}, a = {fmt(bt['alerts'])}, to = {fmt(bt['toast'])}, d = {fmt(bt['depart'])}, o = {fmt(bt['out'])};
        tl.to("#wires-b", {{ opacity: 1, duration: 0.6 }}, {fmt(app_s + 0.5)});
        tl.to(["#nb0", "#nb1", "#nb2", "#nb3", "#nb4"], {{ opacity: 1, x: 0, duration: 0.4, ease: OUI, stagger: 0.08 }}, {fmt(app_s + 0.4)});
        tl.to("#hub", {{ opacity: 1, x: 0, duration: 0.4, ease: OUI }}, {fmt(app_s + 0.7)});
{FLOW_JS_B}
        tl.to(["#wires-b", "#nb0", "#nb1", "#nb2", "#nb3", "#nb4", "#hub"], {{ opacity: 0, duration: 0.7 }}, o);
        tl.to("#brand", {{ opacity: 1, duration: 0.4 }}, h - 0.1);
        tl.to("#phone", {{ y: 0, opacity: 1, duration: 0.75, ease: OUI }}, h);
        tl.fromTo("#cap2", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, h + 0.6);
        tl.to("#chip1", {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.6)" }}, h + 1.6);
        tl.to("#chip2", {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.6)" }}, h + 2.1);
        tl.to("#chip3", {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.6)" }}, h + 2.6);
        tl.to("#cap2", {{ opacity: 0, y: -12, duration: 0.3 }}, f - 0.2);
        tl.to("#home-scroll", {{ y: -200, duration: 0.5, ease: "power2.inOut" }}, f);
        tl.fromTo("#cap3", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, f + 0.2);
        tl.to("#loading", {{ opacity: 0, duration: 0.3 }}, f + 0.4);
        tl.to("#next-card", {{ opacity: 1, duration: 0.35 }}, f + 0.45);
        tl.to("#eta", {{ opacity: 1, duration: 0.2 }}, f + 0.8);
        const etaProxy = {{ m: 0 }};
        tl.to(etaProxy, {{ m: 265, duration: 0.6, ease: "power2.out", onUpdate() {{ const m = Math.round(etaProxy.m); document.getElementById("eta").textContent = pad(Math.floor(m / 60)) + ":" + pad(m % 60); }} }}, f + 0.8);
        tl.fromTo("#l1", {{ y: 12 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: OUI }}, f + 1.6);
        tl.fromTo("#l2", {{ y: 12 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: OUI }}, f + 2.0);
        tl.fromTo("#l3", {{ y: 12 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: OUI }}, f + 2.4);
        tl.to("#cap3", {{ opacity: 0, y: -12, duration: 0.3 }}, a - 0.2);
        tl.to("#finger", {{ opacity: 1, duration: 0.2 }}, a);
        tl.to("#finger", {{ scale: 0.82, duration: 0.1 }}, a + 0.3);
        tl.to("#finger", {{ scale: 1, duration: 0.18, ease: "back.out(2)" }}, a + 0.4);
        tl.to("#tab-ind", {{ x: 195, duration: 0.3, ease: OUI }}, a + 0.3);
        tl.to("#tab0", {{ color: "#55636b", duration: 0.2 }}, a + 0.3);
        tl.to("#tab2", {{ color: "#193b50", duration: 0.2 }}, a + 0.3);
        tl.to("#scr-home", {{ x: -390, opacity: 0, duration: 0.4, ease: "power2.inOut" }}, a + 0.3);
        tl.to("#scr-alerts", {{ x: 0, opacity: 1, duration: 0.4, ease: "power2.inOut" }}, a + 0.3);
        tl.fromTo("#cap4", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, a + 0.5);
        tl.to("#finger", {{ x: -49, y: -392, duration: 0.55, ease: "power2.inOut" }}, a + 1.2);
        tl.to("#finger", {{ scale: 0.82, duration: 0.1 }}, a + 1.8);
        tl.to("#finger", {{ scale: 1, duration: 0.18, ease: "back.out(2)" }}, a + 1.9);
        tl.to("#apply", {{ scale: 0.97, duration: 0.1 }}, a + 1.8);
        tl.to("#apply", {{ scale: 1, duration: 0.2, ease: "back.out(2)" }}, a + 1.9);
        tl.to("#finger", {{ opacity: 0, duration: 0.25 }}, a + 2.2);
        tl.to("#toast", {{ yPercent: 0, opacity: 1, duration: 0.4, ease: OUI }}, to);
        tl.to("#cap4", {{ opacity: 0, y: -12, duration: 0.3 }}, d - 0.2);
        tl.to("#tab-ind", {{ x: 0, duration: 0.3, ease: OUI }}, d);
        tl.to("#tab2", {{ color: "#55636b", duration: 0.2 }}, d);
        tl.to("#tab0", {{ color: "#193b50", duration: 0.2 }}, d);
        tl.to("#scr-home", {{ x: 0, opacity: 1, duration: 0.4, ease: "power2.inOut" }}, d);
        tl.to("#scr-alerts", {{ x: 390, opacity: 0, duration: 0.4, ease: "power2.inOut" }}, d);
        tl.to("#toast", {{ yPercent: -140, opacity: 0, duration: 0.35, ease: "power2.in" }}, d + 0.2);
        tl.fromTo("#cap5", {{ y: 16 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, d + 0.5);
        tl.to("#home-scroll", {{ y: -300, duration: 0.55, ease: "power2.inOut" }}, d + 0.6);
        tl.to("#depart", {{ scale: 1.04, duration: 0.25 }}, d + 1.3);
        tl.to("#depart", {{ scale: 1, duration: 0.4, ease: OUI }}, d + 1.55);
        tl.to(["#phone", "#brand", "#cap5"], {{ opacity: 0, duration: 0.7 }}, o);

        /* 전화 구간 */
        tl.to("#wires-f", {{ opacity: 1, duration: 0.6 }}, {fmt(cs + 0.5)});
        tl.to(["#nf0", "#nf1", "#nf2", "#nf3", "#nf4", "#nf5", "#nf6"], {{ opacity: 1, x: 0, duration: 0.4, ease: OUI, stagger: 0.07 }}, {fmt(cs + 0.3)});
{FLOW_JS_F}
        tl.to(["#wires-f", "#nf0", "#nf1", "#nf2", "#nf3", "#nf4", "#nf5", "#nf6"], {{ opacity: 0, duration: 0.6 }}, {fmt(FADE_T - 0.6)});
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
        tl.fromTo("#o-credit", {{ y: 12 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: OUI }}, {fmt(OUTRO_T + 1.5)});

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
    extra = "0123456789:·~%.,!?→⚓📞📣🔔🦀🦑🐚🚢🚗🛰📋📊🚚☎🎙🧠🔊 ()tkm통화종료중"
    chars = {c for c in (set(text) | set(extra)) if not c.isspace()}
    if not FONT_SRC.exists():
        print("폰트 원본 없음(윈도우가 아닌 듯): " + ("기존 서브셋 사용" if FONT_SUB.exists() else "시스템 폰트로 대체됨 — 렌더 글꼴이 달라질 수 있음"))
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
