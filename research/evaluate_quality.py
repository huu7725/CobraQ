"""Report BLEU-4, ROUGE-L, entity P/R/F1 and separately reviewed historical factuality."""
import argparse
import json
from pathlib import Path
from backend.app.research.store import read_jsonl
from evaluation.metrics.research_quality import evaluate_quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Choose a new report path")
    try:
        report = evaluate_quality(read_jsonl(args.input))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
