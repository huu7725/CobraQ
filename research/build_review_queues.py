"""Build independent teacher-review and retrieval-gold queues for History 12.

The queues never alter approved content and never select from the held-out test
split. Teacher fields remain blank until an independent reviewer completes them.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "research" / "aqg_v2" / "approved"
DEFAULT_REVIEW_DIR = ROOT / "outputs" / "cobraq_teacher_review_60"
DEFAULT_GOLD = ROOT / "research" / "datasets" / "retrieval_gold.csv"
PLACEHOLDER = "Giáo viên cần hoàn thiện đáp án và thang điểm trước khi phê duyệt."

REVIEW_HEADERS = [
    "review_id", "source_split", "source_record_id", "lesson_id", "lesson_number",
    "lesson_title", "topic_id", "question_type", "difficulty", "bloom_level",
    "stem", "choice_A", "choice_B", "choice_C", "choice_D", "correct_answer",
    "explanation", "source_chunk_id", "source_page", "evidence_quote", "context",
    "issue_flags", "review_priority", "reviewer_id", "review_date",
    "factual_accuracy", "source_support", "unique_correct_answer", "clarity",
    "curriculum_alignment", "cognitive_alignment", "distractor_quality",
    "pedagogical_language", "difficulty_fit", "factual_error_found",
    "teacher_decision", "editing_minutes", "teacher_comment", "revision_version",
]

GOLD_HEADERS = [
    "query_id", "query", "lesson_id", "lesson_number", "lesson_title", "topic_id",
    "question_type", "difficulty", "source_page", "candidate_chunk_id",
    "source_quote", "source_context", "relevant_chunk_ids", "reviewer_id",
    "review_status", "comment",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--gold-output", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--review-count", type=int, default=60)
    parser.add_argument("--gold-per-lesson", type=int, default=3)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def fold(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(re.findall(r"[0-9a-z]+", text.replace("đ", "d")))


def record_question(record: dict) -> dict:
    return (record.get("response") or {}).get("questions", [])[0]


def record_lesson_number(record: dict) -> str:
    return str((record.get("provenance") or {}).get("lesson_number") or record.get("lesson_number") or "")


def record_difficulty(record: dict) -> int:
    return int((record.get("provenance") or {}).get("difficulty") or record.get("difficulty") or 0)


def issue_flags(record: dict, stem_counts: Counter[str]) -> list[str]:
    question = record_question(record)
    flags = []
    if question.get("question_type") == "short_essay" and PLACEHOLDER in question.get("explanation", ""):
        flags.append("essay_answer_placeholder")
    if question.get("question_type") == "multiple_choice" and stem_counts[fold(question.get("stem", ""))] > 1:
        flags.append("repeated_stem_pattern")
    if question.get("question_type") == "multiple_choice":
        choices = [choice.get("text", "") for choice in question.get("choices", [])]
        if len(choices) != len({fold(choice) for choice in choices}):
            flags.append("duplicate_choice_text")
    return flags


def pool_records(data_dir: Path) -> list[dict]:
    records = []
    for split in ("train", "validation"):
        records.extend(load_jsonl(data_dir / f"{split}.jsonl"))
    if any(record.get("split") == "test" for record in records):
        raise ValueError("Review pool must not contain held-out test records")
    return records


def choose_review_records(records: list[dict], count: int) -> list[dict]:
    if count != 60:
        raise ValueError("This preregistered queue is defined for exactly 60 records")
    stem_counts = Counter(fold(record_question(record).get("stem", "")) for record in records)
    by_lesson: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_lesson[record_lesson_number(record)].append(record)
    lesson_numbers = sorted(by_lesson, key=lambda value: int(value))
    if len(lesson_numbers) != 17:
        raise ValueError(f"Expected 17 lessons in train/validation pool, found {len(lesson_numbers)}")

    selected: list[dict] = []
    for index, lesson_number in enumerate(lesson_numbers, start=1):
        quota = 4 if index <= 9 else 3
        candidates = by_lesson[lesson_number]
        for record in candidates:
            record["_flags"] = issue_flags(record, stem_counts)
        # Preserve a 42 MCQ / 18 essay mix and deliberately cover all three
        # difficulty levels. Essay records are mostly difficulty 3; MCQ slots
        # alternate 1/2 so the queue does not collapse onto one level.
        if quota == 4:
            mcq_difficulties = [1, 1, 2] if index <= 6 else [1, 2, 2]
            essay_difficulties = [3]
        elif index == 17:
            mcq_difficulties = [1]
            essay_difficulties = [3, 3]
        else:
            mcq_difficulties = [1, 2]
            essay_difficulties = [3]
        for question_type, difficulty_targets in (
            ("multiple_choice", mcq_difficulties),
            ("short_essay", essay_difficulties),
        ):
            typed = [
                record for record in candidates
                if record_question(record).get("question_type") == question_type
            ]
            for target_difficulty in difficulty_targets:
                matching = [
                    record for record in typed
                    if record_difficulty(record) == target_difficulty
                ]
                matching.sort(key=lambda record: (
                    0 if record["_flags"] else 1,
                    str(record.get("record_id")),
                ))
                if not matching:
                    raise ValueError(
                        f"Lesson {lesson_number} lacks difficulty {target_difficulty} "
                        f"{question_type} record"
                    )
                selected.append(matching[0])
                typed.remove(matching[0])

    if len(selected) != count:
        raise AssertionError(f"Expected {count} selected records, found {len(selected)}")
    return selected


def review_row(record: dict, order: int) -> dict:
    question = deepcopy(record_question(record))
    choices = {choice.get("label"): choice.get("text", "") for choice in question.get("choices", [])}
    provenance = record.get("provenance") or {}
    flags = list(record.get("_flags", []))
    return {
        "review_id": f"IR60-{order:03d}",
        "source_split": record.get("split", ""),
        "source_record_id": record.get("sample_id", ""),
        "lesson_id": provenance.get("lesson_id", ""),
        "lesson_number": provenance.get("lesson_number", ""),
        "lesson_title": provenance.get("lesson_title", ""),
        "topic_id": provenance.get("topic_id", ""),
        "question_type": question.get("question_type", ""),
        "difficulty": provenance.get("difficulty", ""),
        "bloom_level": provenance.get("bloom_level", ""),
        "stem": question.get("stem", ""),
        "choice_A": choices.get("A", ""), "choice_B": choices.get("B", ""),
        "choice_C": choices.get("C", ""), "choice_D": choices.get("D", ""),
        "correct_answer": question.get("correct_answer", ""),
        "explanation": question.get("explanation", ""),
        "source_chunk_id": (provenance.get("source_chunk_ids") or [""])[0],
        "source_page": (provenance.get("source_book_pages") or [""])[0],
        "evidence_quote": (provenance.get("source_citations") or [{}])[0].get("quote", ""),
        "context": record.get("context", ""),
        "issue_flags": ";".join(flags),
        "review_priority": "high" if flags else ("medium" if question.get("question_type") == "short_essay" else "standard"),
        "reviewer_id": "", "review_date": "", "factual_accuracy": "", "source_support": "",
        "unique_correct_answer": "", "clarity": "", "curriculum_alignment": "",
        "cognitive_alignment": "", "distractor_quality": "", "pedagogical_language": "",
        "difficulty_fit": "", "factual_error_found": "", "teacher_decision": "",
        "editing_minutes": "", "teacher_comment": "", "revision_version": "v0-review",
    }


def choose_gold_records(records: list[dict], per_lesson: int) -> list[dict]:
    by_lesson: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_lesson[record_lesson_number(record)].append(record)
    if len(by_lesson) != 17:
        raise ValueError("Retrieval gold requires all 17 lessons")
    selected = []
    for lesson_number in sorted(by_lesson, key=lambda value: int(value)):
        candidates = sorted(
            by_lesson[lesson_number],
            key=lambda record: (
                len((record.get("context") or "")) < 80,
                str(record.get("record_id")),
            ),
        )
        seen_chunks: set[str] = set()
        lesson_selected = []
        for record in candidates:
            chunk_id = ((record.get("provenance") or {}).get("source_chunk_ids") or [""])[0]
            if chunk_id and chunk_id not in seen_chunks:
                lesson_selected.append(record)
                seen_chunks.add(chunk_id)
            if len(lesson_selected) == per_lesson:
                break
        if len(lesson_selected) < per_lesson:
            for record in candidates:
                if record not in lesson_selected:
                    lesson_selected.append(record)
                if len(lesson_selected) == per_lesson:
                    break
        selected.extend(lesson_selected)
    return selected


def gold_row(record: dict, order: int) -> dict:
    question = record_question(record)
    provenance = record.get("provenance") or {}
    citation = (provenance.get("source_citations") or [{}])[0]
    return {
        "query_id": f"RG-{order:03d}",
        "query": question.get("stem", ""),
        "lesson_id": provenance.get("lesson_id", ""),
        "lesson_number": provenance.get("lesson_number", ""),
        "lesson_title": provenance.get("lesson_title", ""),
        "topic_id": provenance.get("topic_id", ""),
        "question_type": question.get("question_type", ""),
        "difficulty": provenance.get("difficulty", ""),
        "source_page": (provenance.get("source_book_pages") or [""])[0],
        "candidate_chunk_id": (provenance.get("source_chunk_ids") or [""])[0],
        "source_quote": citation.get("quote", ""),
        "source_context": record.get("context", ""),
        "relevant_chunk_ids": "",
        "reviewer_id": "",
        "review_status": "pending_teacher_review",
        "comment": "Giáo viên chọn tất cả chunk thực sự đủ bằng chứng cho truy vấn; không chỉ dựa vào candidate_chunk_id.",
    }


def write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    records = pool_records(args.data_dir)
    selected = choose_review_records(records, args.review_count)
    review_rows = [review_row(record, index) for index, record in enumerate(selected, start=1)]
    review_csv = args.review_dir / "CobraQ_Independent_Review_60.csv"
    write_csv(review_csv, REVIEW_HEADERS, review_rows)

    gold_records = choose_gold_records(records, args.gold_per_lesson)
    gold_rows = [gold_row(record, index) for index, record in enumerate(gold_records, start=1)]
    write_csv(args.gold_output, GOLD_HEADERS, gold_rows)

    manifest = {
        "schema_version": "1.0",
        "review_queue_id": "cobraq-independent-review-60-v1",
        "selection_pool": "aqg_v2 approved train + validation; test excluded",
        "selection_pool_hashes": {
            split: sha256_file(args.data_dir / f"{split}.jsonl")
            for split in ("train", "validation")
        },
        "review_queue": {
            "path": str(review_csv.resolve()),
            "count": len(review_rows),
            "lesson_counts": dict(Counter(row["lesson_number"] for row in review_rows)),
            "question_type_counts": dict(Counter(row["question_type"] for row in review_rows)),
            "difficulty_counts": dict(Counter(str(row["difficulty"]) for row in review_rows)),
            "priority_counts": dict(Counter(row["review_priority"] for row in review_rows)),
            "issue_flag_counts": dict(Counter(
                flag for row in review_rows for flag in row["issue_flags"].split(";") if flag
            )),
        },
        "retrieval_gold_queue": {
            "path": str(args.gold_output.resolve()),
            "count": len(gold_rows),
            "per_lesson": args.gold_per_lesson,
            "status": "pending_teacher_review",
        },
        "teacher_instructions": [
            "Không xem điểm rubric 5/5 của người duyệt trước.",
            "Chấm độc lập factuality, source support, đáp án, độ rõ và sư phạm.",
            "Với essay, bỏ qua unique_correct_answer và distractor_quality.",
            "Chỉ sửa nội dung sau khi ghi nhận quyết định và comment; lưu revision_version.",
            "Retrieval gold phải điền relevant_chunk_ids bằng chunk_id thật và reviewer_id/review_status.",
        ],
    }
    manifest_path = args.review_dir / "review_queue_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
