"""Re-evaluate saved C0-C3 question outputs against cited/verification chunks."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics.factuality import aggregate_factuality, evaluate_question_factuality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    by_condition = defaultdict(list)
    with args.results.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") != "ok":
                continue
            chunks = {item["chunk_id"]: item for item in row.get("retrieved_chunks", [])}
            condition = row["condition"]
            for question in row.get("questions", []):
                evaluation_question = dict(question)
                evaluation_question.pop("auto_evaluation", None)
                if condition in {"C0", "C2"}:
                    # Verification retrieval is hidden from the model but supplies a common
                    # evidence reference for fair factuality comparison.
                    evaluation_question["citations"] = [
                        {"chunk_id": chunk_id, "page": item["page"], "quote": item["text"]}
                        for chunk_id, item in chunks.items()
                    ]
                by_condition[condition].append(
                    evaluate_question_factuality(evaluation_question, chunks)
                )
    report = {condition: aggregate_factuality(items) for condition, items in sorted(by_condition.items())}
    output = args.output or args.results.with_suffix(".factuality.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
