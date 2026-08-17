"""Run the same AQG request set through CobraQ conditions C0-C3."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.auto_exam_pipeline import AutoExamPipeline, AutoExamRequest  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requests",
        type=Path,
        default=ROOT / "research" / "datasets" / "eval_requests.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "research" / "experiment_results.jsonl",
    )
    parser.add_argument("--conditions", default="C0,C1,C2,C3")
    parser.add_argument("--limit", type=int, help="Use only the first N requests for a pilot run")
    parser.add_argument("--backend", choices=["local", "api"], default="local")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    requests = load_jsonl(args.requests)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be at least 1")
        requests = requests[: args.limit]
    conditions = [value.strip() for value in args.conditions.split(",") if value.strip()]
    if not set(conditions) <= {"C0", "C1", "C2", "C3"}:
        raise ValueError("Conditions must be selected from C0,C1,C2,C3")
    pipeline = AutoExamPipeline()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for condition in conditions:
            for index, record in enumerate(requests, start=1):
                body = AutoExamRequest(
                    condition_id=condition,
                    lesson_id=record["lesson_id"],
                    question_type=record["question_type"],
                    difficulty=record["difficulty"],
                    bloom_level=record["bloom_level"],
                    num_questions=record.get("num_questions", 1),
                    learning_objective=record.get("learning_objective", ""),
                    model_backend=args.backend,
                )
                try:
                    result = pipeline.generate(body)
                    row = {
                        "run_at": datetime.now(timezone.utc).isoformat(),
                        "prompt_id": record["prompt_id"],
                        "request": record,
                        "status": "ok",
                        **result,
                    }
                except Exception as error:
                    row = {
                        "run_at": datetime.now(timezone.utc).isoformat(),
                        "prompt_id": record.get("prompt_id", ""),
                        "request": record,
                        "condition": condition,
                        "status": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                    if not args.continue_on_error:
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                        raise
                results.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(f"[{condition}] {index:03d}/{len(requests):03d} {row['status']}", flush=True)

    summary = {}
    for condition in conditions:
        condition_rows = [row for row in results if row.get("condition") == condition]
        successful = [row for row in condition_rows if row["status"] == "ok"]
        failed = [row for row in condition_rows if row["status"] == "error"]
        latencies = [row["latency_ms"] for row in successful]
        questions = [question for row in successful for question in row.get("questions", [])]
        summary[condition] = {
            "runs": len(condition_rows),
            "successful_runs": len(successful),
            "failed_runs": len(failed),
            "success_rate": round(len(successful) / max(len(condition_rows), 1), 4),
            "error_types": dict(sorted(Counter(row["error_type"] for row in failed).items())),
            "questions": len(questions),
            "auto_verified_rate": round(
                sum(q["auto_evaluation"]["status"] == "auto_verified" for q in questions) / max(len(questions), 1),
                4,
            ),
            "mean_fact_support_rate": round(
                statistics.fmean(q["auto_evaluation"]["fact_support_rate"] for q in questions), 4
            ) if questions else 0.0,
            "latency_p50_ms": percentile(latencies, 0.50),
            "latency_p95_ms": percentile(latencies, 0.95),
        }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
