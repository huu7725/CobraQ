"""Compute classical item difficulty, discrimination, and Cronbach alpha."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import statistics


def correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3 or len(xs) != len(ys):
        return 0.0
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else 0.0


def cronbach_alpha(matrix: list[list[float]]) -> float:
    if not matrix or len(matrix[0]) < 2 or len(matrix) < 2:
        return 0.0
    item_count = len(matrix[0])
    columns = [[row[index] for row in matrix] for index in range(item_count)]
    item_variances = sum(statistics.variance(column) for column in columns)
    totals = [sum(row) for row in matrix]
    total_variance = statistics.variance(totals)
    if total_variance == 0:
        return 0.0
    return item_count / (item_count - 1) * (1 - item_variances / total_variance)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Long CSV: student_id,item_id,is_correct")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    responses: dict[str, dict[str, float]] = defaultdict(dict)
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            responses[row["student_id"]][row["item_id"]] = float(row["is_correct"])
    items = sorted({item for student in responses.values() for item in student})
    students = sorted(responses)
    complete = [student for student in students if all(item in responses[student] for item in items)]
    matrix = [[responses[student][item] for item in items] for student in complete]
    if not matrix:
        raise ValueError("No complete student response rows found")
    item_results = []
    for index, item in enumerate(items):
        item_scores = [row[index] for row in matrix]
        rest_scores = [sum(row) - row[index] for row in matrix]
        difficulty = statistics.fmean(item_scores)
        discrimination = correlation(item_scores, rest_scores)
        item_results.append(
            {
                "item_id": item,
                "difficulty_p": round(difficulty, 4),
                "point_biserial": round(discrimination, 4),
                "difficulty_label": "hard" if difficulty < 0.3 else ("easy" if difficulty > 0.8 else "moderate"),
                "discrimination_flag": "review" if discrimination < 0.2 else "acceptable",
            }
        )
    report = {
        "students": len(complete),
        "items": len(items),
        "cronbach_alpha": round(cronbach_alpha(matrix), 4),
        "analysis_scope": "exploratory" if len(complete) < 100 else "confirmatory_classical_test_theory",
        "item_results": item_results,
    }
    output = args.output or args.input.with_suffix(".analysis.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
