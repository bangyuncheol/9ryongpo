"""timeline.json 의 컷을 원본에서 잘라 1920×1080 30fps 촬영분 하나(composition/assets/live/footage.mp4)로 잇는다.

컷마다:
  · fit  cover(가로 꽉) | pillar(세로 영상 가운데 + 양옆은 같은 영상을 흐리게) | black(검은 화면, 원본 소리만 작게. src 없으면 무음)
  · rotate ccw   폰을 눕혀 찍은 세로 파일을 가로로 세운다
  · mosaic       얼굴 모자이크(mediapipe blaze_face_short_range, 화면을 480px 조각으로 나눠 작은 얼굴도 잡는다).
                 한 번 잡은 자리는 12프레임 동안 유지해 놓친 프레임도 가린다
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
        base_options=mpp.BaseOptions(model_asset_path=str(MODEL)), min_detection_confidence=0.6))
    T, HOLD, PAD = 480, 12, 0.45
    cap = cv2.VideoCapture(str(src)); w, h, fps = int(cap.get(3)), int(cap.get(4)), cap.get(5)
    xs = sorted({*range(0, max(1, w - T + 1), T // 2), max(0, w - T)})
    ys = sorted({*range(0, max(1, h - T + 1), T // 2), max(0, h - T)})
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-",
                          "-i", str(src), "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)],
                         stdin=subprocess.PIPE)
    live = []   # [x0, y0, x1, y1, 남은 프레임]
    n = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        for y in ys:
            for x in xs:
                tile = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb[y:y + T, x:x + T].copy())
                for d in det.detect(tile).detections:
                    b = d.bounding_box; pw, ph = b.width * PAD, b.height * PAD
                    live.append([max(0, int(x + b.origin_x - pw)), max(0, int(y + b.origin_y - ph * 1.4)),
                                 min(w, int(x + b.origin_x + b.width + pw)), min(h, int(y + b.origin_y + b.height + ph)), HOLD])
        for bx in live:
            x0, y0, x1, y1, _ = bx
            if x1 - x0 > 4 and y1 - y0 > 4:
                cell = max(8, (x1 - x0) // 9)
                small = cv2.resize(f[y0:y1, x0:x1], (max(1, (x1 - x0) // cell), max(1, (y1 - y0) // cell)), interpolation=cv2.INTER_AREA)
                f[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
            bx[4] -= 1
        live = [b for b in live if b[4] > 0]
        p.stdin.write(f.tobytes()); n += 1
    p.stdin.close(); p.wait(); cap.release()
    if p.returncode:
        raise SystemExit(f"모자이크 인코딩 실패: {src.name}")
    print(f"    모자이크 {n}프레임")


def build_shot(i: int, s: dict) -> Path:
    out = TMP / f"{i:02d}_{s['id']}.mp4"
    if s["fit"] == "black":
        dur = s.get("duration") or s["out"] - s["in"]
        if "src" in s:
            ff("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}", "-ss", s["in"], "-t", dur, "-i", SRC_DIR / s["src"],
               "-map", "0:v", "-map", "1:a", "-af", f"volume={s.get('vol', 0.4)},afade=t=in:d=0.4,afade=t=out:st={dur - 0.4}:d=0.4",
               "-t", dur, *ENC, out)
        else:
            ff("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", dur, *ENC, out)
        return out

    raw = TMP / f"{i:02d}_{s['id']}_raw.mp4"
    ff("-ss", s["in"], "-t", s["out"] - s["in"], "-i", SRC_DIR / s["src"], "-c:v", "libx264", "-crf", "14", "-c:a", "aac", "-b:a", "256k", raw)
    if s.get("mosaic"):
        m = raw.with_name(raw.stem + "_m.mp4"); mosaic(raw, m); raw = m

    v = "transpose=2," if s.get("rotate") == "ccw" else ""
    grade = ",eq=saturation=0.55:contrast=1.06:brightness=-0.03,colorbalance=bs=0.07:bm=0.03,vignette=PI/4.5" if s.get("grade") == "doc" else ""
    if s["fit"] == "cover":
        vf = f"[0:v]{v}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1{grade}[v]"
    else:
        vf = (f"[0:v]{v}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.18[bg];"
              f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1{grade}[v]")
    af = "asetrate=48000*0.85,aresample=48000,atempo=1.17647," if s.get("voice") else ""
    af += "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.08"
    ff("-i", raw, "-filter_complex", vf, "-map", "[v]", "-map", "0:a", "-af", af, *ENC, out)
    return out


parts = []
for i, s in enumerate(cfg["shots"]):
    print(f"[{i:02d}] {s['id']}")
    parts.append(build_shot(i, s))

lst = TMP / "list.txt"
lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
footage = LIVE / "footage.mp4"
ff("-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", footage)
info = [{"id": s["id"], "dur": round(duration(p), 3)} for s, p in zip(cfg["shots"], parts)]
(LIVE / "shots.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"footage.mp4 {duration(footage):.2f}초 ({len(parts)}컷)")
