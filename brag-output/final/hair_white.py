"""촬영분에서 오른쪽 사람(할아버지 역)의 머리카락만 은백색으로 바꾼다(10/13 오너 요청 '백발').

mediapipe 얼굴 검출(blaze_face_short_range) + 다중 분할(selfie_multiclass_256x256, hair 채널)을 쓴다.
화면 오른쪽 45% 안에서 가장 오른쪽 얼굴을 할아버지로 보고(청년은 늘 왼쪽), 그 머리 주변만 잘라 분할한다.
얼굴을 잠깐 못 찾으면(옆으로 누울 때) 마지막 자리 주변을 3초까지 넓게 본다. 마스크는 앞 프레임과 섞어 깜빡임을 줄인다.
색은 명도 감마(0.32)로 밝혀 은회색 — 결의 음영은 그대로 남는다.

준비: pip install mediapipe opencv-python numpy, ffmpeg. 모델 두 개는 구글 저장소에서 받는다:
  https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite
  https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite
실행: python hair_white.py <모델 폴더> <원본 footage.mp4> <출력 footage.mp4>   (1920×1080 30fps 기준 약 10분, 소리는 그대로 복사)
"""
import sys, cv2, numpy as np, pathlib, subprocess
sys.stdout.reconfigure(encoding="utf-8")
import mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
M, SRC, DST = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=mpp.BaseOptions(model_asset_path=str(M/"selfie_multiclass_256x256.tflite")), output_confidence_masks=True))
det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(base_options=mpp.BaseOptions(model_asset_path=str(M/"blaze_face_short_range.tflite")), min_detection_confidence=0.4))
cap = cv2.VideoCapture(SRC); W, H = int(cap.get(3)), int(cap.get(4)); fps = cap.get(5); N = int(cap.get(7))
ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps}", "-i", "-", "-i", SRC,
                       "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", DST], stdin=subprocess.PIPE)
def faces(bgr):
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    return [(d.bounding_box.origin_x, d.bounding_box.origin_y, d.bounding_box.width, d.bounding_box.height) for d in r.detections]
def hair_mask(bgr, face, k):
    x, y, w, h = face
    cx, cy = x + w/2, y + h*0.25; s = int(max(w, h) * k)
    x0, y0 = int(max(0, cx - s/2)), int(max(0, cy - s/2)); x1, y1 = int(min(W, cx + s/2)), int(min(H, cy + s/2))
    if x1 - x0 < 32 or y1 - y0 < 32: return None
    crop = bgr[y0:y1, x0:x1]
    r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
    hm = cv2.resize(r.confidence_masks[1].numpy_view(), (x1-x0, y1-y0))
    full = np.zeros((H, W), np.float32); full[y0:y1, x0:x1] = hm
    return full
def whiten(bgr, m, gamma=0.32):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    w = np.clip(255 * np.power(g, gamma) * 0.92 + 8, 0, 255)
    white = cv2.merge([w, w * 0.995, w * 0.985])
    m3 = cv2.merge([m, m, m])
    return (bgr.astype(np.float32) * (1 - m3) + white * m3).astype(np.uint8)
prev_m, last_box, last_seen, i = None, None, -999, 0
while True:
    ok, bgr = cap.read()
    if not ok: break
    fs = [f for f in faces(bgr) if f[0] + f[2]/2 > 0.45 * W]
    box = None
    if fs:
        box = max(fs, key=lambda b: b[0] + b[2]/2); last_box, last_seen = box, i; k = 3.0
    elif last_box is not None and i - last_seen < 90:
        box, k = last_box, 4.0          # 잠깐 못 찾으면 마지막 자리 주변을 넓게
    m = hair_mask(bgr, box, k) if box else None
    if m is None: m = np.zeros((H, W), np.float32)
    m = np.clip((m - 0.2) / 0.5, 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 2)
    if prev_m is not None: m = 0.65 * m + 0.35 * prev_m
    prev_m = m
    out = whiten(bgr, m) if m.max() > 0.05 else bgr
    ff.stdin.write(out.tobytes()); i += 1
    if i % 150 == 0: print(f"{i}/{N} t={i/fps:.1f}s box={box}", flush=True)
ff.stdin.close(); ff.wait(); print("done", i)
