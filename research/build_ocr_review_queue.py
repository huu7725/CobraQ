"""Export OCR chunks requiring human review to a teacher-friendly CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chunks",
        type=Path,
        default=ROOT / "data" / "research" / "history12_kntt" / "chunks.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "research" / "history12_kntt" / "ocr_review_queue.csv",
    )
    args = parser.parse_args()
    records = []
    with args.chunks.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                item = json.loads(line)
                if item.get("review_required"):
                    records.append(item)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "chunk_id", "topic_id", "lesson_id", "lesson_title", "pdf_page", "book_page",
        "ocr_confidence", "review_reasons", "source_text", "review_status",
        "corrected_text", "reviewer_id", "review_comment",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in records:
            writer.writerow(
                {
                    "chunk_id": item["chunk_id"],
                    "topic_id": item["topic_id"],
                    "lesson_id": item["lesson_id"],
                    "lesson_title": item["lesson_title"],
                    "pdf_page": item["pdf_page"],
                    "book_page": item["book_page"],
                    "ocr_confidence": item.get("ocr_confidence"),
                    "review_reasons": ";".join(item.get("review_reasons") or []),
                    "source_text": item["text"],
                    "review_status": "pending",
                    "corrected_text": "",
                    "reviewer_id": "",
                    "review_comment": "",
                }
            )
    print(f"review_chunks={len(records)} path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
