from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

IMG_DIR = Path(__file__).resolve().parent / "beijing_awards_work" / "images"
engine = RapidOCR()

targets = [f"{i:03d}.png" for i in range(19, 86)]

for fname in targets:
    path = IMG_DIR / fname
    result, _ = engine(str(path))
    nums = []
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        if max(xs) <= 170 and re.fullmatch(r"\d{1,3}", text.strip()):
            nums.append((min(ys), text.strip()))
    nums.sort()
    serials = [n for _, n in nums]
    print(fname, serials)
