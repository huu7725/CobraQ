"""Verify ten held-out examples, keeping malformed generations and runtime failures in the denominator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from backend.app.research.generation import execution_contract, generate, model_paths
from backend.app.research.schemas import ExamRequest
from backend.app.research.store import CorpusStore, read_jsonl


def held_out(test, train, validation, count):
    if not test or not train or not validation:
        raise ValueError("Cần đủ dữ liệu train/validation/test gốc; không thay bằng 60 câu nháp khôi phục.")
    seen = {cid for row in train + validation for cid in row["chunk_ids"]}
    ids = [row["id"] for row in test]
    if len(ids) != len(set(ids)) or set(ids) & {row["id"] for row in train + validation}:
        raise ValueError("Trùng ID giữa các tập dữ liệu")
    if any(not row["chunk_ids"] or seen.intersection(row["chunk_ids"]) for row in test):
        raise ValueError("Source chunk leakage giữa test và train/validation")
    if any(row.get("split") != "test" or row.get("review_status") != "teacher_approved" for row in test):
        raise ValueError("Test phải có split=test và nhãn giáo viên gốc")
    if len(test) < count:
        raise ValueError("Không đủ mẫu held-out")
    return test[:count]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["test", "train", "validation", "output"]:
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    store = CorpusStore(args.root)
    if args.count < 1 or args.output.exists():
        parser.error("count must be positive and output must be a new path")
    try:
        samples = held_out(read_jsonl(args.test), read_jsonl(args.train), read_jsonl(args.validation), args.count)
        model, adapter = model_paths(store)
        if not (model / "config.json").exists() or not (adapter / "adapter_config.json").exists():
            raise ValueError("Thiếu model hoặc adapter v2.1 cục bộ; chưa thể kiểm chứng.")
        requests = [ExamRequest(query=row.get("query", row["question"]["stem"]), lesson_id=row["lesson_id"],
                                question_type=row["question"]["question_type"], configuration="C2") for row in samples]
        contract = execution_contract(store, [r.model_dump() for r in requests])
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    report = {"execution_contract": contract, "runs": [], "factuality": "not_assessed", "full_experiment_allowed": False,
              "requested_total": len(samples), "dataset_hashes": {name:hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()
                                                                   for name in ("train", "validation", "test")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for sample, request in zip(samples, requests):
        try:
            result = generate(request, store)
        except (RuntimeError, OSError, ImportError) as exc:
            result = {"valid_schema": False, "valid_json": False, "runtime_error": str(exc)}
        report["runs"].append({"id": sample["id"], **result})
        report["total"] = len(report["runs"])
        report["valid_schema"] = sum(r["valid_schema"] for r in report["runs"])
        report["valid_json"] = sum(r["valid_json"] for r in report["runs"])
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.output)


if __name__ == "__main__":
    main()
