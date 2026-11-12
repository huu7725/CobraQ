"""Recover drafts and textbook from the surviving teacher review ZIP, without approvals."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile

import pymupdf

from backend.app.research.schemas import SourceChunk, digest
from backend.app.research.store import write_jsonl

SOURCE_NAME = "Lịch sử 12 - Kết nối tri thức với cuộc sống, bản mẫu 10/2023"


def topic(lesson):
    return next(i for i, end in enumerate((3, 5, 9, 11, 14, 17), 1) if lesson <= end)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def body(page):
    return page.get_text(sort=True).split("CobraQ | Phiếu nhận xét độc lập")[0]


def recover(bundle: Path, output: Path):
    if (output / "corpus/chunks.jsonl").exists():
        raise ValueError("Recovery already exists; choose a new output directory to preserve revisions")
    chunks, questions, queries, lessons, inputs = {}, [], [], {}, []
    with zipfile.ZipFile(bundle) as archive:
        textbook_bytes = archive.read("03_SGK_day_du_de_doi_chieu.pdf")
        book_hash = hashlib.sha256(textbook_bytes).hexdigest()
        sources = output / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        (sources / "history12_kntt_2023_sample.pdf").write_bytes(textbook_bytes)

        def add_chunk(text, page, lesson_id, title, origin, origin_page):
            text = clean(text)
            key = "recovered-" + digest([text, page, lesson_id])[:20]
            chunks[key] = SourceChunk(
                id=key, text=text, source=SOURCE_NAME, source_sha256=book_hash,
                book_page=page, pdf_page=page + 2, lesson_id=lesson_id,
                lesson_title=title, topic_id=topic(lesson_id), provenance="review_pdf_extract",
                years=sorted(set(re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", text))),
            ).model_dump()
            return key

        for name in archive.namelist():
            if not name.startswith(("00_", "01_", "02_")):
                continue
            raw = archive.read(name)
            inputs.append({"member": name, "sha256": hashlib.sha256(raw).hexdigest()})
            pdf = pymupdf.open(stream=raw, filetype="pdf")
            for index, page in enumerate(pdf):
                text = body(page)
                match = re.match(r"\s*([CN]\d{2})\s*\|\s*(Trắc nghiệm|Tự luận|Xác nhận nguồn)", text)
                if not match:
                    continue
                lesson = re.search(r"Bài\s+(\d+):\s*(.+?)\n\s*\n", text, re.S)
                if not lesson:
                    raise ValueError(f"Missing lesson in {name}:{index+1}")
                lesson_id, title = int(lesson[1]), clean(lesson[2])
                lessons[lesson_id] = title
                content = text[lesson.end():].strip()
                provenance = {"archive_member": name, "pdf_page": index + 1,
                              "sha256": hashlib.sha256(raw).hexdigest()}
                if match[1].startswith("C"):
                    draft, remainder = content.split("Đáp án đề xuất:", 1)
                    answer, remainder = remainder.split("Lời giải đề xuất:", 1)
                    explanation, remainder = remainder.split("Trích dẫn cung cấp - SGK trang", 1)
                    cite = re.match(r"\s*(\d+)\s*\(xem trang gốc cuối tập\)\s*(.*?)\s*Nhận xét của thầy/cô", remainder, re.S)
                    if not cite:
                        raise ValueError(f"Missing source in {match[1]}")
                    key = add_chunk(cite[2], int(cite[1]), lesson_id, title, name, index + 1)
                    choices = {}
                    if match[2] == "Trắc nghiệm":
                        parts = re.split(r"(?:^|\n)\s*([ABCD])\.\s*", draft)
                        stem = parts[0]
                        choices = {parts[i]: clean(parts[i+1]) for i in range(1, len(parts), 2)}
                    else:
                        stem = draft
                    question = {"question_type": "multiple_choice" if choices else "short_answer",
                                "stem": clean(stem), "choices": choices,
                                "correct_answer": clean(answer), "explanation": clean(explanation)}
                    questions.append({"id": match[1], "lesson_id": lesson_id, "lesson_title": title,
                                      "question": question, "chunk_ids": [key], "book_page": int(cite[1]),
                                      "quote": clean(cite[2]), "review_status": "review_required",
                                      "reviewer_id": "", "reviewed_at": "", "provenance": provenance,
                                      "original_content_hash": digest(question),
                                      "flags": ["answer_rubric_placeholder"] if "Giáo viên cần hoàn" in explanation else []})
                else:
                    prompt, candidates = content.split("Các trích đoạn dưới đây", 1)
                    found = re.findall(r"Đoạn ([ABC]) - SGK trang (\d+)\s*(?:\(trích một phần\))?\s*(.*?)(?=\n\s*Đoạn [ABC] -|\n\s*Xin ghi quyết định|$)", candidates, re.S)
                    candidate_ids = {letter: add_chunk(quote, int(pg), lesson_id, title, name, index + 1)
                                     for letter, pg, quote in found}
                    if set(candidate_ids) != set("ABC"):
                        raise ValueError(f"Missing retrieval candidates for {match[1]}")
                    queries.append({"id": match[1], "query": clean(prompt), "lesson_id": lesson_id,
                                    "candidate_chunk_ids": json.dumps(candidate_ids),
                                    "relevant_chunk_ids": "[]", "review_status": "review_required",
                                    "reviewer_id": "", "reviewed_at": ""})
    if len(questions) != 60 or len(queries) != 51 or len(lessons) != 17:
        raise ValueError(f"Incomplete recovery: {len(questions)} questions/{len(queries)} queries/{len(lessons)} lessons")
    write_jsonl(output / "corpus/chunks.jsonl", list(chunks.values()))
    write_jsonl(output / "datasets/independent_review_60.jsonl", questions)
    gold = output / "datasets/retrieval_gold.csv"
    with gold.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(queries[0]))
        writer.writeheader()
        writer.writerows(queries)
    (output / "corpus/lessons.json").write_text(json.dumps([
        {"id": key, "title": title, "topic_id": topic(key)} for key, title in sorted(lessons.items())
    ], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "textbook_sha256": book_hash, "textbook_pdf_pages": 116,
                "book_page_offset": 2, "chunks_recovered": len(chunks), "questions": len(questions),
                "question_types": dict(Counter(q["question"]["question_type"] for q in questions)),
                "retrieval_queries": len(queries), "approved": 0,
                "note": "Recovered review drafts, NOT the lost 600 approved training examples or held-out set.",
                "inputs": inputs}
    (output / "RECOVERY_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, default=Path("research"))
    args = parser.parse_args()
    recover(args.bundle, args.output)
