"""timeline.json 의 컷을 원본에서 잘라 1920×1080 30fps 촬영분 하나(composition/assets/live/footage.mp4)로 잇는다.

컷마다:
  · fit  cover(가로 꽉) | pillar(세로 영상 가운데 + 양옆은 같은 영상을 흐리게) | black(검은 화면, 원본 소리만 작게. src 없으면 무음)
  · rotate ccw   폰을 눕혀 찍은 세로 파일을 가로로 세운다
  · mosaic       얼굴 모자이크(mediapipe blaze_face_short_range, 화면을 짧은 변의 절반 크기 조각으로 나눠 작은 얼굴도 잡는다).
                 잡은 자리를 앞뒤 1초 동안 가려 놓친 프레임(옆얼굴·처음 보이는 순간)도 가린다
  · blur         화면 전체를 흐리게(인터뷰이·간판까지 알아볼 수 없게, 10/13 오너)
  · voice        음성변조(음높이 0.85배, 빠르기는 그대로)
  · grade doc    인터뷰 톤(채도·밝기 낮추고 푸른 기)
실제 길이는 composition/assets/live/shots.json 에 적어 build.py 가 자막 시각을 맞춘다.

준비: ffmpeg, 얼굴 모델 blaze_face_short_range.tflite
  https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite
실행: uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless python prep.py <원본 영상 폴더> <모델 파일>
"""
import json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SRC_DIR, MODEL = Path(sys.argv[1]), Path(sys.argv[2])
LIVE = HERE / "composition" / "assets" / "live"
TMP = LIVE / "shots"
TMP.mkdir(parents=True, exist_ok=True)
cfg = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
W, H, FPS = 1920, 1080, 30
ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, a)], check=True)


def duration(p: Path) -> float:
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def mosaic(src: Path, dst: Path) -> None:
    import cv2, mediapipe as mp
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=mpp.BaseOptions(model_asset_path=str(MODEL)), min_detection_confidence=0.55))
    cap = cv2.VideoCapture(str(src)); w, h, fps = int(cap.get(3)), int(cap.get(4)), cap.get(5)
    T, HOLD, PAD = min(w, h) // 2, int(fps), 0.5
    xs = sorted({*range(0, max(1, w - T + 1), T // 2), max(0, w - T)})
    ys = sorted({*range(0, max(1, h - T + 1), T // 2), max(0, h - T)})
    # 1단계: 프레임마다 얼굴 자리를 모은다. 조각의 절반보다 크거나 화면 아래 40%에 있는 '얼굴'은 하늘·상자 오검출이라 버린다
    found = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB); boxes = []
        for y in ys:
            for x in xs:
                for d in det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb[y:y + T, x:x + T].copy())).detections:
                    bb = d.bounding_box
                    if bb.width > T * 0.5 or y + bb.origin_y + bb.height / 2 > h * 0.6:   # 서 있는 사람 얼굴은 화면 위 60% 안 — 아래는 홍게 상자 오검출
                        continue
                    pw, ph = bb.width * PAD, bb.height * PAD
                    boxes.append((max(0, int(x + bb.origin_x - pw)), max(0, int(y + bb.origin_y - ph * 1.4)),
                                  min(w, int(x + bb.origin_x + bb.width + pw)), min(h, int(y + bb.origin_y + bb.height + ph))))
        found.append(boxes)
    cap.release()
    # 2단계: 각 자리를 앞뒤 1초 동안 가린다 — 얼굴이 처음 보이는 순간·옆얼굴로 놓친 프레임까지
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-",
                          "-i", str(src), "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)],
                         stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(src)); n = len(found)
    for i in range(n):
        ok, f = cap.read()
        if not ok:
            break
        for x0, y0, x1, y1 in {bx for j in range(max(0, i - HOLD), min(n, i + HOLD + 1)) for bx in found[j]}:
            if x1 - x0 > 4 and y1 - y0 > 4:
                cell = max(8, (x1 - x0) // 9)
                small = cv2.resize(f[y0:y1, x0:x1], (max(1, (x1 - x0) // cell), max(1, (y1 - y0) // cell)), interpolation=cv2.INTER_AREA)
                f[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait(); cap.release()
    if p.returncode:
        raise SystemExit(f"모자이크 인코딩 실패: {src.name}")
    print(f"    모자이크 {n}프레임")


def build_shot(i: int, s: dict) -> Path:
    out = TMP / f"{i:02d}_{s['id']}.mp4"
    dur = round((s.get("duration") or s["out"] - s["in"]) * FPS) / FPS
    fix = ["-frames:v", round(dur * FPS), "-t", dur]
    if s["fit"] == "black":
        if "src" in s:
            ff("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}", "-ss", s["in"], "-t", dur, "-i", SRC_DIR / s["src"],
               "-map", "0:v", "-map", "1:a", "-af", f"volume={s.get('vol', 0.4)},afade=t=in:d=0.4,afade=t=out:st={dur - 0.4}:d=0.4",
               *fix, *ENC, out)
        else:
            ff("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", *fix, *ENC, out)
        return out

    raw = TMP / f"{i:02d}_{s['id']}_raw.mp4"
    ff("-ss", s["in"], "-t", dur + 0.5, "-i", SRC_DIR / s["src"], "-c:v", "libx264", "-crf", "14", "-c:a", "aac", "-b:a", "256k", raw)
    if s.get("mosaic"):
        m = raw.with_name(raw.stem + "_m.mp4"); mosaic(raw, m); raw = m

    v = "transpose=2," if s.get("rotate") == "ccw" else ""
    blur = ",gblur=sigma=22" if s.get("blur") else ""
    grade = ",eq=saturation=0.55:contrast=1.06:brightness=-0.03,colorbalance=bs=0.07:bm=0.03,vignette=PI/4.5" if s.get("grade") == "doc" else ""
    if s["fit"] == "cover":
        vf = f"[0:v]{v}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1{blur}{grade}[v]"
    else:
        vf = (f"[0:v]{v}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.18[bg];"
              f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1{blur}{grade}[v]")
    af = "asetrate=48000*0.85,aresample=48000,atempo=1.17647," if s.get("voice") else ""
    af += f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad,atrim=0:{dur},afade=t=in:d=0.08"
    ff("-i", raw, "-filter_complex", vf, "-map", "[v]", "-map", "0:a", "-af", af, *fix, *ENC, out)
    return out


parts = []
for i, s in enumerate(cfg["shots"]):
    print(f"[{i:02d}] {s['id']}")
    parts.append(build_shot(i, s))

# concat 필터로 다시 인코딩한다 — concat 분리기(-c copy)는 컷마다 AAC 앞 여백이 쌓여 뒤로 갈수록 입과 소리가 어긋났다
footage = LIVE / "footage.mp4"
ins = [a for p in parts for a in ("-i", p)]
graph = "".join(f"[{k}:v][{k}:a]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
ff(*ins, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", *ENC, "-movflags", "+faststart", footage)
info = [{"id": s["id"], "dur": round(duration(p), 3)} for s, p in zip(cfg["shots"], parts)]
(LIVE / "shots.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"footage.mp4 {duration(footage):.2f}초 ({len(parts)}컷)")
