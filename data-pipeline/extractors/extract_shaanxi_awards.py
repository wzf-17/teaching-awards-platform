from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook


RAW_HEADERS = ["序号", "成果名称", "完成人", "完成单位", "获奖等级"]
EXTRA_HEADERS = ["第一完成单位层次", "第一完成单位学科类型", "第一完成单位地理位置"]
OUTPUT_HEADERS = ["序号", "成果名称", "完成人", "完成单位", *EXTRA_HEADERS, "获奖等级"]

ORG_SUFFIXES = [
    "大学",
    "学院",
    "出版社",
    "公司",
    "研究所",
    "研究院",
    "党校",
    "中心",
    "实验室",
    "医院",
    "学校",
    "小学",
    "中学",
]
ORG_HINTS = ["大学", "学院", "出版社", "公司", "研究所", "研究院", "党校", "中心", "实验室", "医院", "学校", "集团", "小学", "中学"]
SERIAL_RE = re.compile(r"^(\d+)\s*(.*)$")


@dataclass
class Record:
    serial: str
    award_level: str
    school_parts: list[str]
    project_parts: list[str]
    author_parts: list[str]

    def to_row(self) -> list[str]:
        school = join_parts(self.school_parts)
        project = join_parts(self.project_parts)
        authors = join_parts(self.author_parts)
        return [
            self.serial,
            project,
            authors,
            school,
            "",
            "",
            "",
            "",
            self.award_level,
        ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--undergrad-pdf", type=Path, required=True)
    parser.add_argument("--grad-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pdftotext", default=r"D:\texlive\2024\bin\windows\pdftotext.exe")
    return parser.parse_args()


def run_pdftotext(pdf_path: Path, txt_path: Path, exe: str) -> None:
    subprocess.run([exe, "-raw", str(pdf_path), str(txt_path)], check=True)


def is_header_or_noise(line: str) -> bool:
    if not line:
        return True
    if "序号 学校名称 申报成果名称 成果主要完成人姓名" in line:
        return True
    if line.startswith("附件"):
        return True
    if line.startswith("—") and line.endswith("—"):
        return True
    if "教学成果奖拟获奖" in line:
        return True
    return False


def detect_award_level(line: str) -> str | None:
    if "特等奖" in line:
        return "特等奖"
    if "一等奖" in line:
        return "一等奖"
    if "二等奖" in line:
        return "二等奖"
    return None


def join_parts(parts: list[str]) -> str:
    return "".join(part.strip() for part in parts if part and part.strip())


def looks_like_author_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    parts = [part.strip() for part in text.split("、") if part.strip()]
    if text.startswith("、") and len(parts) >= 1 and all(len(part) <= 4 for part in parts):
        return True
    if len(parts) >= 2 and all(len(part) <= 4 for part in parts):
        return True
    return False


def looks_like_school_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if any(hint in text for hint in ORG_HINTS):
        return True
    if any(hint in text for hint in ORG_HINTS):
        return True
    return False


def split_project_and_authors(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return "", ""
    if looks_like_author_line(stripped):
        return "", stripped
    for match in reversed(list(re.finditer(r"\s+", stripped))):
        tail = stripped[match.end():].strip()
        if looks_like_author_line(tail):
            return stripped[:match.start()].strip(), tail
    return stripped, ""


def split_school_and_project(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return "", ""
    best_school = ""
    best_rest = ""
    for suffix in ORG_SUFFIXES:
        idx = stripped.find(suffix)
        while idx != -1:
            end = idx + len(suffix)
            school = stripped[:end].strip(" 、")
            rest = stripped[end:].strip()
            if school and (not best_school or len(school) > len(best_school)):
                best_school = school
                best_rest = rest
            idx = stripped.find(suffix, idx + 1)
    if best_school:
        return best_school, best_rest
    return "", stripped


def parse_raw_text(raw_text: str) -> list[Record]:
    records: list[Record] = []
    current_level = ""
    current: Record | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        level = detect_award_level(line)
        if level:
            current_level = level
            continue
        if is_header_or_noise(line):
            continue

        match = SERIAL_RE.match(line)
        if match and line.split()[0].isdigit():
            if current:
                records.append(current)
            serial = match.group(1)
            remainder = match.group(2).strip()
            school_parts: list[str] = []
            project_parts: list[str] = []
            if remainder:
                school, project = split_school_and_project(remainder)
                if school:
                    school_parts.append(school)
                if project:
                    project, authors = split_project_and_authors(project)
                    if project:
                        project_parts.append(project)
                    if authors:
                        current_authors = [authors]
                    else:
                        current_authors = []
                else:
                    current_authors = []
                if not school and not project:
                    project_parts.append(remainder)
                    current_authors = []
            else:
                current_authors = []
            current = Record(serial=serial, award_level=current_level, school_parts=school_parts, project_parts=project_parts, author_parts=current_authors)
            continue

        if current is None:
            continue

        if current.author_parts:
            current.author_parts.append(line)
            continue

        if looks_like_author_line(line):
            current.author_parts.append(line)
            continue

        if not current.project_parts and not current.school_parts and not looks_like_author_line(line):
            current.school_parts.append(line)
            continue

        if not current.project_parts and looks_like_school_line(line):
            current.school_parts.append(line)
            continue

        if current.project_parts or not looks_like_school_line(line):
            project, authors = split_project_and_authors(line)
            if project:
                current.project_parts.append(project)
            if authors:
                current.author_parts.append(authors)
            elif not project:
                current.project_parts.append(line)
            continue

        current.school_parts.append(line)

    if current:
        records.append(current)
    return records


def write_workbook(rows: list[list[str]], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "总表"
    ws.append(OUTPUT_HEADERS)
    for row in rows:
        ws.append(row)
    wb.save(output_path)


def main() -> None:
    args = parse_args()
    tmp_undergrad = Path("tmp_shaanxi_undergrad_raw.txt")
    tmp_grad = Path("tmp_shaanxi_grad_raw.txt")

    run_pdftotext(args.undergrad_pdf, tmp_undergrad, args.pdftotext)
    run_pdftotext(args.grad_pdf, tmp_grad, args.pdftotext)

    undergrad_records = parse_raw_text(tmp_undergrad.read_text(encoding="utf-8"))
    grad_records = parse_raw_text(tmp_grad.read_text(encoding="utf-8"))

    rows = [record.to_row() for record in undergrad_records + grad_records]
    write_workbook(rows, args.output)

    print(f"UNDERGRAD_COUNT: {len(undergrad_records)}")
    print(f"GRAD_COUNT: {len(grad_records)}")
    print(f"TOTAL_COUNT: {len(rows)}")
    print(f"OUTPUT: {args.output}")


if __name__ == "__main__":
    main()
