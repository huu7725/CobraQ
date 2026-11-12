"""Compare independent THPT groups using paired pre/post gains and Welch's independent t-test."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev


def analyze(rows: list[dict]) -> dict:
    from scipy.stats import ttest_ind
    if len({r["participant_id"] for r in rows}) != len(rows):
        raise ValueError("Mỗi học sinh chỉ có một cặp pre/post; participant_id phải duy nhất")
    groups = {"experimental": [], "control": []}
    for row in rows:
        if not row["participant_id"].strip() or row["group"] not in groups:
            raise ValueError("Cần mã ẩn danh và group=experimental/control")
        pre, post = float(row["pre_test"]), float(row["post_test"])
        if any(not math.isfinite(v) or not 0 <= v <= 10 for v in (pre, post)):
            raise ValueError("Điểm pre/post phải hữu hạn trong thang 0-10; không tự điền điểm thiếu")
        groups[row["group"]].append((pre, post, post - pre))
    if any(len(values) < 2 for values in groups.values()):
        raise ValueError("Cần ít nhất 2 cặp hoàn chỉnh cho mỗi nhóm")
    def welch(index):
        a, b = ([r[index] for r in groups[g]] for g in ("experimental", "control"))
        if stdev(a) == stdev(b) == 0:
            return {"status": "undefined_zero_variance", "t": None, "p_two_sided": None}
        test = ttest_ind(a, b, equal_var=False)
        return {"status": "computed", "t": float(test.statistic), "p_two_sided": float(test.pvalue), "df": float(test.df)}
    return {"groups": {g:{"n":len(v), "mean_pre":mean(r[0] for r in v), "mean_post":mean(r[1] for r in v),
                           "mean_gain":mean(r[2] for r in v), "sd_gain":stdev(r[2] for r in v)} for g,v in groups.items()},
            "primary_outcome": "post_test_minus_pre_test", "welch_gain":welch(2), "baseline_welch":welch(0),
            "notice": "Cần thiết kế nhóm độc lập và kiểm soát sai lệch chọn mẫu trước khi diễn giải hiệu quả."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Choose a new report path")
    try:
        with args.input.open(encoding="utf-8-sig", newline="") as stream:
            report = analyze(list(csv.DictReader(stream)))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__": main()
