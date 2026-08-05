"""Score teacher rubric CSV and summarize results by C0-C3 after unblinding."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC = ROOT / "research" / "rubrics" / "teacher_rubric.json"


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "có", "co", "x"}


def score_row(row: dict[str, str], rubric: dict) -> dict:
    question_type = row.get("question_type", "multiple_choice")
    criteria = []
    for criterion in rubric["criteria"]:
        applies_to = criterion.get("applies_to")
        if applies_to and question_type not in applies_to:
            continue
        raw = row.get(criterion["id"], "")
        try:
            score = float(raw)
        except ValueError as error:
            raise ValueError(
                f"Question {row.get('question_id')} has invalid score for {criterion['id']}: {raw}"
            ) from error
        if not 1 <= score <= 5:
            raise ValueError(f"Rubric scores must be between 1 and 5: {criterion['id']}={score}")
        criteria.append((criterion, score))
    total_weight = sum(item[0]["weight"] for item in criteria)
    weighted_score = sum(item[0]["weight"] * item[1] for item in criteria) / total_weight
    critical_scores = [score for criterion, score in criteria if criterion.get("critical")]
    factual_error = truthy(row.get("factual_error_found", ""))
    if weighted_score >= 4.2 and all(score >= 4 for score in critical_scores) and not factual_error:
        computed_decision = "approve"
    elif weighted_score < 3.4 or any(score <= 2 for score in critical_scores) or factual_error:
        computed_decision = "reject"
    else:
        computed_decision = "revise"
    return {
        **row,
        "weighted_score": round(weighted_score, 4),
        "computed_decision": computed_decision,
        "decision_matches_rule": row.get("decision", "").strip().lower() in {"", computed_decision},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rubric = json.loads(args.rubric.read_text(encoding="utf-8"))
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = [score_row(row, rubric) for row in csv.DictReader(stream)]
    if not rows:
        raise ValueError("No teacher ratings found")
    output = args.output or args.input.with_name(args.input.stem + "_scored.csv")
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("condition_id_unblinded") or "unassigned"].append(row)
    summary = {}
    for condition, items in grouped.items():
        scores = [float(item["weighted_score"]) for item in items]
        summary[condition] = {
            "ratings": len(items),
            "questions": len({item["question_id"] for item in items}),
            "mean_weighted_score": round(statistics.fmean(scores), 4),
            "median_weighted_score": round(statistics.median(scores), 4),
            "approve_rate": round(sum(item["computed_decision"] == "approve" for item in items) / len(items), 4),
            "revise_rate": round(sum(item["computed_decision"] == "revise" for item in items) / len(items), 4),
            "reject_rate": round(sum(item["computed_decision"] == "reject" for item in items) / len(items), 4),
            "mean_editing_minutes": round(
                statistics.fmean(float(item["editing_minutes"] or 0) for item in items), 2
            ),
        }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
