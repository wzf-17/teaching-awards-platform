from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook


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

ORG_KEYWORDS = (
    "大学",
    "学院",
    "学校",
    "研究院",
    "研究所",
    "公司",
    "医院",
    "中心",
    "基地",
    "实验室",
    "委员会",
    "幼儿园",
    "中学",
    "小学",
    "学会",
    "集团",
    "报社",
    "出版社",
    "博物馆",
    "图书馆",
    "法院",
    "检察院",
)

ORG_START_HINTS = (
    "华中科技大学",
    "武汉大学",
    "中国地质大学（武汉）",
    "华中农业大学",
    "华中师范大学",
    "武汉理工大学",
    "武汉科技大学",
    "湖北大学",
    "中南财经政法大学",
    "中南民族大学",
    "武汉工程大学",
    "武汉纺织大学",
    "武汉轻工大学",
    "武汉体育学院",
    "武汉音乐学院",
    "湖北工业大学",
    "湖北经济学院",
    "湖北中医药大学",
    "湖北医药学院",
    "湖北工程学院",
    "湖北师范大学",
    "湖北理工学院",
    "湖北科技学院",
    "湖北美术学院",
    "湖北民族大学",
    "湖北文理学院",
    "湖北第二师范学院",
    "湖北汽车工业学院",
    "湖北汽车工业学院科技学院",
    "湖北警官学院",
    "湖北开放大学",
    "湖北教育数字化研究院",
    "长江大学",
    "长江大学文理学院",
    "三峡大学",
    "江汉大学",
    "海军工程大学",
    "空军预警学院",
    "信息支援部队工程大学",
    "荆楚理工学院",
    "荆州学院",
    "黄冈师范学院",
    "汉江师范学院",
    "汉口学院",
    "文华学院",
    "武昌首义学院",
    "武昌工学院",
    "武昌理工学院",
    "武汉东湖学院",
    "武汉传媒学院",
    "武汉华夏理工学院",
    "武汉学院",
    "武汉工商学院",
    "武汉工程科技学院",
    "武汉文理学院",
    "武汉晴川学院",
    "武汉城市学院",
    "武汉设计工程学院",
    "武汉商学院",
    "武汉生物工程学院",
    "湖北恩施学院",
    "湖北商贸学院",
)

NOISE_PATTERNS = (
    "2025 年湖北省高等教育",
    "拟授奖成果名单",
    "拟授奖成果排名不分先后",
    "序号 成果名称 成果主要完成人姓名 成果主要完成单位",
)

SERIAL_RE = re.compile(r"^(\d+)(?:\s+(.*))?$")
SPACE_RE = re.compile(r"\s+")


@dataclass
class ParsedRecord:
    section_serial: int
    award_level: str
    title: str
    authors: str
    orgs: str
    source_lines: list[str]

    def to_row(self, output_serial: int) -> list[str]:
        return [
            str(output_serial),
            self.title,
            self.authors,
            self.orgs,
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


def normalize_line(line: str) -> str:
    return SPACE_RE.sub(" ", line.replace("\ufeff", "").strip())


def detect_award_level(line: str) -> str | None:
    if "特等奖" in line:
        return "特等奖"
    if "一等奖" in line:
        return "一等奖"
    if "二等奖" in line:
        return "二等奖"
    return None


def is_noise_line(line: str) -> bool:
    if not line:
        return True
    if re.fullmatch(r"—\s*\d+\s*—", line):
        return True
    if any(pattern in line for pattern in NOISE_PATTERNS):
        return True
    return False


def is_probable_page_number(line: str, next_line: str | None) -> bool:
    if not re.fullmatch(r"\d+", line):
        return False
    if next_line and ("湖北省高等教育" in next_line or "拟授奖成果名单" in next_line):
        return True
    if next_line and detect_award_level(next_line):
        return True
    if next_line and re.fullmatch(r"\d+(?:\s+.*)?", next_line):
        return True
    return False


def split_name_tokens(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[、,，]", text) if part.strip()]


def is_name_token(token: str) -> bool:
    text = token.strip()
    if not text:
        return False
    if re.fullmatch(r"[A-Za-z .]+", text):
        return True
    compact = text.replace(" ", "").replace("·", "").replace("•", "").replace(".", "")
    if "·" in text or "•" in text:
        return 2 <= len(compact) <= 8
    return 1 <= len(compact) <= 4


def looks_like_author_line(line: str, min_tokens: int = 2) -> bool:
    if any(keyword in line for keyword in ORG_KEYWORDS):
        return False
    tokens = split_name_tokens(line)
    if len(tokens) < min_tokens:
        return False
    return sum(1 for token in tokens if is_name_token(token)) / len(tokens) >= 0.8


def looks_like_org_text(text: str) -> bool:
    return any(keyword in text for keyword in ORG_KEYWORDS)


def split_author_org_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    for match in re.finditer(r"\s+", stripped):
        head = stripped[: match.start()].strip()
        tail = stripped[match.end() :].strip()
        if head and tail and looks_like_author_line(head, min_tokens=1) and looks_like_org_text(tail):
            return head, tail
    for hint in ORG_START_HINTS:
        idx = stripped.find(hint)
        if idx > 0:
            head = stripped[:idx].strip()
            tail = stripped[idx:].strip()
            if head and tail and looks_like_author_line(head, min_tokens=1) and looks_like_org_text(tail):
                return head, tail
    return None


def is_short_author_continuation(line: str, next_line: str | None) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped.replace(" ", "")) > 2:
        return False
    if re.fullmatch(r"[A-Za-z. ]+", stripped):
        return True
    if next_line and looks_like_org_text(next_line):
        return True
    if next_line:
        for hint in ORG_START_HINTS:
            if next_line.startswith(hint):
                return True
    return False


def collect_record_blocks(raw_text: str) -> list[tuple[str, int, list[str]]]:
    lines = [normalize_line(line) for line in raw_text.splitlines()]
    blocks: list[tuple[str, int, list[str]]] = []
    current_level = ""
    current_serial = 0
    current_lines: list[str] | None = None

    for idx, line in enumerate(lines):
        if not line:
            continue
        next_line = None
        for probe in lines[idx + 1 :]:
            if probe:
                next_line = probe
                break

        level = detect_award_level(line)
        if level:
            if current_lines is not None:
                blocks.append((current_level, current_serial, current_lines))
                current_lines = None
            current_level = level
            continue

        if is_noise_line(line) or is_probable_page_number(line, next_line):
            continue

        match = SERIAL_RE.match(line)
        if match:
            if current_lines is not None:
                blocks.append((current_level, current_serial, current_lines))
            current_serial = int(match.group(1))
            remainder = (match.group(2) or "").strip()
            current_lines = [remainder] if remainder else []
            continue

        if current_lines is None:
            continue
        current_lines.append(line)

    if current_lines is not None:
        blocks.append((current_level, current_serial, current_lines))

    return blocks


def split_record_fields(record_lines: list[str]) -> tuple[str, str, str]:
    title_lines: list[str] = []
    author_lines: list[str] = []
    org_lines: list[str] = []
    phase = "title"

    for idx, line in enumerate(record_lines):
        next_line = record_lines[idx + 1] if idx + 1 < len(record_lines) else None
        if phase == "title":
            inline_split = split_author_org_line(line)
            if inline_split:
                phase = "org"
                author, org = inline_split
                author_lines.append(author)
                org_lines.append(org)
            elif looks_like_author_line(line):
                phase = "author"
                author_lines.append(line)
            else:
                title_lines.append(line)
            continue

        if phase == "author":
            inline_split = split_author_org_line(line)
            if inline_split:
                phase = "org"
                author, org = inline_split
                author_lines.append(author)
                org_lines.append(org)
            elif is_short_author_continuation(line, next_line):
                author_lines.append(line)
            elif looks_like_author_line(line):
                author_lines.append(line)
            else:
                phase = "org"
                org_lines.append(line)
            continue

        org_lines.append(line)

    title = "".join(title_lines).strip()
    authors = "".join(author_lines).strip()
    orgs = "".join(org_lines).strip()
    return title, authors, orgs


def parse_records(raw_text: str) -> list[ParsedRecord]:
    records: list[ParsedRecord] = []
    for award_level, section_serial, record_lines in collect_record_blocks(raw_text):
        title, authors, orgs = split_record_fields(record_lines)
        records.append(
            ParsedRecord(
                section_serial=section_serial,
                award_level=award_level,
                title=title,
                authors=authors,
                orgs=orgs,
                source_lines=record_lines,
            )
        )
    return records


def audit_records(records: list[ParsedRecord], label: str) -> list[str]:
    issues: list[str] = []
    for rec in records:
        prefix = f"{label} {rec.award_level}#{rec.section_serial}"
        if not rec.title or not rec.authors or not rec.orgs:
            issues.append(f"{prefix}: blank field")
        if looks_like_author_line(rec.title):
            issues.append(f"{prefix}: title looks like authors")
        if looks_like_org_text(rec.authors):
            issues.append(f"{prefix}: authors look like orgs")
        if not looks_like_org_text(rec.orgs):
            issues.append(f"{prefix}: orgs missing org keywords")
    return issues


def write_workbook(records: list[ParsedRecord], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "总表"
    ws.append(OUTPUT_HEADERS)
    for idx, record in enumerate(records, start=1):
        ws.append(record.to_row(idx))
    wb.save(output_path)


def main() -> None:
    args = parse_args()
    tmp_undergrad = Path("tmp_hubei_undergrad_raw.txt")
    tmp_grad = Path("tmp_hubei_grad_raw.txt")

    run_pdftotext(args.undergrad_pdf, tmp_undergrad, args.pdftotext)
    run_pdftotext(args.grad_pdf, tmp_grad, args.pdftotext)

    undergrad_records = parse_records(tmp_undergrad.read_text(encoding="utf-8"))
    grad_records = parse_records(tmp_grad.read_text(encoding="utf-8"))

    issues = audit_records(undergrad_records, "本科") + audit_records(grad_records, "研究生")

    combined = undergrad_records + grad_records
    write_workbook(combined, args.output)

    print(f"undergrad={len(undergrad_records)}")
    print(f"grad={len(grad_records)}")
    print(f"total={len(combined)}")
    print("undergrad_levels=" + ",".join(record.award_level for record in undergrad_records[:3]))
    print("grad_levels=" + ",".join(record.award_level for record in grad_records[:3]))
    print(f"issues={len(issues)}")
    for issue in issues[:50]:
        print(issue)


if __name__ == "__main__":
    main()
