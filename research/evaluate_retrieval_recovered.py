"""Evaluate only complete, independently approved retrieval gold; never infer gold from citations."""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path

from backend.app.research.schemas import digest
from backend.app.research.store import CorpusStore
from backend.app.research.retrieval import search, evidence_issue
from evaluation.metrics.retrieval import compute_retrieval_metrics_for_entry, aggregate_retrieval_metrics


def evaluate(store: CorpusStore, modes: list[str]) -> dict:
    rows, chunks = store.rows("gold"), store.chunks
    by_id = {c.id: c for c in chunks}
    if not rows:
        raise ValueError("Missing retrieval gold")
    for row in rows:
        ids = json.loads(row["relevant_chunk_ids"])
        date.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None
        if (row["review_status"] != "teacher_approved" or not row["reviewer_id"] or not row["reviewed_at"]
                or not ids or len(set(ids)) != len(ids)
                or any(cid not in by_id or by_id[cid].review_status != "teacher_approved"
                       or by_id[cid].lesson_id != int(row["lesson_id"]) or evidence_issue(by_id[cid]) for cid in ids)):
            raise ValueError(f"Gold {row['id']} chưa được giáo viên xác nhận đầy đủ; không tính điểm trên tập con.")
        if row.get("approved_source_hash") != digest([by_id[cid].model_dump() for cid in ids]):
            raise ValueError(f"Gold {row['id']}: nguồn đã thay đổi, cần duyệt lại")
    reports = {}
    for mode in modes:
        per_query = []
        for row in rows:
            hits = search(chunks, row["query"], lesson_id=int(row["lesson_id"]), mode=mode)
            ids = [h["chunk"]["id"] for h in hits]
            metrics = compute_retrieval_metrics_for_entry(row["query"], ids, list(by_id), set(json.loads(row["relevant_chunk_ids"])))
            per_query.append({"id": row["id"], "retrieved_ids": ids, **metrics})
        reports[mode] = {**aggregate_retrieval_metrics(per_query), "per_query": per_query}
    return {"corpus_hash": store.fingerprint, "gold_hash": digest(rows), "modes": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--modes", nargs="+", choices=["keyword", "dense", "hybrid"], default=["keyword", "dense", "hybrid"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(CorpusStore(args.root), args.modes)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    if args.output.exists():
        parser.error("Output exists; choose a new report path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
