"""배마중_발표.html 의 장별 발표 메모(aside.notes)와 출처를 뽑아 배마중_발표_노트.md 로 쓴다.

PDF 를 이미지로 떠서 PPT 에 붙일 때 각 장의 노트에 넣는 용도. HTML 을 고친 뒤 `python make_notes.py` 를 다시 돌린다.
출처는 화면에서 뺐고(9판, 10/13) 발표 메모 끝에 '출처:' 로 들어 있다.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "배마중_발표.html"
OUT = HERE / "배마중_발표_노트.md"


def clean(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def main() -> None:
    s = SRC.read_text(encoding="utf-8")
    out = [
        "# 배마중 발표 슬라이드 노트(발표 메모 + 출처)",
        "",
        "PDF를 이미지로 떠서 PPT에 붙일 때 각 장의 노트에 넣는 글. `배마중_발표.html`의 발표 메모(N 키)와 같은 내용이며, "
        "화면에서 뺀 출처 줄은 여기와 발표 메모에만 있다. HTML을 고치면 `python make_notes.py`로 다시 만든다.",
        "",
    ]
    n = 0
    for m in re.finditer(r"<!-- (\d+) ([^\n]+?) -->\n<section.*?</section>\n", s, re.S):
        n += 1
        num, title, block = m.group(1), m.group(2), m.group(0)
        h = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        head = clean(h.group(1)).replace("\n", " ") if h else ""
        notes_m = re.search(r'<aside class="notes">(.*?)</aside>', block, re.S)
        notes = clean(notes_m.group(1)) if notes_m else ""
        memo, src = notes, ""
        if "\n\n출처: " in notes:
            memo, src = notes.split("\n\n출처: ", 1)
        out += [f"## {num}. {title}" + (f": {head}" if head else ""), ""]
        out += ["**발표 메모**", "", memo or "(없음)", ""]
        out += ["**출처**", "", src or "(없음)", ""]
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{OUT.name}: {n}장")


if __name__ == "__main__":
    main()
