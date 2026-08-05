"""Evaluate keyword, dense, or hybrid retrieval against teacher-labeled gold data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.vector_service import VectorService  # noqa: E402
from evaluation.metrics.retrieval import (  # noqa: E402
    aggregate_retrieval_metrics,
    compute_retrieval_metrics_for_entry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", type=Path)
    parser.add_argument("--mode", choices=["keyword", "dense", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "data" / "research" / "history12_kntt")
    args = parser.parse_args()
    service = VectorService(
        persist_dir=str(args.corpus_dir / "chroma_db"),
        collection_name="cobraq_history12_kntt_v1",
        embedding_model="intfloat/multilingual-e5-small",
    )
    with args.gold.open(encoding="utf-8-sig", newline="") as stream:
        gold_rows = [row for row in csv.DictReader(stream) if row.get("review_status") == "teacher_approved"]
    if not gold_rows:
        raise ValueError("No teacher_approved retrieval gold rows found")
    per_query = []
    for row in gold_rows:
        relevant = {value.strip() for value in row["relevant_chunk_ids"].split(";") if value.strip()}
        results = service.search(
            row["query"],
            doc_id="history12_kntt_2023_sample",
            top_k=args.top_k,
            mode=args.mode,
            filters={"lesson_id": row["lesson_id"]} if row.get("lesson_id") else None,
        )
        metrics = compute_retrieval_metrics_for_entry(
            row["query"], [item.id for item in results], [], relevant
        )
        per_query.append(
            {
                "query_id": row["query_id"],
                "query": row["query"],
                "retrieved_chunk_ids": [item.id for item in results],
                "relevant_chunk_ids": sorted(relevant),
                **metrics,
            }
        )
    report = {
        "mode": args.mode,
        "top_k": args.top_k,
        "ground_truth_status": "teacher_approved",
        "summary": aggregate_retrieval_metrics(per_query),
        "queries": per_query,
    }
    output = args.output or args.gold.with_name(f"retrieval_{args.mode}_report.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
