"""Export the approved AQG v1 splits using CobraQ's compact v2 model target.

The teacher-approved pedagogical content is copied verbatim. Identifiers,
lesson metadata, citations, difficulty, Bloom level, and experiment condition
remain in provenance only and are never included in the model response target.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data" / "research" / "aqg_v1" / "approved"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "research" / "aqg_v2" / "approved"
DEFAULT_WORKBOOK = (
    ROOT / "outputs" / "cobraq_aqg_review" / "CobraQ_AQG_600_Review.xlsx"
)
SPLIT_NAMES = ("train", "validation", "test")
TARGET_FIELDS = (
    "question_type",
    "stem",
    "choices",
    "correct_answer",
    "explanation",
)
SERVER_MANAGED_FIELDS = (
    "question_id",
    "lesson_id",
    "difficulty",
    "bloom_level",
    "citations",
    "generation_condition",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--expected-count", type=int, default=600)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the compact JSONL splits and dataset_manifest.json.",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def content_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: each row must be a JSON object")
            records.append(record)
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def compact_question(source_question: dict[str, Any]) -> dict[str, Any]:
    missing = set(TARGET_FIELDS) - source_question.keys()
    if missing:
        raise ValueError(f"Approved question is missing target fields: {sorted(missing)}")
    compact = {field: deepcopy(source_question[field]) for field in TARGET_FIELDS}

    question_type = compact["question_type"]
    choices = compact["choices"]
    if question_type == "multiple_choice":
        if not isinstance(choices, list) or len(choices) != 4:
            raise ValueError("Approved multiple-choice question must have exactly four choices")
        labels = [choice.get("label") for choice in choices if isinstance(choice, dict)]
        if labels != list("ABCD"):
            raise ValueError("Approved multiple-choice labels must be ordered A/B/C/D")
        if compact["correct_answer"] not in labels:
            raise ValueError("Approved multiple-choice answer must be one of A/B/C/D")
    elif question_type == "short_essay":
        if choices != []:
            raise ValueError("Approved short-essay question must have choices=[]")
    else:
        raise ValueError(f"Unsupported question_type={question_type!r}")

    for field in ("stem", "correct_answer", "explanation"):
        if not isinstance(compact[field], str) or not compact[field].strip():
            raise ValueError(f"Approved question has an empty {field}")
    return compact


def compact_record(source: dict[str, Any], split: str) -> tuple[dict[str, Any], dict[str, int]]:
    if source.get("review_status") != "teacher_approved":
        raise ValueError(f"{source.get('record_id', '<unknown>')}: source is not teacher_approved")
    if source.get("split") != split:
        raise ValueError(
            f"{source.get('record_id', '<unknown>')}: split={source.get('split')!r}, "
            f"expected {split!r}"
        )
    questions = source.get("response", {}).get("questions", [])
    if len(questions) != 1 or not isinstance(questions[0], dict):
        raise ValueError(
            f"{source.get('record_id', '<unknown>')}: expected exactly one approved question"
        )
    source_question = questions[0]
    target_question = compact_question(source_question)
    for field in TARGET_FIELDS:
        if target_question[field] != source_question[field]:
            raise AssertionError(
                f"{source.get('record_id', '<unknown>')}: content changed in {field}"
            )

    target_response = {"questions": [target_question]}
    source_response_chars = len(json.dumps(source["response"], ensure_ascii=False))
    target_response_chars = len(json.dumps(target_response, ensure_ascii=False))
    source_record_id = str(source.get("record_id") or "").strip()
    if not source_record_id:
        raise ValueError("Approved source record is missing record_id")

    output = {
        "schema_version": "2.0",
        "sample_id": source_record_id.replace("aqg-v1-", "aqg-v2-", 1),
        "instruction": source["instruction"],
        "context": source.get("context", ""),
        "response": target_response,
        "review_status": "teacher_approved",
        "split": split,
        "provenance": {
            "source_dataset": "cobraq_history12_aqg_v1",
            "source_record_id": source_record_id,
            "source_approved_content_sha256": source.get("approved_content_sha256", ""),
            "lesson_id": source.get("lesson_id", ""),
            "lesson_number": source.get("lesson_number"),
            "lesson_title": source.get("lesson_title", ""),
            "topic_id": source.get("topic_id", ""),
            "difficulty": source.get("difficulty"),
            "bloom_level": source.get("bloom_level", ""),
            "source_chunk_ids": deepcopy(source.get("source_chunk_ids", [])),
            "source_book_pages": deepcopy(source.get("source_book_pages", [])),
            "source_question_id": source_question.get("question_id"),
            "source_citations": deepcopy(source_question.get("citations", [])),
            "source_generation_condition": source_question.get("generation_condition"),
            "reviewer_id": source.get("reviewer_id", ""),
            "review_date": source.get("review_date", ""),
        },
        "model_target_sha256": content_sha256(target_response),
    }
    return output, {
        "source_response_chars": source_response_chars,
        "target_response_chars": target_response_chars,
    }


def _chunk_sets(splits: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    return {
        split: {
            chunk_id
            for record in records
            for chunk_id in record["provenance"].get("source_chunk_ids", [])
        }
        for split, records in splits.items()
    }


def build_compact_dataset(
    source_dir: Path,
    workbook: Path,
    expected_count: int = 600,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    manifest_path = source_dir / "approved_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not workbook.exists():
        raise FileNotFoundError(workbook)
    workbook_hash = file_sha256(workbook)
    expected_workbook_hash = source_manifest.get("workbook_sha256")
    if workbook_hash != expected_workbook_hash:
        raise ValueError(
            "The review workbook no longer matches the approved v1 manifest; "
            "rerun finalization before building v2"
        )

    compact_splits: dict[str, list[dict[str, Any]]] = {}
    all_source_ids: list[str] = []
    all_sample_ids: list[str] = []
    type_counts: Counter[str] = Counter()
    field_preservation_counts: Counter[str] = Counter()
    excluded_field_counts: Counter[str] = Counter()
    normalized_mcq_stems: Counter[str] = Counter()
    essay_teacher_completion_notes = 0
    source_chars = 0
    target_chars = 0

    for split in SPLIT_NAMES:
        source_path = source_dir / f"{split}.jsonl"
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        expected_hash = source_manifest.get("split_hashes", {}).get(split)
        if expected_hash and file_sha256(source_path) != expected_hash:
            raise ValueError(f"{source_path} does not match the approved v1 manifest hash")
        source_records = load_jsonl(source_path)
        expected_split_count = source_manifest.get("split_counts", {}).get(split)
        if expected_split_count is not None and len(source_records) != expected_split_count:
            raise ValueError(
                f"{split}: found {len(source_records)} records, expected {expected_split_count}"
            )

        compact_records = []
        for source in source_records:
            output, sizes = compact_record(source, split)
            compact_records.append(output)
            all_source_ids.append(output["provenance"]["source_record_id"])
            all_sample_ids.append(output["sample_id"])
            question = output["response"]["questions"][0]
            type_counts[question["question_type"]] += 1
            if question["question_type"] == "multiple_choice":
                normalized_mcq_stems[" ".join(question["stem"].lower().split())] += 1
            elif "giáo viên cần hoàn thiện đáp án và thang điểm" in question[
                "explanation"
            ].lower():
                essay_teacher_completion_notes += 1
            for field in TARGET_FIELDS:
                field_preservation_counts[field] += 1
            source_question = source["response"]["questions"][0]
            for field in set(source_question) - set(TARGET_FIELDS):
                excluded_field_counts[field] += 1
            source_chars += sizes["source_response_chars"]
            target_chars += sizes["target_response_chars"]
        compact_splits[split] = compact_records

    total = sum(len(records) for records in compact_splits.values())
    if total != expected_count:
        raise ValueError(f"Found {total} approved records, expected exactly {expected_count}")
    if len(set(all_source_ids)) != total or len(set(all_sample_ids)) != total:
        raise ValueError("Duplicate source_record_id or sample_id found across splits")

    chunk_sets = _chunk_sets(compact_splits)
    overlaps = {
        "train_validation": sorted(chunk_sets["train"] & chunk_sets["validation"]),
        "train_test": sorted(chunk_sets["train"] & chunk_sets["test"]),
        "validation_test": sorted(chunk_sets["validation"] & chunk_sets["test"]),
    }
    if any(overlaps.values()):
        raise ValueError(f"Source chunk leakage detected: {overlaps}")

    duplicate_mcq_stems = [count for count in normalized_mcq_stems.values() if count > 1]
    reduction = 0.0 if source_chars == 0 else 1 - target_chars / source_chars
    manifest = {
        "schema_version": "2.0",
        "dataset_id": "cobraq_history12_aqg_v2_compact",
        "created_from": "cobraq_history12_aqg_v1 teacher-approved splits",
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_workbook": str(workbook.resolve()),
        "source_workbook_sha256": workbook_hash,
        "source_workbook_hash_verified": True,
        "model_input_fields": ["instruction", "context"],
        "model_target_path": "response.questions[]",
        "model_target_fields": list(TARGET_FIELDS),
        "server_managed_fields": list(SERVER_MANAGED_FIELDS),
        "target_contract": {
            "multiple_choice": "exactly four ordered choices A/B/C/D",
            "short_essay": "choices must be an empty list",
            "metadata_in_model_target": False,
        },
        "split_policy": source_manifest.get("split_policy"),
        "split_counts": {
            split: len(records) for split, records in compact_splits.items()
        },
        "total_records": total,
        "question_type_counts": dict(sorted(type_counts.items())),
        "content_preservation_audit": {
            "source_records_compared": total,
            "records_with_changed_teacher_content": 0,
            "verbatim_field_matches": dict(field_preservation_counts),
            "excluded_from_model_target": dict(sorted(excluded_field_counts.items())),
            "source_response_characters": source_chars,
            "compact_response_characters": target_chars,
            "character_reduction_fraction": round(reduction, 6),
        },
        "source_chunk_leakage_audit": {
            "leakage_detected": False,
            "overlaps": overlaps,
            "unique_chunks_by_split": {
                split: len(chunks) for split, chunks in chunk_sets.items()
            },
        },
        "quality_observations_preserved_without_edit": {
            "short_essay_teacher_completion_note_count": essay_teacher_completion_notes,
            "normalized_duplicate_mcq_stem_groups": len(duplicate_mcq_stems),
            "mcq_records_in_duplicate_stem_groups": sum(duplicate_mcq_stems),
            "interpretation": (
                "These are approved-data limitations recorded for the next review cycle; "
                "the compact export does not alter them."
            ),
        },
        "source_review_audit_summary": source_manifest.get("review_audit_summary", {}),
    }
    return compact_splits, manifest


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    compact_splits, manifest = build_compact_dataset(
        args.source_dir,
        args.workbook,
        expected_count=args.expected_count,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if not args.apply:
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, records in compact_splits.items():
        write_jsonl(records, args.output_dir / f"{split}.jsonl")
    manifest["output_hashes"] = {
        split: file_sha256(args.output_dir / f"{split}.jsonl")
        for split in SPLIT_NAMES
    }
    (args.output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"compact_dataset={args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
