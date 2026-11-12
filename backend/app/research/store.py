from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import json
import os
import re
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .schemas import SourceChunk, Question, digest

_review_lock = RLock()

ROOT = Path(__file__).resolve().parents[3]


def research_root() -> Path:
    from ..core.config import get_settings
    return get_settings().research_dir


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    temporary.replace(path)


class CorpusStore:
    def __init__(self, root: Path | None = None):
        self.root = root or research_root()

    @property
    def chunks(self) -> list[SourceChunk]:
        return [SourceChunk.model_validate(r) for r in self.rows("chunks")]

    def rows(self, kind: str) -> list[dict]:
        paths = {"chunks": "corpus/chunks.jsonl", "questions": "datasets/independent_review_60.jsonl",
                 "gold": "datasets/retrieval_gold.csv"}
        path = self.root / paths[kind]
        if kind == "gold":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        else:
            rows = read_jsonl(path)
        by_id = {r["id"]: r for r in rows}
        for revision in sorted((self.root / "reviews" / kind).glob("*.json")):
            entry = json.loads(revision.read_text(encoding="utf-8"))
            current = by_id.get(entry["id"])
            if current is None or digest(current) != entry["before_hash"] or digest(entry["row"]) != entry["after_hash"]:
                raise ValueError(f"Review revision integrity failure: {revision.name}")
            by_id[entry["id"]] = entry["row"]
        return list(by_id.values())

    @property
    def fingerprint(self) -> str:
        return digest([c.model_dump() for c in self.chunks])

    def questions(self, approved_only=True) -> list[dict]:
        rows = self.rows("questions")
        if approved_only:
            approved_chunks = {c.id: c for c in self.chunks if c.review_status == "teacher_approved"}
            rows = [r for r in rows if r.get("review_status") == "teacher_approved"
                    and r.get("reviewer_id") and r.get("reviewed_at")
                    and r.get("approved_content_hash") == digest(r["question"])
                    and r.get("approved_source_hash") == digest([
                        approved_chunks[cid].model_dump() for cid in r["chunk_ids"] if cid in approved_chunks])
                    and r["chunk_ids"] and all(cid in approved_chunks for cid in r["chunk_ids"])]
        return rows

    def review(self, kind: str, row_id: str, *, expected_hash: str, decision: str,
               reviewer: str, question: dict | None = None, relevant_chunk_ids: list[str] | None = None,
               notes: str = "", source_text: str | None = None) -> dict:
        from .retrieval import evidence_issue
        from .trust import check_question, citation_for
        if decision not in {"teacher_approved", "rejected", "review_required"} or not reviewer.strip():
            raise ValueError("Invalid review decision or identity")
        with _review_lock:
            current = next((r for r in self.rows(kind) if r["id"] == row_id), None)
            if current is None:
                raise KeyError(row_id)
            if digest(current) != expected_hash:
                raise ValueError("Dữ liệu đã thay đổi. Tải lại trước khi duyệt.")
            row = dict(current)
            if kind == "chunks" and source_text is not None:
                row["text"] = source_text.strip()
                row["years"] = sorted(set(re.findall(r"\b(?:1\d{3}|20\d{2})\b", row["text"])))
            if kind == "questions":
                if question is not None or decision == "teacher_approved":
                    row["question"] = Question.model_validate(question or row["question"]).model_dump()
                if decision == "teacher_approved":
                    sources = {c.id: c for c in self.chunks}
                    selected = [sources[cid] for cid in row["chunk_ids"]]
                    trust = check_question(Question.model_validate(row["question"]),
                                           [citation_for(c) for c in selected], selected)
                    if trust["issues"] or "Giáo viên cần hoàn" in row["question"]["explanation"]:
                        raise ValueError("Cần duyệt nguồn và sửa lỗi trước khi duyệt câu: " + ", ".join(trust["issues"]))
                    row["approved_content_hash"] = digest(row["question"])
                    row["approved_source_hash"] = digest([c.model_dump() for c in selected])
                    row["quote"] = "\n\n".join(c.text for c in selected)
                    row["book_page"] = selected[0].book_page
            elif kind == "chunks" and decision == "teacher_approved":
                if evidence_issue(SourceChunk.model_validate(row)):
                    raise ValueError("Tiêu đề/mục tiêu bài học không đủ làm bằng chứng")
            elif kind == "gold":
                ids = relevant_chunk_ids if relevant_chunk_ids is not None else json.loads(row["relevant_chunk_ids"])
                candidates = set(json.loads(row["candidate_chunk_ids"]).values())
                chunks = {c.id: c for c in self.chunks}
                if len(ids) != len(set(ids)) or not set(ids) <= candidates:
                    raise ValueError("Gold labels must be unique candidate chunk IDs")
                if decision == "teacher_approved" and (not ids or any(
                    chunks[cid].review_status != "teacher_approved" or evidence_issue(chunks[cid])
                    or chunks[cid].lesson_id != int(row["lesson_id"]) for cid in ids)):
                    raise ValueError("Cần chọn ít nhất một nguồn hợp lệ đã duyệt trong bài")
                row["relevant_chunk_ids"] = json.dumps(ids)
                row["approved_source_hash"] = digest([chunks[cid].model_dump() for cid in ids])
            row.update(review_status=decision, reviewer_id=reviewer, reviewed_at=date.today().isoformat())
            if kind == "chunks":
                SourceChunk.model_validate(row)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            folder = self.root / "reviews" / kind
            folder.mkdir(parents=True, exist_ok=True)
            event = {"id": row_id, "before_hash": digest(current), "after_hash": digest(row),
                     "row": row, "notes": notes, "timestamp": stamp}
            path = folder / f"{stamp}_{uuid4().hex}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
            return row

    def status(self) -> dict:
        chunks = self.chunks
        adapter = Path(os.environ.get("COBRAQ_ADAPTER_DIR", self.root.parent / "artifacts/adapters/history12_lora_v2_1"))
        return {
            "recovery_version": "2026-11-rebuild-1", "scope": "history12-kntt-2023-sample",
            "chunks": len(chunks),
            "approved_chunks": sum(c.review_status == "teacher_approved" for c in chunks),
            "lessons": sorted({c.lesson_id for c in chunks}),
            "review_questions": len(self.questions(False)),
            "practice_questions": len(self.questions(True)),
            "retrieval_queries": len(self.rows("gold")),
            "approved_retrieval_queries": sum(r["review_status"] == "teacher_approved" for r in self.rows("gold")),
            "adapter_available": (adapter / "adapter_config.json").exists(),
            "full_experiment_allowed": False,
            "corpus_hash": self.fingerprint,
            "notice": "Dữ liệu khôi phục cần giáo viên kiểm tra. Chưa khôi phục adapter và kết quả thực nghiệm cũ.",
        }
