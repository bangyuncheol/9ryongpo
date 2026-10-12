"""촬영 전 자리표시 영상 만들기.

scenes.json 의 장면마다 composition/assets/live/<file> 이 **없을 때만** 회색 바탕에 장면 제목·촬영 메모를 적은
영상(무음 오디오 트랙 포함)을 만든다. 이미 파일이 있으면(촬영분을 넣었으면) 절대 덮어쓰지 않는다.

기본은 글자 없는 초록 화면(크로마키 그린 #00FF00). 장면 제목·촬영 메모를 적은 회색 화면은 --labels.

실행: python make_placeholders.py              (FFmpeg 필요)
글자 버전: python make_placeholders.py --labels   (폰트는 윈도우 맑은 고딕, 맥은 AppleSDGothicNeo 자동 선택)
강제 재생성: python make_placeholders.py --force   (촬영분이 들어 있으면 그 파일은 건너뛴다. 자리표시만 다시 만든다)
"""
from __future__ import annotations

import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = HERE / "composition" / "assets" / "live"
MARK = "placeholder"  # 자리표시 영상의 metadata comment. 이 표식이 있는 파일만 --force 로 다시 만든다


def font_path() -> Path | None:
    cands = {
        "Windows": [Path(r"C:/Windows/Fonts/malgun.ttf")],
        "Darwin": [Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"), Path("/Library/Fonts/AppleGothic.ttf")],
    }.get(platform.system(), [])
    cands += [Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")]
    return next((p for p in cands if p.exists()), None)


def is_placeholder(path: Path) -> bool:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, encoding="utf-8").stdout
    except FileNotFoundError:
        return False
    return MARK in out


def make(scene: dict, font: Path | None, labels: bool) -> None:
    out = LIVE / scene["file"]
    dur = float(scene["duration"])
    if not labels:  # 초록 빈 화면
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x00FF00:s=1920x1080:r=30:d={dur}",
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(dur), "-shortest",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18",
               "-c:a", "aac", "-b:a", "64k", "-metadata", f"comment={MARK}", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
        print(f"만듦  {out.relative_to(HERE)}  ({dur:.0f}초, 초록 화면)")
        return
    lines = [f"촬영분 {scene['id']} · {scene['title']}", "", scene.get("shot", ""), "",
             f"길이 {dur:.0f}초 · 이 파일 이름으로 교체: assets/live/{scene['file']}"]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(lines))
        textfile = Path(f.name)
    fontopt = f"fontfile='{font.as_posix().replace(':', chr(92) + ':')}':" if font else ""
    draw = (f"drawtext={fontopt}textfile='{textfile.as_posix().replace(':', chr(92) + ':')}':"
            "expansion=none:fontcolor=white:fontsize=44:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2:text_align=C")
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=0x2b3f4e:s=1920x1080:r=30:d={dur}",
           "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
           "-vf", draw, "-t", str(dur), "-shortest",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "64k", "-metadata", f"comment={MARK}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    textfile.unlink(missing_ok=True)
    print(f"만듦  {out.relative_to(HERE)}  ({dur:.0f}초)")


def main() -> None:
    force = "--force" in sys.argv
    labels = "--labels" in sys.argv
    scenes = json.loads((HERE / "scenes.json").read_text(encoding="utf-8"))["scenes"]
    LIVE.mkdir(parents=True, exist_ok=True)
    font = font_path()
    if font is None:
        print("경고: 한글 폰트를 못 찾아 자리표시 글자가 깨질 수 있습니다.")
    for sc in scenes:
        out = LIVE / sc["file"]
        if out.exists() and out.stat().st_size > 0:
            if force and is_placeholder(out):
                make(sc, font, labels)
            else:
                print(f"있음  {out.relative_to(HERE)}  (건드리지 않음{' · 촬영분' if not is_placeholder(out) else ''})")
            continue
        make(sc, font, labels)


if __name__ == "__main__":
    main()
