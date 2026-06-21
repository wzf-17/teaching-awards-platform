from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import xml.etree.ElementTree as ET

from openpyxl import Workbook
from rapidocr_onnxruntime import RapidOCR


OUTPUT_HEADERS = [
    "序号",
    "成果名称",
    "完成人",
    "完成单位",
    "第一完成单位层次",
    "第一完成单位学科类型",
    "第一完成单位地理位置",
    "获奖等级",
]

ORG_SUFFIXES = (
    "大学",
    "学院",
    "学校",
    "研究院",
    "研究所",
    "公司",
    "中心",
    "医院",
    "基地",
)
UNDERGRAD_HEADER = "序号 推荐单位名称 成果名称 完成人姓名 拟获奖等级"
SERIAL_LINE_RE = re.compile(r"^(\d+)\s+(.+)$")
PURE_SERIAL_RE = re.compile(r"^\d+$")
UNDERGRAD_LEVEL_RE = re.compile(r"^(特等奖|一等奖|二等奖)$")


@dataclass
class Record:
    serial: int
    org: str
    title: str
    authors: str
    award_level: str

    def to_row(self, output_serial: int) -> list[str]:
        return [
            str(output_serial),
            self.title,
            self.authors,
            self.org,
            "",
            "",
            "",
            self.award_level,
        ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--undergrad-pdf", type=Path, required=True)
    parser.add_argument("--grad-docx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pdftotext", default=r"D:\texlive\2024\bin\windows\pdftotext.exe")
    return parser.parse_args()


def run_pdftotext(pdf_path: Path, txt_path: Path, exe: str) -> None:
    subprocess.run([exe, "-raw", str(pdf_path), str(txt_path)], check=True)


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\ufeff", "").strip())


def is_name_like_line(line: str) -> bool:
    if any(suffix in line for suffix in ORG_SUFFIXES):
        return False
    tokens = [t.strip() for t in re.split(r"[、,，]", line) if t.strip()]
    if len(tokens) < 2:
        return False
    ok = 0
    for token in tokens:
        compact = token.replace(" ", "").replace("·", "").replace("•", "")
        if re.fullmatch(r"[A-Za-z .]+", token):
            ok += 1
        elif 1 <= len(compact) <= 4:
            ok += 1
    return ok / len(tokens) >= 0.8


def split_org_and_title(text: str) -> tuple[str, str]:
    stripped = text.strip()
    best_org = ""
    best_rest = stripped
    for suffix in ORG_SUFFIXES:
        idx = stripped.find(suffix)
        while idx != -1:
            end = idx + len(suffix)
            org = stripped[:end].strip()
            rest = stripped[end:].strip()
            if org and len(org) > len(best_org):
                best_org = org
                best_rest = rest
            idx = stripped.find(suffix, idx + 1)
    return best_org, best_rest


def parse_undergrad_records(raw_text: str) -> list[Record]:
    lines = [normalize_line(line) for line in raw_text.splitlines()]
    records: list[Record] = []
    current_serial = 0
    current_org = ""
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_serial, current_org, body_lines
        if not current_serial:
            body_lines = []
            return
        payload = [line for line in body_lines if line]
        while payload and not UNDERGRAD_LEVEL_RE.fullmatch(payload[-1]):
            payload.pop()
        if not payload:
            body_lines = []
            return
        award_level = payload.pop()
        authors: list[str] = []
        while payload and is_name_like_line(payload[-1]):
            authors.insert(0, payload.pop())
        title = "".join(payload).strip()
        author_text = "".join(authors).strip()
        records.append(Record(current_serial, current_org, title, author_text, award_level))
        body_lines = []

    for line in lines:
        if not line:
            continue
        if line in {"附件"} or UNDERGRAD_HEADER in line or "2025 年湖南省高等教育（本科）教学成果奖拟获奖成果名单" in line:
            continue
        if PURE_SERIAL_RE.fullmatch(line):
            continue
        match = SERIAL_LINE_RE.match(line)
        if match:
            serial = int(match.group(1))
            remainder = match.group(2)
            org, rest = split_org_and_title(remainder)
            if org:
                flush()
                current_serial = serial
                current_org = org
                body_lines = [rest] if rest else []
                continue
        if current_serial:
            body_lines.append(line)

    flush()
    return records


def extract_docx_images(docx_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        if old.is_file():
            old.unlink()
    with ZipFile(docx_path) as zf:
        names = sorted(name for name in zf.namelist() if name.startswith("word/media/image"))
        paths: list[Path] = []
        for name in names:
            target = out_dir / Path(name).name
            target.write_bytes(zf.read(name))
            paths.append(target)
    return paths


def ocr_page_rows(image_path: Path, engine: RapidOCR) -> list[dict[str, str]]:
    result, _ = engine(str(image_path))
    items = []
    for box, text, score in result or []:
        text = normalize_line(text)
        if not text or text in {"附件", "公众号", "新高教"}:
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        items.append(
            {
                "x": min(xs),
                "y": min(ys),
                "text": text,
                "score": float(score),
            }
        )
    items.sort(key=lambda item: (item["y"], item["x"]))

    rows: list[list[dict[str, str]]] = []
    for item in items:
        if not rows or item["y"] - rows[-1][0]["y"] > 12:
            rows.append([item])
        else:
            rows[-1].append(item)

    normalized_rows: list[dict[str, str]] = []
    for row_items in rows:
        row_items.sort(key=lambda item: item["x"])
        row = {"serial": "", "org": "", "title": "", "authors": "", "level": ""}
        for item in row_items:
            x = item["x"]
            text = item["text"]
            if x < 140 and PURE_SERIAL_RE.fullmatch(text):
                row["serial"] = text
            elif x < 270:
                row["org"] += text
            elif x < 605:
                row["title"] += text
            elif x < 925:
                row["authors"] += text
            else:
                row["level"] += text
        if any(row.values()):
            normalized_rows.append(row)
    return normalized_rows


def parse_grad_records(image_paths: list[Path]) -> list[Record]:
    engine = RapidOCR()
    records: list[Record] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current and current.get("serial"):
            records.append(
                Record(
                    serial=int(current["serial"]),
                    org=current["org"].strip(),
                    title=current["title"].strip(),
                    authors=current["authors"].strip(),
                    award_level=current["level"].strip(),
                )
            )
        current = None

    for image_path in image_paths:
        for row in ocr_page_rows(image_path, engine):
            joined = "".join(row.values())
            if not joined:
                continue
            if "推荐单位名称" in joined or "成果名称" in joined or "成果完成人" in joined or "拟获奖等" in joined:
                continue
            if "2025年湖南省高等教育（研究生）教学成果奖拟获奖成果名单" in joined:
                continue
            if row["serial"] and row["org"]:
                flush()
                current = row.copy()
            elif current is not None:
                current["org"] += row["org"]
                current["title"] += row["title"]
                current["authors"] += row["authors"]
                current["level"] += row["level"]
            if current and current["level"] in {"特等奖", "一等奖", "二等奖"}:
                flush()
    flush()
    return records


def audit(records: list[Record], label: str) -> list[str]:
    issues: list[str] = []
    for rec in records:
        if not rec.title or not rec.authors or not rec.org or rec.award_level not in {"特等奖", "一等奖", "二等奖"}:
            issues.append(f"{label}#{rec.serial}: blank or bad level")
    return issues


def write_workbook(records: list[Record], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "总表"
    ws.append(OUTPUT_HEADERS)
    for idx, record in enumerate(records, start=1):
        ws.append(record.to_row(idx))
    wb.save(output_path)


def main() -> None:
    args = parse_args()
    undergrad_txt = Path("tmp_hunan_undergrad_raw.txt")
    grad_docx = Path("tmp_hunan_grad.docx")
    grad_media_dir = Path("tmp_hunan_grad_media")

    run_pdftotext(args.undergrad_pdf, undergrad_txt, args.pdftotext)
    grad_docx.write_bytes(args.grad_docx.read_bytes())

    undergrad_records = parse_undergrad_records(undergrad_txt.read_text(encoding="utf-8"))
    grad_images = extract_docx_images(grad_docx, grad_media_dir)
    grad_records = parse_grad_records(grad_images)

    combined = undergrad_records + grad_records
    issues = audit(undergrad_records, "本科") + audit(grad_records, "研究生")

    write_workbook(combined, args.output)

    print(f"undergrad={len(undergrad_records)}")
    print(f"grad={len(grad_records)}")
    print(f"total={len(combined)}")
    print(f"issues={len(issues)}")
    for issue in issues[:50]:
        print(issue)


if __name__ == "__main__":
    main()
