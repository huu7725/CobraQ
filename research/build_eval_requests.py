"""Create a deterministic, lesson-balanced AQG request set for C0-C3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK = ROOT / "research" / "configs" / "history12_kntt.json"
DEFAULT_OUT = ROOT / "research" / "datasets" / "eval_requests.jsonl"
BLOOM_BY_DIFFICULTY = {1: "remember", 2: "understand", 3: "analyze"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-config", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample", type=int, default=40)
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
    rng = random.Random(args.seed)
    rng.shuffle(requests)
    selected = requests[: min(args.sample, len(requests))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for record in selected:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote={len(selected)} path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
