"""Build a deterministic, source-grounded AQG candidate set for teacher review.

The generated records are annotation candidates, not teacher-approved training
data. Every item cites an OCR-reviewed textbook chunk and remains pending until
it passes the teacher rubric through ``finalize_aqg_dataset.py``.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.question_schema import GeneratedQuestion  # noqa: E402


DEFAULT_CORPUS = ROOT / "data" / "research" / "history12_kntt" / "chunks_reviewed.jsonl"
DEFAULT_BOOK_CONFIG = ROOT / "research" / "configs" / "history12_kntt.json"
DEFAULT_PLAN = ROOT / "research" / "configs" / "aqg_annotation_plan.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "research" / "aqg_v1"

YEAR_RE = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
SPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^0-9a-zà-ỹđ]+", re.IGNORECASE)
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
LEADING_MARKER_RE = re.compile(r"^[\s+•¢«»\-–—]+")
BAD_PREFIXES = (
    "học xong",
    "biết cách",
    "nêu được",
    "trình bày được",
    "trinh bày được",
    "phân tích được",
    "giải thích được",
    "nhận biết được",
    "hình ",
    "bảng ",
    "sơ đồ",
    "tư liệu",
    "em có biết",
    "luyện tập",
    "vận dụng",
    "khai thác",
    "quan sát",
    "lập bảng",
    "viết bài",
    "sưu tầm",
    "tìm hiểu",
    "hãy ",
)
FACT_VERBS = (
    " là ", " đã ", " được ", " diễn ra", " thành lập", " trở thành",
    " góp phần", " thực hiện", " xác định", " khẳng định", " mở ra",
    " đạt ", " tổ chức", " kí ", " ký ", " ban hành", " tiến hành",
    " phát triển", " quyết định", " tuyên bố", " giành ", " đề ra",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--book-config", type=Path, default=DEFAULT_BOOK_CONFIG)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return NON_WORD_RE.sub(" ", value.casefold()).strip()


def clean_sentence(value: str) -> str:
    value = LEADING_MARKER_RE.sub("", value)
    return SPACE_RE.sub(" ", value).strip()


def is_eligible_sentence(value: str, *, relaxed: bool = False) -> bool:
    lowered = value.casefold()
    if not 55 <= len(value) <= 420:
        return False
    if "?" in value or "@" in value or CYRILLIC_RE.search(value) or "�" in value:
        return False
    if any(lowered.startswith(prefix) for prefix in BAD_PREFIXES):
        return False
    if "vào vở" in lowered:
        return False
    first_alpha = next((char for char in value if char.isalpha()), "")
    if first_alpha and not first_alpha.isupper():
        return False
    letters = [char for char in value if char.isalpha()]
    if letters and sum(char.isupper() for char in letters) / len(letters) > 0.8:
        return False
    if value.endswith("...") or value[-1] not in '.!;)”"':
        return False
    if len(value.split()) < 9:
        return False
    if sum(char.isalpha() for char in value) < len(value) * 0.45:
        return False
    if not relaxed and not any(marker in f" {lowered} " for marker in FACT_VERBS):
        return False
    return True


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_lessons(path: Path) -> dict[str, dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    lessons: dict[str, dict[str, Any]] = {}
    for topic in config["topics"]:
        for lesson in topic["lessons"]:
            lessons[lesson["lesson_id"]] = {
                **lesson,
                "topic_id": topic["topic_id"],
                "topic_title": topic["title"],
            }
    return lessons


def sentence_pool(chunks: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    ordered = sorted(chunks, key=lambda row: (row.get("book_page", 0), row["chunk_id"]))
    for relaxed in (False, True):
        for chunk in ordered:
            lesson_id = chunk.get("lesson_id") or ""
            if not lesson_id or chunk.get("review_required"):
                continue
            if chunk.get("segment_type") not in {"content", "source_box"}:
                continue
            for raw in SENTENCE_SPLIT_RE.split(chunk.get("text", "")):
                sentence = clean_sentence(raw)
                key = normalize(sentence)
                if not key or key in seen[lesson_id]:
                    continue
                if not is_eligible_sentence(sentence, relaxed=relaxed):
                    continue
                seen[lesson_id].add(key)
                pools[lesson_id].append(
                    {
                        "text": sentence,
                        "chunk_id": chunk["chunk_id"],
                        "book_page": int(chunk["book_page"]),
                        "lesson_id": lesson_id,
                        "topic_id": chunk.get("topic_id", ""),
                        "section_title": clean_sentence(chunk.get("section_title", "")),
                        "lesson_title": chunk.get("lesson_title", ""),
                    }
                )
    return dict(pools)


def build_targets(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Create exact per-lesson/type/difficulty targets for 600 records."""
    targets: list[dict[str, Any]] = []
    for lesson_index, (lesson_id, quota) in enumerate(plan["lesson_quotas"].items(), start=1):
        mcq_count = 25 if lesson_index <= 12 else 24
        essay_count = int(quota) - mcq_count
        d1_mcq = 15 if lesson_index <= 2 else 14
        d2_mcq = mcq_count - d1_mcq
        d3_essay = 8 if lesson_index == 3 else 7
        d2_essay = essay_count - d3_essay
        targets.extend(
            {"lesson_id": lesson_id, "question_type": "multiple_choice", "difficulty": 1,
             "bloom_level": "remember"}
            for _ in range(d1_mcq)
        )
        targets.extend(
            {"lesson_id": lesson_id, "question_type": "multiple_choice", "difficulty": 2,
             "bloom_level": "understand"}
            for _ in range(d2_mcq)
        )
        targets.extend(
            {"lesson_id": lesson_id, "question_type": "short_essay", "difficulty": 2,
             "bloom_level": "understand"}
            for _ in range(d2_essay)
        )
        targets.extend(
            {"lesson_id": lesson_id, "question_type": "short_essay", "difficulty": 3,
             "bloom_level": "analyze"}
            for _ in range(d3_essay)
        )
    return targets


def _choices(values: list[str], correct: str, rng: random.Random) -> tuple[list[dict[str, str]], str]:
    options = list(dict.fromkeys([correct, *values]))
    if len(options) < 4:
        raise ValueError("Not enough unique choices")
    options = options[:4]
    rng.shuffle(options)
    labels = ["A", "B", "C", "D"]
    return (
        [{"label": label, "text": text} for label, text in zip(labels, options)],
        labels[options.index(correct)],
    )


def _citation(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "chunk_id": evidence["chunk_id"],
        "page": evidence["book_page"],
        "quote": evidence["text"][:800],
    }]


def _year_item(
    target: dict[str, Any], evidence: dict[str, Any], year_bank: list[str], rng: random.Random
) -> tuple[dict[str, Any], str]:
    years = sorted(set(YEAR_RE.findall(evidence["text"])))
    if len(years) != 1:
        raise ValueError("Year-cloze evidence must contain exactly one unique year")
    correct = years[0]
    masked = YEAR_RE.sub("[NĂM]", evidence["text"])
    distractors = sorted(
        (year for year in set(year_bank) if year != correct),
        key=lambda year: (abs(int(year) - int(correct)), year),
    )[:12]
    if len(distractors) < 3:
        raise ValueError("Not enough year distractors")
    sampled = rng.sample(distractors, 3)
    choices, answer = _choices(sampled, correct, rng)
    question = {
        "question_type": "multiple_choice",
        "stem": f'Theo SGK Lịch sử 12, năm nào hoàn chỉnh nhận định sau: "{masked}"?',
        "choices": choices,
        "correct_answer": answer,
        "explanation": f"Dữ kiện gốc trong SGK ghi năm {correct}: {evidence['text']}",
        "difficulty": target["difficulty"],
        "bloom_level": target["bloom_level"],
        "lesson_id": target["lesson_id"],
        "citations": _citation(evidence),
        "generation_condition": "C3",
    }
    return question, "year_cloze_mcq_v1"


def _source_selection_item(
    target: dict[str, Any], evidence: dict[str, Any], distractor_pool: list[dict[str, Any]],
    lesson: dict[str, Any], rng: random.Random, variant: int,
) -> tuple[dict[str, Any], str]:
    candidates = [
        item["text"] for item in distractor_pool
        if item["lesson_id"] != target["lesson_id"]
        and item["topic_id"] != evidence["topic_id"]
        and item["text"] != evidence["text"]
        and 0.45 <= len(item["text"]) / max(len(evidence["text"]), 1) <= 1.8
    ]
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) < 3:
        candidates = list(dict.fromkeys(
            item["text"] for item in distractor_pool
            if item["lesson_id"] != target["lesson_id"] and item["text"] != evidence["text"]
        ))
    choices, answer = _choices(rng.sample(candidates, min(12, len(candidates))), evidence["text"], rng)
    section = evidence["section_title"] or lesson["title"]
    stems = [
        f"Theo SGK Lịch sử 12, nhận định nào sau đây thuộc nội dung Bài {lesson['number']}: {lesson['title']}?",
        f"Nhận định nào sau đây được SGK trình bày trong phần {section} của Bài {lesson['number']}?",
        f"Đâu là thông tin phù hợp với nội dung Bài {lesson['number']} trong SGK Lịch sử 12?",
        f"Khi tìm hiểu Bài {lesson['number']}: {lesson['title']}, học sinh có thể rút ra nhận định nào sau đây?",
        f"Thông tin nào sau đây có nguồn đối chiếu tại trang {evidence['book_page']} của Bài {lesson['number']}?",
    ]
    question = {
        "question_type": "multiple_choice",
        "stem": stems[variant % len(stems)],
        "choices": choices,
        "correct_answer": answer,
        "explanation": f"Nhận định đúng được trích từ SGK trang {evidence['book_page']}: {evidence['text']}",
        "difficulty": target["difficulty"],
        "bloom_level": target["bloom_level"],
        "lesson_id": target["lesson_id"],
        "citations": _citation(evidence),
        "generation_condition": "C3",
    }
    return question, "source_selection_mcq_v1"


def _essay_item(
    target: dict[str, Any], evidence: dict[str, Any], lesson: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    if target["difficulty"] == 3:
        stem = (
            f"Dựa vào dẫn chứng SGK sau, hãy phân tích nội dung và nêu mối liên hệ của "
            f"dẫn chứng với Bài {lesson['number']}: {lesson['title']}. "
            f'Dẫn chứng: "{evidence["text"]}"'
        )
        guidance = (
            "Bài làm cần giải thích đúng dữ kiện trong dẫn chứng, đặt dữ kiện vào nội dung của bài "
            "và trình bày mối liên hệ có căn cứ."
        )
    else:
        stem = (
            "Dựa vào SGK Lịch sử 12, hãy trình bày ngắn gọn nội dung lịch sử được thể hiện "
            f'trong dẫn chứng sau: "{evidence["text"]}"'
        )
        guidance = "Bài làm cần nêu đúng và đủ nội dung lịch sử trực tiếp được thể hiện trong dẫn chứng."
    question = {
        "question_type": "short_essay",
        "stem": stem,
        "choices": [],
        "correct_answer": f"Ý chính tối thiểu cần có: {evidence['text']}",
        "explanation": (
            f"{guidance} Nguồn đối chiếu: SGK trang {evidence['book_page']}. "
            "Giáo viên cần hoàn thiện đáp án và thang điểm trước khi phê duyệt."
        ),
        "difficulty": target["difficulty"],
        "bloom_level": target["bloom_level"],
        "lesson_id": target["lesson_id"],
        "citations": _citation(evidence),
        "generation_condition": "C3",
    }
    return question, "extractive_guided_essay_v1"


def build_candidates(
    chunks: list[dict[str, Any]], lessons: dict[str, dict[str, Any]], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    rng = random.Random(int(plan["seed"]))
    pools = sentence_pool(chunks)
    targets = build_targets(plan)
    all_evidence = [item for lesson_pool in pools.values() for item in lesson_pool]
    year_bank = sorted({year for item in all_evidence for year in YEAR_RE.findall(item["text"])})
    year_pools = {
        lesson_id: [item for item in lesson_pool if len(set(YEAR_RE.findall(item["text"]))) == 1]
        for lesson_id, lesson_pool in pools.items()
    }
    per_lesson_index: Counter[str] = Counter()
    per_lesson_cursor: Counter[str] = Counter()
    per_lesson_year_cursor: Counter[str] = Counter()
    used_stems: set[str] = set()
    records: list[dict[str, Any]] = []

    for target in targets:
        lesson_id = target["lesson_id"]
        lesson_pool = pools.get(lesson_id, [])
        if not lesson_pool:
            raise ValueError(f"No eligible evidence for {lesson_id}")
        lesson = lessons[lesson_id]
        question: dict[str, Any] | None = None
        method = ""
        selected: dict[str, Any] | None = None
        attempts = max(len(lesson_pool) * 3, 100)
        for attempt in range(attempts):
            year_pool = year_pools.get(lesson_id, [])
            prefer_year = (
                target["question_type"] == "multiple_choice"
                and target["difficulty"] == 1
                and per_lesson_year_cursor[lesson_id] < len(year_pool)
            )
            if prefer_year:
                selected = year_pool[per_lesson_year_cursor[lesson_id]]
                per_lesson_year_cursor[lesson_id] += 1
            else:
                cursor = per_lesson_cursor[lesson_id]
                selected = lesson_pool[cursor % len(lesson_pool)]
                per_lesson_cursor[lesson_id] += 1
            years = sorted(set(YEAR_RE.findall(selected["text"])))
            try:
                if target["question_type"] == "multiple_choice" and target["difficulty"] == 1 and len(years) == 1:
                    question, method = _year_item(target, selected, year_bank, rng)
                elif target["question_type"] == "multiple_choice":
                    question, method = _source_selection_item(
                        target, selected, all_evidence, lesson, rng, attempt
                    )
                else:
                    question, method = _essay_item(target, selected, lesson)
            except ValueError:
                question = None
                continue
            answer_text = question["correct_answer"]
            if question["question_type"] == "multiple_choice":
                answer_text = next(
                    choice["text"] for choice in question["choices"]
                    if choice["label"] == question["correct_answer"]
                )
            stem_key = normalize(question["stem"] + " " + answer_text)
            if stem_key in used_stems:
                question = None
                continue
            used_stems.add(stem_key)
            break
        if question is None or selected is None:
            raise ValueError(f"Could not create a unique candidate for {target}")

        per_lesson_index[lesson_id] += 1
        question_id = f"aqg-v1-{lesson_id}-{per_lesson_index[lesson_id]:03d}"
        question["question_id"] = question_id
        instruction = (
            f"Sinh một câu hỏi {target['question_type']} cho Bài {lesson['number']} - {lesson['title']}; "
            f"độ khó {target['difficulty']}/3, Bloom {target['bloom_level']}; chỉ dùng ngữ liệu được cung cấp."
        )
        response = {"questions": [question]}
        record = {
            "record_id": question_id,
            "lesson_id": lesson_id,
            "lesson_number": lesson["number"],
            "lesson_title": lesson["title"],
            "topic_id": lesson["topic_id"],
            "instruction": instruction,
            "context": f"[{selected['chunk_id']} | trang {selected['book_page']}]\n{selected['text']}",
            "response": response,
            "question_type": target["question_type"],
            "difficulty": target["difficulty"],
            "bloom_level": target["bloom_level"],
            "candidate_generator": method,
            "source_chunk_ids": [selected["chunk_id"]],
            "source_book_pages": [selected["book_page"]],
            "evidence_quote": selected["text"],
            "review_status": "pending_teacher_review",
            "reviewer_id": "",
            "review_date": "",
            "comment": "",
            "annotation_version": "1.0",
        }
        record["candidate_content_sha256"] = content_hash({
            "instruction": record["instruction"],
            "context": record["context"],
            "response": response,
            "source_chunk_ids": record["source_chunk_ids"],
        })
        records.append(record)
    return records


def validate_candidates(
    records: list[dict[str, Any]], chunks: list[dict[str, Any]], plan: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    chunk_map = {row["chunk_id"]: row for row in chunks}
    ids = [row["record_id"] for row in records]
    stems: list[str] = []
    for record in records:
        if record["review_status"] != "pending_teacher_review":
            errors.append(f"{record['record_id']}: invalid initial review status")
        try:
            question = GeneratedQuestion.model_validate(record["response"]["questions"][0])
        except Exception as error:  # Pydantic exposes detailed context in the message.
            errors.append(f"{record['record_id']}: schema error: {error}")
            continue
        answer_text = question.correct_answer
        if question.question_type == "multiple_choice":
            answer_text = next(
                choice.text for choice in question.choices if choice.label == question.correct_answer
            )
        stems.append(normalize(question.stem + " " + answer_text))
        for citation in question.citations:
            source = chunk_map.get(citation.chunk_id)
            if source is None:
                errors.append(f"{record['record_id']}: unknown chunk {citation.chunk_id}")
                continue
            if source.get("review_required"):
                errors.append(f"{record['record_id']}: source chunk still requires OCR review")
            if int(source["book_page"]) != citation.page:
                errors.append(f"{record['record_id']}: citation page mismatch")
            if normalize(citation.quote) not in normalize(source["text"]):
                errors.append(f"{record['record_id']}: quote is not present in source chunk")

    if len(records) != int(plan["total_candidates"]):
        errors.append(f"expected {plan['total_candidates']} records, got {len(records)}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate record_id values")
    if len(stems) != len(set(stems)):
        errors.append("duplicate normalized question-and-answer pairs")

    lesson_counts = Counter(row["lesson_id"] for row in records)
    if dict(lesson_counts) != plan["lesson_quotas"]:
        errors.append(f"lesson distribution mismatch: {dict(lesson_counts)}")
    type_counts = Counter(row["question_type"] for row in records)
    difficulty_counts = Counter(str(row["difficulty"]) for row in records)
    bloom_counts = Counter(row["bloom_level"] for row in records)
    expected = plan["target_distribution"]
    for name, actual, target in (
        ("question_type", type_counts, expected["question_type"]),
        ("difficulty", difficulty_counts, expected["difficulty"]),
        ("bloom_level", bloom_counts, expected["bloom_level"]),
    ):
        if dict(actual) != target:
            errors.append(f"{name} distribution mismatch: {dict(actual)}")
    if errors:
        raise ValueError("Invalid AQG candidates:\n- " + "\n- ".join(errors[:40]))
    return {
        "total_candidates": len(records),
        "lessons": dict(sorted(lesson_counts.items())),
        "question_type": dict(type_counts),
        "difficulty": dict(sorted(difficulty_counts.items())),
        "bloom_level": dict(bloom_counts),
        "generation_method": dict(Counter(row["candidate_generator"] for row in records)),
        "initial_review_status": "pending_teacher_review",
        "teacher_approved": 0,
    }


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    for required in (args.corpus, args.book_config, args.plan):
        if not required.exists():
            raise FileNotFoundError(required)
    chunks = load_jsonl(args.corpus)
    lessons = load_lessons(args.book_config)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    records = build_candidates(chunks, lessons, plan)
    summary = validate_candidates(records, chunks, plan)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = args.output_dir / "candidates_pending.jsonl"
    write_jsonl(records, candidates_path)
    summary.update({
        "schema_version": "1.0",
        "dataset_id": plan["dataset_id"],
        "seed": plan["seed"],
        "source_corpus": str(args.corpus.resolve()),
        "source_corpus_sha256": file_sha256(args.corpus),
        "plan": str(args.plan.resolve()),
        "plan_sha256": file_sha256(args.plan),
        "candidates": str(candidates_path.resolve()),
        "candidates_sha256": file_sha256(candidates_path),
        "policy": "candidate_only_teacher_approval_required_before_training",
    })
    (args.output_dir / "candidate_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
