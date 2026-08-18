"""Run a gated pilot or full AQG experiment through CobraQ C0-C3."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.auto_exam_pipeline import AutoExamPipeline, AutoExamRequest  # noqa: E402
from research.evaluate_pilot import (  # noqa: E402
    DEFAULT_EXPERIMENT_CONFIG,
    DEFAULT_EVAL_DESIGN,
    DEFAULT_MANIFEST,
    assert_full_run_allowed,
    build_pilot_report,
    select_pilot_requests,
    summarize_condition,
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


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
    )
    parser.add_argument(
        "--phase",
        choices=["pilot", "full", "custom"],
        default="pilot",
        help="Pilot is the safe default; full requires a GO pilot report.",
    )
    parser.add_argument("--pilot-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pilot-report", type=Path)
    parser.add_argument("--experiment-config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG)
    parser.add_argument("--eval-design", type=Path, default=DEFAULT_EVAL_DESIGN)
    parser.add_argument("--conditions", default="C0,C1,C2,C3")
    parser.add_argument("--limit", type=int, help="Custom/debug runs only")
    parser.add_argument("--backend", choices=["local", "api"], default="local")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    conditions = [value.strip() for value in args.conditions.split(",") if value.strip()]
    if not set(conditions) <= {"C0", "C1", "C2", "C3"}:
        raise ValueError("Conditions must be selected from C0,C1,C2,C3")
    all_requests = load_jsonl(args.requests)
    manifest = json.loads(args.pilot_manifest.read_text(encoding="utf-8"))
    required_conditions = manifest["required_conditions"]

    if args.phase == "pilot":
        if args.limit is not None:
            raise ValueError("--limit is not allowed for the preregistered pilot")
        if conditions != required_conditions:
            raise ValueError(f"Pilot must run all conditions in order: {required_conditions}")
        design = json.loads(args.eval_design.read_text(encoding="utf-8"))
        if {row["prompt_id"] for row in all_requests} != set(design["selected_prompt_ids"]):
            raise ValueError("Request set does not match the preregistered full evaluation design")
        requests = select_pilot_requests(all_requests, manifest)
        output = args.output or ROOT / "data" / "research" / "pilot_v2_results.jsonl"
    elif args.phase == "full":
        if args.limit is not None:
            raise ValueError("--limit is not allowed for the full experiment")
        if conditions != required_conditions:
            raise ValueError(f"Full experiment must run all conditions in order: {required_conditions}")
        if not args.pilot_report or not args.pilot_report.is_file():
            raise ValueError("--pilot-report pointing to a GO report is required for --phase full")
        report = json.loads(args.pilot_report.read_text(encoding="utf-8"))
        assert_full_run_allowed(
            report,
            args.pilot_manifest,
            args.requests,
            args.experiment_config,
            args.eval_design,
        )
        design = json.loads(args.eval_design.read_text(encoding="utf-8"))
        if {row["prompt_id"] for row in all_requests} != set(design["selected_prompt_ids"]):
            raise ValueError("Request set does not match the preregistered full evaluation design")
        config = json.loads(args.experiment_config.read_text(encoding="utf-8"))
        expected = int(config["evaluation"]["questions_per_condition"])
        if len(all_requests) != expected or len({row["prompt_id"] for row in all_requests}) != expected:
            raise ValueError(
                f"Full request set must contain exactly {expected} unique prompt IDs; "
                f"found {len(all_requests)} rows"
            )
        requests = all_requests
        output = args.output or ROOT / "data" / "research" / "experiment_results.jsonl"
    else:
        requests = all_requests
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit must be at least 1")
            requests = requests[: args.limit]
        config = json.loads(args.experiment_config.read_text(encoding="utf-8"))
        full_size = int(config["evaluation"]["questions_per_condition"])
        if len(requests) >= full_size and conditions == required_conditions:
            raise ValueError(
                "A 40x4 run is blocked in custom mode; use --phase full with a GO pilot report"
            )
        output = args.output or ROOT / "data" / "research" / "custom_results.jsonl"

    pipeline = AutoExamPipeline(args.experiment_config)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with output.open("w", encoding="utf-8", newline="\n") as stream:
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
                    if not (args.continue_on_error or args.phase in {"pilot", "full"}):
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                        raise
                results.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(f"[{condition}] {index:03d}/{len(requests):03d} {row['status']}", flush=True)

    summary = {
        "schema_version": "2.0",
        "phase": args.phase,
        "requests_per_condition": len(requests),
        "conditions": {
            condition: summarize_condition(
                [row for row in results if row.get("condition") == condition], condition
            )
            for condition in conditions
        },
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.phase == "pilot":
        report = build_pilot_report(
            results,
            manifest,
            manifest_path=args.pilot_manifest,
            requests_path=args.requests,
            experiment_config_path=args.experiment_config,
            eval_design_path=args.eval_design,
        )
        report_path = output.with_suffix(".pilot_report.json")
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        print(f"pilot_decision={report['decision']} report={report_path}")
        if report["decision"] != "go":
            print("Full 40x4 experiment remains blocked; inspect gate_failures in the report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
