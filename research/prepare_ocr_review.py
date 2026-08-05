"""Prepare a traceable teacher-review package for suspicious OCR chunks.

The script never changes OCR text or grants teacher approval. It assigns a
technical risk priority, renders the corresponding textbook pages, and writes
flat JSON/CSV data that can be audited or imported into a workbook.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


NOISE_CHARACTERS = set("|\\_`¢£§¬~^#*=<>$¡⁄®")
ALLOWED_PUNCTUATION = set(".,;:!?()[]{}'\"“”‘’/-–—%+@©«»&")
YEAR_RE = re.compile(r"(?<!\d)(?:1[5-9]\d{2}|20\d{2})(?!\d)")
MIXED_NOISE_TOKEN_RE = re.compile(
    r"(?i)(?:[A-Za-zÀ-ỹĐđ0-9]+[|\\_`¢£§¬~^#*=<>$¡⁄®]+"
    r"|[|\\_`¢£§¬~^#*=<>$¡⁄®]+[A-Za-zÀ-ỹĐđ0-9]+)"
)
COMPLEX_LAYOUT_RE = re.compile(
    r"(?i)\b(?:bảng|biểu đồ|lược đồ|sơ đồ|niên biểu|trục thời gian)\b"
)
REPEATED_SEPARATOR_RE = re.compile(r"[—_]{3,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("data/research/history12_kntt/ocr_review_queue.csv"),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("file doc/SGK Lịch sử 12 Kết nối tri thức.pdf"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/cobraq_ocr_review"),
    )
    parser.add_argument(
        "--pdftoppm",
        type=Path,
        default=Path(shutil.which("pdftoppm") or "pdftoppm"),
    )
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-render", action="store_true")
    return parser.parse_args()


def nonstandard_characters(text: str) -> list[str]:
    return [
        char
        for char in text
        if not (
            char.isalnum()
            or char.isspace()
            or char in ALLOWED_PUNCTUATION
        )
    ]


def has_noise_near_year(text: str, radius: int = 24) -> bool:
    for match in YEAR_RE.finditer(text):
        context = text[max(0, match.start() - radius): match.end() + radius]
        if (
            any(char in NOISE_CHARACTERS for char in context)
            or REPEATED_SEPARATOR_RE.search(context)
        ):
            return True
    return False


def classify(row: dict[str, str]) -> dict[str, Any]:
    text = row.get("source_text", "")
    unusual = nonstandard_characters(text)
    density = len(unusual) / max(len(text), 1)
    pipe_count = text.count("|") + text.count("\\")
    mixed_noise = bool(MIXED_NOISE_TOKEN_RE.search(text))
    repeated_separator = bool(REPEATED_SEPARATOR_RE.search(text))
    noise_near_year = has_noise_near_year(text)
    complex_layout = bool(COMPLEX_LAYOUT_RE.search(text)) or pipe_count >= 5

    flags: list[str] = []
    if noise_near_year:
        flags.append("noise_near_historical_year")
    if mixed_noise:
        flags.append("mixed_noise_token")
    if repeated_separator:
        flags.append("repeated_separator_noise")
    if complex_layout:
        flags.append("complex_table_chart_or_map")
    if density >= 0.02:
        flags.append("noise_density_ge_2pct")
    elif density >= 0.0075:
        flags.append("noise_density_ge_0_75pct")
    elif density >= 0.0025:
        flags.append("noise_density_ge_0_25pct")
    if not flags:
        flags.append("isolated_layout_symbol")

    if noise_near_year or density >= 0.02:
        priority = "CRITICAL"
        action = "Đối chiếu từng mốc thời gian/số liệu với ảnh trang; sửa toàn bộ đoạn nếu cần."
    elif complex_layout or density >= 0.0075:
        priority = "HIGH"
        action = "Kiểm tra thứ tự đọc bảng/biểu đồ/bản đồ và mọi số liệu trước khi phê duyệt."
    elif mixed_noise or repeated_separator or density >= 0.0025:
        priority = "MEDIUM"
        action = "Đọc đối chiếu đoạn OCR; sửa từ hoặc ký hiệu bị nhận dạng sai."
    else:
        priority = "LOW"
        action = "Xác nhận ký hiệu chỉ là nhiễu bố cục và nội dung dữ kiện vẫn đúng."

    score = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }[priority]
    return {
        "risk_priority": priority,
        "risk_score": score,
        "risk_flags": ";".join(flags),
        "noise_character_count": len(unusual),
        "noise_density": round(density, 6),
        "recommended_action": action,
    }


def render_page(
    page: int,
    *,
    pdf: Path,
    pages_dir: Path,
    pdftoppm: Path,
    dpi: int,
) -> Path:
    output = pages_dir / f"page_{page:03d}.jpg"
    if output.exists() and output.stat().st_size > 0:
        return output
    base = output.with_suffix("")
    process = subprocess.run(
        [
            str(pdftoppm), "-f", str(page), "-l", str(page), "-singlefile",
            "-jpeg", "-r", str(dpi), str(pdf), str(base),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode:
        raise RuntimeError(
            f"Could not render PDF page {page}: "
            f"{(process.stderr or process.stdout).strip()}"
        )
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"Rendered page is missing or empty: {output}")
    return output


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    for required in (args.queue, args.pdf, args.pdftoppm):
        if not required.exists():
            raise FileNotFoundError(required)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = args.output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    with args.queue.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))

    pages = sorted({int(row["pdf_page"]) for row in source_rows})
    if not args.skip_render:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(
                    render_page,
                    page,
                    pdf=args.pdf,
                    pages_dir=pages_dir,
                    pdftoppm=args.pdftoppm,
                    dpi=args.dpi,
                ): page
                for page in pages
            }
            for future in as_completed(futures):
                future.result()

    rows: list[dict[str, Any]] = []
    for row in source_rows:
        page = int(row["pdf_page"])
        audit = classify(row)
        image_path = (pages_dir / f"page_{page:03d}.jpg").resolve()
        rows.append(
            {
                "chunk_id": row["chunk_id"],
                "risk_priority": audit["risk_priority"],
                "risk_score": audit["risk_score"],
                "risk_flags": audit["risk_flags"],
                "topic_id": row["topic_id"],
                "lesson_id": row["lesson_id"],
                "lesson_title": row["lesson_title"],
                "pdf_page": page,
                "book_page": int(row["book_page"]),
                "ocr_confidence": float(row["ocr_confidence"]),
                "noise_character_count": audit["noise_character_count"],
                "noise_density": audit["noise_density"],
                "original_review_reasons": row["review_reasons"],
                "recommended_action": audit["recommended_action"],
                "page_image_path": str(image_path),
                "source_text": row["source_text"],
                "review_status": row.get("review_status") or "pending",
                "corrected_text": row.get("corrected_text", ""),
                "reviewer_id": row.get("reviewer_id", ""),
                "review_date": "",
                "review_comment": row.get("review_comment", ""),
            }
        )

    rows.sort(key=lambda item: (-item["risk_score"], item["pdf_page"], item["chunk_id"]))
    write_csv(rows, args.output_dir / "ocr_review_rows.csv")
    (args.output_dir / "ocr_review_rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    summary = {
        "total_chunks": len(rows),
        "total_pages": len(pages),
        "priorities": {
            priority: sum(row["risk_priority"] == priority for row in rows)
            for priority in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        },
        "source_queue": str(args.queue.resolve()),
        "source_pdf": str(args.pdf.resolve()),
        "dpi": args.dpi,
        "policy": "technical_pretriage_only_no_teacher_approval",
    }
    (args.output_dir / "ocr_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
