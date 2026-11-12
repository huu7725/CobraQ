from __future__ import annotations

import csv
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.research import router, get_store
from backend.app.core.security import get_current_user
from backend.app.research.schemas import SourceChunk, Question, ExamRequest, digest, parse_question
from backend.app.research.store import CorpusStore, write_jsonl
from backend.app.research.retrieval import search
from backend.app.research.trust import check_question, citation_for
from backend.app.research.generation import generate, messages
from evaluation.metrics.retrieval import compute_retrieval_metrics_for_entry, generate_retrieval_report
from research.evaluate_retrieval import evaluate
from research.verify_adapter import held_out


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.store = CorpusStore(root)
        self.chunk = SourceChunk(id="source-1", text="Liên hợp quốc được thành lập năm 1945 để duy trì hòa bình và an ninh quốc tế.",
                                 source="SGK", source_sha256="0" * 64, book_page=7, pdf_page=9,
                                 lesson_id=1, lesson_title="Liên hợp quốc", topic_id=1, provenance="review_pdf_extract")
        self.q = Question(question_type="multiple_choice", stem="Liên hợp quốc được thành lập vào năm nào?",
                          choices={"A": "1945", "B": "1946", "C": "1947", "D": "1948"},
                          correct_answer="A", explanation="Liên hợp quốc được thành lập năm 1945 theo SGK.")
        write_jsonl(root / "corpus/chunks.jsonl", [self.chunk.model_dump()])
        write_jsonl(root / "datasets/independent_review_60.jsonl", [{"id":"q1", "lesson_id":1,
                    "question":self.q.model_dump(), "chunk_ids":["source-1"], "book_page":7,
                    "quote":self.chunk.text, "review_status":"review_required", "reviewer_id":"", "reviewed_at":""}])
        with (root / "datasets/retrieval_gold.csv").open("w", encoding="utf-8", newline="") as stream:
            row = {"id":"n1", "query":"Liên hợp quốc năm 1945", "lesson_id":1,
                   "candidate_chunk_ids":json.dumps({"A":"source-1"}), "relevant_chunk_ids":"[]",
                   "review_status":"review_required", "reviewer_id":"", "reviewed_at":""}
            writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
        (root / "corpus/lessons.json").write_text('[{"id":1,"title":"SGK"}]', encoding="utf-8")
        self.user = {"sub":"teacher@example.invalid", "role":"teacher"}
        self.app = FastAPI(); self.app.include_router(router, prefix="/api")
        self.app.dependency_overrides[get_store] = lambda: self.store
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def approve(self, kind, row_id, **kwargs):
        row = next(r for r in self.store.rows(kind) if r["id"] == row_id)
        return self.store.review(kind, row_id, expected_hash=digest(row), decision="teacher_approved",
                                 reviewer="teacher@example.invalid", **kwargs)

    def approve_question(self):
        self.approve("chunks", "source-1")
        return self.approve("questions", "q1")

    def test_no_unapproved_practice_or_retrieval(self):
        self.assertEqual(self.store.questions(), [])
        self.assertEqual(search(self.store.chunks, "Liên hợp quốc"), [])
        self.assertEqual(len(search(self.store.chunks, "Liên hợp quốc", approved_only=False)), 1)

    def test_requires_source_approval(self):
        with self.assertRaisesRegex(ValueError, "nguồn"):
            self.approve("questions", "q1")

    def test_practice_revision_does_not_modify_originals(self):
        paths = [self.store.root / p for p in ["corpus/chunks.jsonl", "datasets/independent_review_60.jsonl"]]
        originals = [p.read_bytes() for p in paths]
        self.approve_question()
        self.assertEqual(len(self.store.questions()), 1)
        self.assertEqual(originals, [p.read_bytes() for p in paths])

    def test_source_revision_invalidates_approved_question(self):
        self.approve_question()
        self.approve("chunks", "source-1", source_text=self.chunk.text + " Nguồn đã đối chiếu lại.")
        self.assertEqual(self.store.questions(), [])

    def test_source_rejection_invalidates_practice(self):
        self.approve_question()
        row = self.store.rows("chunks")[0]
        self.store.review("chunks", row["id"], expected_hash=digest(row), decision="rejected", reviewer="teacher")
        self.assertEqual(self.store.questions(), [])

    def test_stale_revision_rejected(self):
        old_hash = digest(self.store.rows("chunks")[0])
        self.approve("chunks", "source-1")
        with self.assertRaisesRegex(ValueError, "thay đổi"):
            self.store.review("chunks", "source-1", expected_hash=old_hash, decision="rejected", reviewer="teacher")

    def test_teacher_can_reject_a_malformed_recovered_draft(self):
        rows = self.store.rows("questions")
        rows[0]["question"]["choices"]["B"] = "1945"
        write_jsonl(self.store.root / "datasets/independent_review_60.jsonl", rows)
        response = self.client.post('/api/research/reviews/questions/q1', json={
            "expected_hash":digest(rows[0]), "decision":"rejected"})
        self.assertEqual(response.status_code, 200)

    def test_corrupt_revision_rejected(self):
        self.approve("chunks", "source-1")
        path = next((self.store.root / "reviews/chunks").glob("*.json"))
        event = json.loads(path.read_text(encoding="utf-8")); event["row"]["text"] += " modified"
        path.write_text(json.dumps(event), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integrity"):
            _ = self.store.chunks

    def test_learning_objectives_cannot_be_approved(self):
        with self.assertRaises(ValueError):
            self.approve("chunks", "source-1", source_text="Sau bài học em có thể trình bày sự thành lập của Liên hợp quốc.")

    def test_lesson_filter(self):
        self.approve("chunks", "source-1")
        self.assertEqual(search(self.store.chunks, "Liên hợp quốc", lesson_id=2), [])
        self.assertEqual(len(search(self.store.chunks, "Liên hợp quốc", lesson_id=1)), 1)

    def test_gold_not_inferred(self):
        with self.assertRaises(ValueError):
            evaluate(self.store, ["keyword"])

    def test_approved_gold_evaluated_and_invalidated_by_source_change(self):
        self.approve("chunks", "source-1")
        self.approve("gold", "n1", relevant_chunk_ids=["source-1"])
        report = evaluate(self.store, ["keyword"])
        self.assertEqual(report["modes"]["keyword"]["mrr"], 1)
        self.approve("chunks", "source-1", source_text=self.chunk.text + " Đã sửa bản OCR.")
        with self.assertRaisesRegex(ValueError, "thay đổi"):
            evaluate(self.store, ["keyword"])

    def test_gold_rejects_non_candidate(self):
        with self.assertRaises(ValueError):
            self.approve("gold", "n1", relevant_chunk_ids=["invented"])

    def test_never_auto_certifies_semantics(self):
        approved = self.chunk.model_copy(update={"review_status":"teacher_approved"})
        result = check_question(self.q, [citation_for(approved)], [approved])
        self.assertTrue(result["automatic_checks_passed"])
        self.assertEqual(result["status"], "needs_teacher_review")
        self.assertEqual(result["semantic_support"], "not_assessed")

    def test_unsupported_claim_year_detected_but_distractors_ignored(self):
        result = check_question(self.q, [citation_for(self.chunk)], [self.chunk])
        self.assertNotIn("unsupported_year", result["issues"])
        q = self.q.model_copy(update={"explanation":"Liên hợp quốc thành lập vào năm 1950."})
        self.assertIn("unsupported_year", check_question(q, [citation_for(self.chunk)], [self.chunk])["issues"])

    def test_tampered_citation(self):
        cite = citation_for(self.chunk).model_copy(update={"book_page":99})
        self.assertFalse(check_question(self.q, [cite], [self.chunk])["provenance_valid"])

    def test_schema_duplicate_choices_and_wrong_type(self):
        q = self.q.model_dump(); q["choices"]["B"] = "1945"
        with self.assertRaises(ValueError): parse_question(json.dumps(q), "multiple_choice")
        with self.assertRaises(ValueError): parse_question(self.q.model_dump_json(), "short_answer")

    def test_duplicate_json_keys(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            parse_question('{"question_type":"short_answer","question_type":"multiple_choice"}', "multiple_choice")

    def test_failed_generation_keeps_raw_and_telemetry(self):
        req = ExamRequest(query="Liên hợp quốc", lesson_id=1, configuration="C0")
        result = generate(req, self.store, backend=lambda r,c: ({"raw_output":"not json", "latency_seconds":1.25}, c))
        self.assertFalse(result["valid_json"]); self.assertFalse(result["valid_schema"])
        self.assertEqual(result["raw_output"], "not json"); self.assertEqual(result["latency_seconds"], 1.25)
        self.assertNotIn("Ngữ liệu", messages(req, [])[1]["content"])

    def test_rag_requires_reviewed_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "nguồn đã duyệt"):
            generate(ExamRequest(query="Liên hợp quốc", lesson_id=1), self.store)

    def test_metrics_first_relevant_and_missing_relevant(self):
        d = compute_retrieval_metrics_for_entry("q", ["a","b","c"], [], {"b","missing"})
        self.assertEqual(d["mrr"], .5); self.assertEqual(d["hit_rate_1"], 0)
        self.assertEqual(d["hit_rate_3"], 1); self.assertAlmostEqual(d["precision_3"], 1/3, places=4)
        self.assertEqual(d["recall"], .5)
        self.assertAlmostEqual(d["ndcg_5"], (1 / __import__('math').log2(3)) / (1 + 1 / __import__('math').log2(3)), places=4)

    def test_metrics_no_hits_or_duplicates(self):
        no = compute_retrieval_metrics_for_entry("q", ["wrong"], [], {"missing"})
        self.assertEqual(no["mrr"], 0); self.assertEqual(no["hit_rate_5"], 0)
        duplicate = compute_retrieval_metrics_for_entry("q", ["a","a"], [], {"a"})
        self.assertEqual(duplicate["num_retrieved"], 1)

    def test_citations_do_not_create_retrieval_gold(self):
        path = self.store.root / "logs.jsonl"
        write_jsonl(path, [{"event_type":"tutoring_query", "retrieval_chunks":["a"], "citation_present":True}])
        report = generate_retrieval_report(path)
        self.assertEqual(report["evaluation_status"], "awaiting_teacher_gold")
        self.assertEqual(report["total_queries"], 0)

    def test_verifier_prevents_source_leakage(self):
        test = [{"id":"test", "chunk_ids":["a"], "split":"test", "review_status":"teacher_approved"}]
        with self.assertRaisesRegex(ValueError, "leakage"):
            held_out(test, [{"id":"train", "chunk_ids":["a"]}], [{"id":"val", "chunk_ids":["b"]}], 1)

    def test_verifier_rejects_recovered_review_drafts(self):
        with self.assertRaises(ValueError): held_out(self.store.questions(False), [], [], 10)

    def test_api_auth_required(self):
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get('/api/research/practice').status_code, 401)

    def test_student_cannot_review_or_read_drafts(self):
        self.user = {"sub":"student", "role":"student"}
        self.assertEqual(self.client.get('/api/research/reviews/questions').status_code, 403)
        self.assertEqual(self.client.get('/api/research/search?query=quoc&include_drafts=true').status_code, 403)
        self.assertEqual(self.client.post('/api/research/auto-exam', json={"query":"Liên hợp quốc", "lesson_id":1}).status_code, 403)

    def test_practice_api_hides_answers_and_grades_on_server(self):
        self.approve_question(); self.user = {"sub":"student", "role":"student"}
        data = self.client.get('/api/research/practice').json()
        self.assertNotIn("correct_answer", data["questions"][0])
        result = self.client.post('/api/research/practice/q1/answer', json={"answer":"A"})
        self.assertTrue(result.json()["correct"])
        self.assertEqual(self.client.post('/api/research/practice/q1/answer', json={"answer":"Z"}).status_code, 422)

    def test_teacher_api_reviewer_identity_from_auth(self):
        row = self.client.get('/api/research/reviews/chunks').json()["rows"][0]
        response = self.client.post('/api/research/reviews/chunks/source-1', json={"expected_hash":row["revision_hash"], "decision":"teacher_approved"})
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["reviewer_id"], self.user["sub"])
        self.assertEqual(self.client.post('/api/research/reviews/chunks/source-1', json={"expected_hash":row["revision_hash"], "decision":"rejected"}).status_code, 409)

    def test_short_answer_is_never_auto_graded(self):
        self.approve("chunks", "source-1")
        q = Question(question_type="short_answer", stem="Trình bày vai trò của Liên hợp quốc?", correct_answer="Duy trì hòa bình và an ninh quốc tế.", explanation="SGK mô tả vai trò duy trì hòa bình và an ninh quốc tế.")
        self.approve("questions", "q1", question=q.model_dump())
        self.assertIsNone(self.client.post('/api/research/practice/q1/answer', json={"answer":"test"}).json()["correct"])


if __name__ == "__main__":
    unittest.main()
