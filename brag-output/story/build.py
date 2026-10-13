"""timeline.json + assets/live/shots.json → composition/index.html (배마중 취재영상, 가로 1920×1080).

prep.py 가 이어 붙인 촬영분(footage.mp4)을 바닥에 깔고 그 위에
  · 자막: 원본 초(t/end) → 컷 시작 + (t - in). 인터뷰는 말한 사람 표시(Q = 우리 팀)
  · 검은 카드: 한 글자씩 찍히는 타자기 문장(추적 60분 톤)
  · 인터뷰 컷: 왼쪽 위 ● REC, 오른쪽 위 누구인지, 왼쪽 아래 '음성변조' 표시
  · 몽타주 캡션·두 번째 방문 표시·데이터 한 줄(실제 위판 실적)
  · 아웃트로: 앱 아이콘 + 워드마크 + 한 줄 설명 + 주소
를 얹는다. 문장·시각은 timeline.json 에서만 고친다.

글꼴: Noto Sans KR 에서 쓰는 글자만 추려 assets/fonts/NotoSansKR-subset.ttf 로 넣는다. 원본은 NOTO_KR_TTF(없으면 기존 서브셋 유지).
실행: python build.py  →  cd composition && npx --yes hyperframes@0.8.146 check && npx --yes hyperframes@0.8.146 render --quality looks --output ../배마중_취재영상.mp4
"""
import json, os, re, subprocess, sys
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
COMP = HERE / "composition"
cfg = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
real = {s["id"]: s["dur"] for s in json.loads((COMP / "assets/live/shots.json").read_text(encoding="utf-8"))}
W, H = 1920, 1080
CORAL, BRAND = "#e8604c", "#073f4c"
fmt = lambda x: f"{x:.3f}".rstrip("0").rstrip(".")

clips, js = [], []
t0 = 0.0
for s in cfg["shots"]:
    d = real[s["id"]]
    sid = s["id"]
    for j, sub in enumerate(s.get("subs", [])):
        a = t0 + sub["t"] - s["in"]; b = min(t0 + d, t0 + sub["end"] - s["in"])
        who = sub.get("who")
        tag = f'<span class="who">{escape(who)}</span>' if who else ""
        clips.append(f'<div id="sub-{sid}-{j}" class="clip sub" data-start="{fmt(a)}" data-duration="{fmt(b - a)}" data-track-index="1">'
                     f'{tag}<p class="txt">{escape(sub["text"])}</p></div>')
    if s.get("card"):
        lines = s["card"]; step = (d - 1.2) / len(lines)
        spans = "".join(f'<p class="ln">{"".join(f"<i>{escape(c)}</i>" for c in ln)}</p>' for ln in lines)
        clips.append(f'<section id="card-{sid}" class="clip card" data-start="{fmt(t0)}" data-duration="{fmt(d)}" data-track-index="2">{spans}</section>')
        for k in range(len(lines)):
            js.append(f'tl.to("#card-{sid} .ln:nth-child({k + 1}) i", {{ opacity: 1, duration: 0.01, stagger: {fmt(min(0.07, step * 0.6 / max(1, len(lines[k]))))} }}, {fmt(t0 + 0.3 + k * step)});')
        js.append(f'tl.to("#card-{sid}", {{ opacity: 0, duration: 0.3 }}, {fmt(t0 + d - 0.35)});')
    if s.get("hud"):
        clips.append(f'<div id="hud-{sid}" class="clip hud" data-start="{fmt(t0)}" data-duration="{fmt(d)}" data-track-index="3">'
                     f'<span class="rec"><b></b>REC</span><span class="vc">음성변조</span></div>')
        js.append(f'tl.to("#hud-{sid} .rec b", {{ opacity: 0.15, duration: 0.5, repeat: {max(1, int(d / 0.5) - 1)}, yoyo: true, ease: "steps(1)" }}, {fmt(t0)});')
    if s.get("caption"):
        # 캡션은 그 컷부터 caption_len 초 — 앞뒤 컷 자막과 겹치지 않게(자막은 한 번에 하나)
        cl = s.get("caption_len", d)
        clips.append(f'<div id="cap-{sid}" class="clip cap" data-start="{fmt(t0)}" data-duration="{fmt(cl)}" data-track-index="4">{escape(s["caption"])}</div>')
        js.append(f'tl.from("#cap-{sid}", {{ opacity: 0, y: 14, duration: 0.4, ease: "power2.out" }}, {fmt(t0)});')
    if s.get("chip"):
        a = t0 + d - 3.2
        clips.append(f'<div id="chip-{sid}" class="clip chip" data-start="{fmt(a)}" data-duration="{fmt(t0 + d - a)}" data-track-index="4">{escape(s["chip"])}</div>')
        js.append(f'tl.from("#chip-{sid}", {{ opacity: 0, x: -24, duration: 0.4, ease: "power2.out" }}, {fmt(a)});')
    if s.get("data"):
        a = t0 + 1.5
        clips.append(f'<div id="data-{sid}" class="clip data" data-start="{fmt(a)}" data-duration="{fmt(min(3.0, t0 + d - a))}" data-track-index="5">{escape(s["data"])}</div>')
        js.append(f'tl.from("#data-{sid}", {{ opacity: 0, y: 10, duration: 0.35 }}, {fmt(a)});')
    t0 += d

FOOT = t0
O = cfg["outro"]
TOTAL = round(FOOT + O["duration"], 3)

HTML = f"""<!doctype html>
<html lang="ko" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>배마중 취재영상</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family:"Noto Sans KR"; src:url("assets/fonts/NotoSansKR-subset.ttf") format("truetype"); font-weight:100 900; font-display:block; }}
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html, body {{ width:{W}px; height:{H}px; overflow:hidden; background:#000; color:#fff;
                   font-family:"Noto Sans KR",sans-serif; }}
      #root {{ position:relative; width:{W}px; height:{H}px; }}
      #footage {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
      /* 자막: 시사 프로그램식 — 검은 기울어진 이름표(빨간 그림자) + 굵은 흰 글자에 검은 테두리, 가운데 아래 (10/13 오너 참고 이미지·가운데 정렬) */
      .sub {{ position:absolute; left:90px; right:90px; bottom:64px; display:flex; flex-direction:column; align-items:center; text-align:center; gap:14px; }}
      .who {{ display:inline-block; padding:6px 30px 8px; background:#151515; color:#fff; font-size:44px; font-weight:900; transform:skewX(-10deg); box-shadow:10px 8px 0 #d6312b; }}
      .txt {{ max-width:1600px; font-size:62px; font-weight:800; line-height:1.28; color:#fff; word-break:keep-all;
             -webkit-text-stroke:9px #111; paint-order:stroke fill; text-shadow:0 3px 12px rgba(0,0,0,.6); }}
      .card {{ position:absolute; inset:0; background:#000; display:flex; flex-direction:column; justify-content:center; padding-left:260px; gap:26px; }}
      .card .ln {{ font-size:72px; font-weight:700; letter-spacing:-0.01em; }}
      .card .ln:first-child {{ color:{CORAL}; }}
      .card i {{ font-style:normal; opacity:0; }}
      .hud {{ position:absolute; inset:0; }}
      .hud .rec {{ position:absolute; left:56px; top:48px; font-size:34px; font-weight:700; line-height:1; letter-spacing:.08em; display:flex; align-items:center; gap:14px; }}
      .hud .rec b {{ width:22px; height:22px; border-radius:50%; background:#e53935; }}
      .hud .vc {{ position:absolute; right:56px; top:44px; padding:6px 16px; background:rgba(0,0,0,.6); font-size:28px; font-weight:700; }}
      .cap {{ position:absolute; left:90px; right:90px; bottom:64px; text-align:center; font-size:62px; font-weight:800; line-height:1.28; word-break:keep-all;
             -webkit-text-stroke:9px #111; paint-order:stroke fill; text-shadow:0 3px 12px rgba(0,0,0,.6); }}
      .chip {{ position:absolute; left:56px; top:56px; padding:12px 24px; background:{CORAL}; font-size:36px; font-weight:800; }}
      .data {{ position:absolute; left:50%; top:40px; transform:translateX(-50%); padding:10px 24px; background:{CORAL}; font-size:34px; font-weight:800; white-space:nowrap; }}
      #outro {{ position:absolute; inset:0; background:#f6f8f8; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:30px; }}
      #o-logo {{ display:flex; align-items:center; gap:28px; }}
      #o-logo img.ic {{ height:150px; border-radius:34px; }}
      #o-logo img.wm {{ height:110px; }}
      #o-sub {{ font-size:46px; font-weight:700; color:{BRAND}; }}
      #o-url {{ font-size:40px; font-weight:800; color:{CORAL}; letter-spacing:.02em; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{fmt(TOTAL)}" data-width="{W}" data-height="{H}">
      <!-- 렌더러가 영상을 2프레임 늦게 찍어(완성본을 촬영분과 프레임 비교해 확인) 영상만 2프레임 앞에서 시작하고, 소리는 따로 정시에 깐다 -->
      <video id="footage" src="assets/live/footage.mp4" playsinline muted data-media-start="{fmt(2 / 30)}" data-start="0" data-duration="{fmt(FOOT)}" data-track-index="0"></video>
      <audio id="footage-audio" src="assets/live/footage.m4a" data-start="0" data-duration="{fmt(FOOT)}" data-track-index="9"></audio>
      {chr(10).join("      " + c for c in clips).lstrip()}
      <section id="outro" class="clip" data-start="{fmt(FOOT)}" data-duration="{fmt(O['duration'])}" data-track-index="6">
        <div id="o-logo"><img class="ic" src="assets/brand/icon.png" alt="" /><img class="wm" src="assets/brand/wordmark.png" alt="배마중" /></div>
        <div id="o-sub">{escape(O['line'])}</div>
        <div id="o-url">{escape(O['url'])}</div>
      </section>
    </div>
    <script>
      // timeline.json 에서 생성됨 — 직접 고치지 말고 build.py 를 다시 돌린다.
      window.__timelines = window.__timelines || {{}};
      document.fonts.ready.then(() => {{
        const tl = gsap.timeline({{ paused: true }});
        {(chr(10) + "        ").join(js)}
        tl.from("#o-logo", {{ opacity: 0, scale: 0.85, duration: 0.5, ease: "back.out(1.4)" }}, {fmt(FOOT + 0.3)});
        tl.from("#o-sub", {{ opacity: 0, y: 16, duration: 0.4 }}, {fmt(FOOT + 0.8)});
        tl.from("#o-url", {{ opacity: 0, y: 16, duration: 0.4 }}, {fmt(FOOT + 1.1)});
        tl.to({{}}, {{ duration: 0.01 }}, {fmt(TOTAL - 0.01)});
        window.__timelines["main"] = tl;
        if (window.__hfForceTimelineRebind) window.__hfForceTimelineRebind();
      }});
    </script>
  </body>
</html>
"""
(COMP / "index.html").write_text(HTML, encoding="utf-8")
print(f"index.html 생성 — 총 {TOTAL:.1f}초 (촬영분 {FOOT:.1f}초 + 아웃트로 {O['duration']:g}초)")

# 글꼴 서브셋(final/build.py 와 같은 방식)
src = Path(os.environ.get("NOTO_KR_TTF", r"C:/Windows/Fonts/NotoSansKR-VF.ttf"))
sub = COMP / "assets" / "fonts" / "NotoSansKR-subset.ttf"
if src.exists():
    chars = set(re.sub(r"<[^>]+>", " ", HTML.split("<body>", 1)[1].split("<script>", 1)[0])) | set("0123456789RECbmj.kr·~“”")
    glyphs = HERE / ".glyphs.txt"; glyphs.write_text("".join(sorted(c for c in chars if not c.isspace())), encoding="utf-8")
    sub.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["uvx", "--from", "fonttools", "pyftsubset", str(src), f"--text-file={glyphs}", f"--output-file={sub}", "--layout-features=*"], check=True)
        print(f"글꼴 서브셋 {sub.stat().st_size // 1024}KB")
    finally:
        glyphs.unlink(missing_ok=True)
else:
    print("글꼴 원본 없음(NOTO_KR_TTF 로 지정): " + ("기존 서브셋 사용" if sub.exists() else "서브셋 없음 — 렌더 글꼴이 달라짐"))
