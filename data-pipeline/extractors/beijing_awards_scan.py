from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from rapidocr_onnxruntime import RapidOCR


ARTICLE_URL = "https://www.sohu.com/a/986557840_121124333"
BASE_DIR = Path(__file__).resolve().parent / "beijing_awards_work"
IMG_DIR = BASE_DIR / "images"
META_JSON = BASE_DIR / "meta.json"
OCR_TXT = BASE_DIR / "ocr_preview.txt"


def fetch_urls() -> list[str]:
    s = requests.Session()
    s.trust_env = False
    html = s.get(ARTICLE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    urls: list[str] = []
    for m in re.findall(r"https://q\d+\.itc\.cn/[^\"'\s>]+", html):
        m = m.replace("\\/", "/")
        if m not in urls:
            urls.append(m)
    return urls


def download_images(urls: list[str]) -> list[Path]:
    s = requests.Session()
    s.trust_env = False
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, url in enumerate(urls, 1):
        ext = ".png" if ".png" in url.lower() else ".jpg"
        path = IMG_DIR / f"{i:03d}{ext}"
        if not path.exists():
            r = s.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0", "Referer": ARTICLE_URL})
            r.raise_for_status()
            path.write_bytes(r.content)
        paths.append(path)
    return paths


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    urls = fetch_urls()
    paths = download_images(urls)

    META_JSON.write_text(
        json.dumps([{"index": i + 1, "url": urls[i], "file": str(paths[i])} for i in range(len(urls))], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    engine = RapidOCR()
    previews: list[str] = []
    for i, path in enumerate(paths, 1):
        try:
            result, _ = engine(str(path))
            texts = [item[1] for item in result] if result else []
            preview = " | ".join(texts[:25])
        except Exception as e:
            preview = f"[OCR_ERROR] {e}"
        previews.append(f"{i:03d}\t{path.name}\t{preview}")

    OCR_TXT.write_text("\n".join(previews), encoding="utf-8")
    print(str(OCR_TXT))


if __name__ == "__main__":
    main()
