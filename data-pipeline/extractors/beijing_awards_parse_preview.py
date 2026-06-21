from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


IMG_DIR = Path(__file__).resolve().parent / "beijing_awards_work" / "images"
engine = RapidOCR()


def normalize_award(text: str) -> str | None:
    t = text.replace(" ", "")
    if "特等奖" in t:
        return "特等奖"
    if "一等奖" in t:
        return "一等奖"
    if "二等奖" in t or "二常奖" in t or "二等类" in t or "二等奖" in t:
        return "二等奖"
    return None


def parse_page(path: Path):
    result, _ = engine(str(path))
    items = []
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append(
            {
                "text": text.strip(),
                "x1": min(xs),
                "x2": max(xs),
                "y1": min(ys),
                "y2": max(ys),
                "ym": (min(ys) + max(ys)) / 2,
            }
        )

    items = [x for x in items if x["text"]]
    award_items = []
    for it in items:
        award = normalize_award(it["text"])
        if award and it["x1"] >= 880:
            award_items.append({**it, "award": award})
    award_items.sort(key=lambda x: x["ym"])

    rows = []
    for i, a in enumerate(award_items):
        prev_y = award_items[i - 1]["ym"] if i > 0 else 150
        next_y = award_items[i + 1]["ym"] if i + 1 < len(award_items) else 10000
        top = (prev_y + a["ym"]) / 2 if i > 0 else 150
        bottom = (a["ym"] + next_y) / 2 if i + 1 < len(award_items) else a["ym"] + 140

        group = [it for it in items if it["ym"] >= top and it["ym"] < bottom]
        serials = [it["text"] for it in group if it["x2"] <= 160 and re.fullmatch(r"\d{1,3}", it["text"])]

        def collect(xl, xr):
            arr = [it for it in group if it["x1"] >= xl and it["x2"] <= xr]
            arr.sort(key=lambda x: (round(x["ym"] / 8), x["x1"]))
            return "".join([it["text"] for it in arr])

        rows.append(
            {
                "serials": serials,
                "name": collect(150, 350),
                "persons": collect(350, 720),
                "unit": collect(720, 900),
                "award": a["award"],
            }
        )
    return rows


for fname in ["019.png", "020.png", "021.png", "067.png", "068.png", "069.png"]:
    path = IMG_DIR / fname
    rows = parse_page(path)
    print(f"\n## {fname} rows={len(rows)}")
    for r in rows[:10]:
        print(r)
