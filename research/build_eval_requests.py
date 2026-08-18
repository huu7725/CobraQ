"""Create the deterministic preregistered AQG request set for C0-C3."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK = ROOT / "research" / "configs" / "history12_kntt.json"
DEFAULT_DESIGN = ROOT / "research" / "configs" / "eval_design_v2.json"
DEFAULT_OUT = ROOT / "research" / "datasets" / "eval_requests.jsonl"
BLOOM_BY_DIFFICULTY = {1: "remember", 2: "understand", 3: "analyze"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-config", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    book = json.loads(args.book_config.read_text(encoding="utf-8"))
    requests = []
    for topic in book["topics"]:
        for lesson in topic["lessons"]:
            for difficulty in (1, 2, 3):
                question_type = "short_essay" if difficulty == 3 else "multiple_choice"
                requests.append(
                    {
                        "prompt_id": f"{lesson['lesson_id']}-d{difficulty}",
                        "lesson_id": lesson["lesson_id"],
                        "lesson_title": lesson["title"],
                        "topic_id": topic["topic_id"],
                        "question_type": question_type,
                        "difficulty": difficulty,
                        "bloom_level": BLOOM_BY_DIFFICULTY[difficulty],
                        "num_questions": 1,
                        "learning_objective": f"Đánh giá nội dung trọng tâm của bài {lesson['number']}: {lesson['title']}",
                    }
                )
    design = json.loads(args.design.read_text(encoding="utf-8"))
    selected_ids = design["selected_prompt_ids"]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Evaluation design contains duplicate prompt IDs")
    by_id = {record["prompt_id"]: record for record in requests}
    missing = [prompt_id for prompt_id in selected_ids if prompt_id not in by_id]
    if missing:
        raise ValueError(f"Evaluation prompt IDs missing from book configuration: {missing}")
    selected = [by_id[prompt_id] for prompt_id in selected_ids]

    expected = design["expected_distribution"]
    for field in ("topic_id", "difficulty", "question_type"):
        actual = Counter(str(record[field]) for record in selected)
        target = Counter({str(key): int(value) for key, value in expected[field].items()})
        if actual != target:
            raise ValueError(
                f"Evaluation {field} distribution changed: actual={dict(actual)} target={dict(target)}"
            )
    distinct_lessons = len({record["lesson_id"] for record in selected})
    if distinct_lessons != int(expected["distinct_lessons"]):
        raise ValueError(
            f"Evaluation distinct lesson count changed: {distinct_lessons} "
            f"!= {expected['distinct_lessons']}"
        )

    rng = random.Random(args.seed)
    rng.shuffle(selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for record in selected:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"design={design['design_id']} wrote={len(selected)} path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
