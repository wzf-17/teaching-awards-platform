from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
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

LEVEL_ALIASES = {
    "特等奖": "特等奖",
    "一等奖": "一等奖",
    "二等奖": "二等奖",
    "特等奨": "特等奖",
    "一等奖": "一等奖",
    "二等奨": "二等奖",
}

PURE_SERIAL_RE = re.compile(r"^\d+$")


@dataclass
class OcrBox:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


@dataclass
class RowChunk:
    serial: str
    org: str
    title: str
    authors: str
    level: str


@dataclass
class Record:
    serial: int
    org: str
    title: str
    authors: str
    level: str

    def to_row(self, output_serial: int) -> list[str]:
        return [
            str(output_serial),
            self.title,
            self.authors,
            self.org,
            "",
            "",
            "",
            self.level,
        ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument("--work-dir", type=Path, default=Path("data/interim/tmp_hunan_undergrad_table"))
    parser.add_argument("--pdftoppm", default=r"D:\texlive\2024\bin\windows\pdftoppm.EXE")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\ufeff", "").replace("\u3000", "")
    text = re.sub(r"\s+", "", text)
    text = (
        text.replace("（", "(")
        .replace("）", ")")
        .replace("：", "：")
        .replace("，", "、")
        .replace(", ", "、")
        .replace(",", "、")
    )
    return text.strip("、")


def normalize_level(text: str) -> str:
    text = normalize_text(text)
    text = text.replace("等奖", "等奖")
    text = text.replace("奨", "奖")
    text = text.replace("二等奖", "二等奖")
    text = text.replace("一等奖", "一等奖")
    text = text.replace("特等奖", "特等奖")
    return LEVEL_ALIASES.get(text, text)


def cluster_positions(values: np.ndarray) -> list[int]:
    if len(values) == 0:
        return []
    out: list[int] = []
    start = int(values[0])
    prev = int(values[0])
    for raw in values[1:]:
        value = int(raw)
        if value <= prev + 1:
            prev = value
            continue
        out.append((start + prev) // 2)
        start = prev = value
    out.append((start + prev) // 2)
    return out


def detect_table_grid(image: np.ndarray) -> tuple[list[int], list[int]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    vert = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, image.shape[0] // 30))),
    )
    hori = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, image.shape[1] // 30), 1)),
    )

    x_candidates = np.where(vert.sum(axis=0) > vert.sum(axis=0).max() * 0.3)[0]
    y_candidates = np.where(hori.sum(axis=1) > hori.sum(axis=1).max() * 0.3)[0]

    x_lines = cluster_positions(x_candidates)
    y_lines = cluster_positions(y_candidates)
    if len(x_lines) < 6 or len(y_lines) < 3:
        raise RuntimeError("failed to detect table grid")
    return x_lines, y_lines


def render_pdf_pages(pdf: Path, out_dir: Path, pdftoppm: str, dpi: int) -> list[Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "page"
    subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), str(pdf), str(prefix)],
        check=True,
    )
    return sorted(out_dir.glob("page-*.png"))


def extract_ocr_boxes(image_path: Path, engine: RapidOCR) -> list[OcrBox]:
    result, _ = engine(str(image_path))
    boxes: list[OcrBox] = []
    for box, text, _score in result or []:
        clean = normalize_text(text)
        if not clean:
            continue
        xs = [int(pt[0]) for pt in box]
        ys = [int(pt[1]) for pt in box]
        boxes.append(OcrBox(min(xs), min(ys), max(xs), max(ys), clean))
    boxes.sort(key=lambda item: (item.y1, item.x1))
    return boxes


def _split_lines(boxes: list[OcrBox]) -> list[str]:
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda item: (item.cy, item.x1))
    fragments: list[list[OcrBox]] = []
    for box in boxes:
        if not fragments or abs(box.cy - fragments[-1][0].cy) > 18:
            fragments.append([box])
        else:
            fragments[-1].append(box)

    lines: list[str] = []
    for line_boxes in fragments:
        line_boxes.sort(key=lambda item: item.x1)
        lines.append("".join(item.text for item in line_boxes))
    return lines


def join_texts(boxes: list[OcrBox], cell_type: str) -> str:
    lines = _split_lines(boxes)
    if not lines:
        return ""
    if cell_type != "authors":
        return "".join(lines)

    merged = lines[0]
    for line in lines[1:]:
        prev_tail = merged.split("、")[-1]
        next_head = line.split("、")[0]
        if merged.endswith("、") or line.startswith("、"):
            merged += line
            continue
        if len(prev_tail) + len(next_head) > 3:
            merged += "、" + line
            continue
        merged += line
    return merged


def merge_author_fragments(left: str, right: str) -> str:
    left = normalize_text(left)
    right = normalize_text(right)
    if not left:
        return right
    if not right:
        return left
    if left.endswith("、") or right.startswith("、"):
        return left + right
    prev_tail = left.split("、")[-1]
    next_head = right.split("、")[0]
    if len(prev_tail) + len(next_head) > 3:
        return left + "、" + right
    return left + right


def parse_page_chunks(image_path: Path, engine: RapidOCR) -> list[RowChunk]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"failed to read image: {image_path}")

    x_lines, y_lines = detect_table_grid(image)
    boxes = extract_ocr_boxes(image_path, engine)
    chunks: list[RowChunk] = []

    for top, bottom in zip(y_lines[1:-1], y_lines[2:]):
        if bottom - top < 18:
            continue
        row_boxes = [box for box in boxes if top < box.cy < bottom]
        if not row_boxes:
            continue

        cells: list[str] = []
        cell_types = ["serial", "org", "title", "authors", "level"]
        for cell_type, (left, right) in zip(cell_types, zip(x_lines[:-1], x_lines[1:])):
            cell_boxes = [box for box in row_boxes if left < box.cx < right]
            cells.append(join_texts(cell_boxes, cell_type))

        chunk = RowChunk(
            serial=normalize_text(cells[0]),
            org=normalize_text(cells[1]),
            title=normalize_text(cells[2]),
            authors=normalize_text(cells[3]),
            level=normalize_level(cells[4]),
        )

        if "序号" in chunk.serial or "推荐单位名称" in chunk.org:
            continue
        if not any([chunk.serial, chunk.org, chunk.title, chunk.authors, chunk.level]):
            continue
        chunks.append(chunk)
    return chunks


def merge_chunks(chunks: list[RowChunk]) -> list[Record]:
    records: list[Record] = []
    current: Record | None = None
    next_serial = 1

    def start_new(chunk: RowChunk) -> Record:
        nonlocal next_serial
        if PURE_SERIAL_RE.fullmatch(chunk.serial):
            serial = int(chunk.serial)
            next_serial = serial + 1
        else:
            serial = next_serial
            next_serial += 1
        return Record(
            serial=serial,
            org=chunk.org,
            title=chunk.title,
            authors=chunk.authors,
            level=chunk.level,
        )

    for chunk in chunks:
        has_new_record_signal = bool(chunk.org or chunk.level or PURE_SERIAL_RE.fullmatch(chunk.serial or ""))

        if has_new_record_signal:
            if current is not None:
                records.append(current)
            current = start_new(chunk)
            continue

        if current is None:
            continue
        current.title += chunk.title
        current.authors = merge_author_fragments(current.authors, chunk.authors)

    if current is not None:
        records.append(current)

    return records


def audit_records(records: list[Record]) -> list[str]:
    issues: list[str] = []
    expected = 1
    for record in records:
        if record.serial != expected:
            issues.append(f"serial mismatch: expected {expected}, got {record.serial}")
            expected = record.serial
        expected += 1
        if not record.org:
            issues.append(f"#{record.serial}: blank org")
        if not record.title:
            issues.append(f"#{record.serial}: blank title")
        if not record.authors:
            issues.append(f"#{record.serial}: blank authors")
        if record.level not in {"特等奖", "一等奖", "二等奖"}:
            issues.append(f"#{record.serial}: bad level {record.level!r}")
        if "推荐单位名称" in record.org or "成果名称" in record.title:
            issues.append(f"#{record.serial}: header leakage")
    return issues


def write_workbook(records: list[Record], output: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "总表"
    ws.append(OUTPUT_HEADERS)
    for idx, record in enumerate(records, start=1):
        ws.append(record.to_row(idx))
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)


def main() -> None:
    args = parse_args()
    images = render_pdf_pages(args.pdf, args.work_dir, args.pdftoppm, args.dpi)
    engine = RapidOCR()
    chunks: list[RowChunk] = []
    for image_path in images:
        chunks.extend(parse_page_chunks(image_path, engine))

    records = merge_chunks(chunks)
    issues = audit_records(records)
    write_workbook(records, args.output)

    print(f"pages={len(images)}")
    print(f"chunks={len(chunks)}")
    print(f"records={len(records)}")
    print(f"issues={len(issues)}")
    for issue in issues[:100]:
        print(issue)

    if not args.keep_images:
        shutil.rmtree(args.work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
