from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.experiment_config import get_condition, load_experiment_config
from app.services.auto_exam_pipeline import AutoExamPipeline, AutoExamRequest
from app.services.history_corpus import chunk_page_text, load_book_config, lookup_scope
from app.services.question_schema import GeneratedQuestion, ModelGenerationEnvelope, QuestionContent
from app.services.trust_layer import Chunk, TrustLayer, extract_fact_markers
from app.services.vector_service import VectorService
from evaluation.metrics.factuality import evaluate_question_factuality
from evaluation.metrics.retrieval import compute_retrieval_metrics_for_entry
from research.analyze_student_items import correlation, cronbach_alpha
from research.apply_ocr_review import apply_reviews
from research.build_aqg_candidates import build_targets
from research.build_compact_aqg_dataset import TARGET_FIELDS, compact_record
from research.finalize_aqg_dataset import assign_splits
from research.prepare_ocr_review import classify
from research.score_teacher_rubric import score_row
from research.train_lora import validate_compact_payload


BOOK_CONFIG = ROOT / "research" / "configs" / "history12_kntt.json"


class HistoryCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_book_config(BOOK_CONFIG)

    def test_page_mapping_uses_table_of_contents(self):
        scope = lookup_scope(self.config, 38)
        self.assertEqual(scope["lesson_id"], "lesson_07")
        self.assertEqual(scope["lesson_number"], 7)

    def test_chunk_is_traceable_and_flags_bad_ocr(self):
        text = (
            "Bối cảnh lịch sử (1945 - 1954)\n\n"
            "Ngày 23 - 9 - 1945, cuộc kháng chiến ở Nam Bộ bắt đầu. "
            "Đây là đoạn kiểm thử đủ dài để tạo một chunk có nguồn rõ ràng. " * 5
            + " §£\\ "
        )
        chunks = chunk_page_text(
            text,
            pdf_page=40,
            config=self.config,
            source="SGK Lịch sử 12",
            ocr_confidence=93.0,
        )
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].book_page, 38)
        self.assertEqual(chunks[0].lesson_id, "lesson_07")
        self.assertIn("1945", chunks[0].time_expressions)
        self.assertTrue(chunks[0].review_required)
        self.assertIn("suspicious_ocr_symbols", chunks[0].review_reasons)
        self.assertEqual(chunks[0].ocr_review_status, "pending")

    def test_ocr_pretriage_detects_date_noise_without_auto_approval(self):
        risky = classify(
            {
                "source_text": (
                    "Đêm 22, rạng sáng 23 - ———y 9 - 1945, thực dân Pháp "
                    "đánh úp trụ sở Uỷ ban hành chính Nam Bộ."
                )
            }
        )
        decorative = classify({"source_text": "« Nội dung lịch sử đã được OCR rõ ràng. " * 20})
        self.assertEqual(risky["risk_priority"], "CRITICAL")
        self.assertIn("noise_near_historical_year", risky["risk_flags"])
        self.assertEqual(decorative["risk_priority"], "LOW")


class FactualityTests(unittest.TestCase):
    def test_fact_marker_blocking(self):
        chunks = [
            Chunk(
                id="c1",
                text="Ngày 23 - 9 - 1945, nhân dân Nam Bộ kháng chiến.",
                source="SGK",
                page=38,
                score=0.9,
            )
        ]
        trust = TrustLayer(min_confidence=0.5)
        supported = trust.evaluate("Sự kiện diễn ra ngày 23-9-1945.", chunks)
        unsupported = trust.evaluate("Sự kiện diễn ra năm 1946.", chunks)
        self.assertFalse(supported["hallucination_detected"])
        self.assertTrue(unsupported["hallucination_detected"])
        self.assertIn("1946", unsupported["unsupported_facts"])

    def test_question_citation_validation(self):
        question = {
            "question_id": "test-citation-c1",
            "question_type": "multiple_choice",
            "stem": "Sự kiện nào diễn ra ngày 23-9-1945?",
            "choices": [
                {"label": "A", "text": "Nam Bộ kháng chiến"},
                {"label": "B", "text": "Chiến dịch Điện Biên Phủ"},
                {"label": "C", "text": "Cách mạng tháng Tám"},
                {"label": "D", "text": "Hiệp định Giơ-ne-vơ"},
            ],
            "correct_answer": "A",
            "explanation": "Ngày 23-9-1945, nhân dân Nam Bộ bắt đầu kháng chiến.",
            "difficulty": 1,
            "bloom_level": "remember",
            "lesson_id": "lesson_07",
            "generation_condition": "C3",
            "citations": [{"chunk_id": "c1", "page": 38, "quote": "Ngày 23 - 9 - 1945"}],
        }
        validated = GeneratedQuestion.model_validate(question)
        result = evaluate_question_factuality(
            validated.model_dump(),
            {"c1": {"text": "Ngày 23 - 9 - 1945, nhân dân Nam Bộ bắt đầu kháng chiến."}},
        )
        self.assertFalse(result["factual_error"])
        self.assertTrue(
            AutoExamPipeline._citation_is_valid(
                validated,
                [Chunk(id="c1", text="Ngày 23 - 9 - 1945, nhân dân Nam Bộ bắt đầu kháng chiến.", page=38)],
                True,
            )
        )

    def test_question_schema_rejects_contained_choice(self):
        question = {
            "question_id": "test-contained-choice",
            "question_type": "multiple_choice",
            "stem": "Nhận định nào sau đây đúng theo ngữ liệu Lịch sử 12?",
            "choices": [
                {"label": "A", "text": "Liên hợp quốc thông qua Chương trình nghị sự 2030."},
                {"label": "B", "text": "Nội dung không liên quan đến sự kiện đang được hỏi."},
                {"label": "C", "text": "Liên hợp quốc đặt ra 17 mục tiêu phát triển bền vững."},
                {
                    "label": "D",
                    "text": "Năm 2015, Liên hợp quốc thông qua Chương trình nghị sự 2030.",
                },
            ],
            "correct_answer": "A",
            "explanation": "Ngữ liệu xác nhận nội dung về Chương trình nghị sự 2030.",
            "difficulty": 1,
            "bloom_level": "remember",
            "lesson_id": "lesson_01",
            "generation_condition": "C3",
            "citations": [{"chunk_id": "c1", "page": 11, "quote": "Năm 2015"}],
        }
        with self.assertRaises(ValueError):
            GeneratedQuestion.model_validate(question)

    def test_compact_model_contract_forbids_server_metadata_and_extra_fields(self):
        compact = {
            "questions": [
                {
                    "question_type": "short_essay",
                    "stem": "Trình bày ý nghĩa lịch sử của sự kiện trong ngữ liệu.",
                    "choices": [],
                    "correct_answer": "Nêu được ý nghĩa chính của sự kiện.",
                    "explanation": "Câu trả lời phải bám sát dữ kiện có trong ngữ liệu.",
                    "lesson_id": "lesson_07",
                }
            ]
        }
        with self.assertRaises(ValueError):
            ModelGenerationEnvelope.model_validate(compact)

        missing_choices = {
            "questions": [{key: value for key, value in compact["questions"][0].items()
                           if key not in {"choices", "lesson_id"}}]
        }
        with self.assertRaises(ValueError):
            ModelGenerationEnvelope.model_validate(missing_choices)

    def test_pipeline_attaches_deterministic_metadata_and_rag_citations(self):
        request = AutoExamRequest(
            condition_id="C3",
            lesson_id="lesson_07",
            question_type="multiple_choice",
            difficulty=2,
            bloom_level="understand",
        )
        compact = QuestionContent.model_validate(
            {
                "question_type": "multiple_choice",
                "stem": "Sự kiện nào diễn ra ngày 23 tháng 9 năm 1945?",
                "choices": [
                    {"label": "A", "text": "Nhân dân Nam Bộ bắt đầu kháng chiến."},
                    {"label": "B", "text": "Chiến dịch Điện Biên Phủ bắt đầu."},
                    {"label": "C", "text": "Hiệp định Giơ-ne-vơ được ký kết."},
                    {"label": "D", "text": "Cách mạng tháng Tám thành công."},
                ],
                "correct_answer": "A",
                "explanation": "Ngày 23 tháng 9 năm 1945, nhân dân Nam Bộ bắt đầu kháng chiến.",
            }
        )
        chunks = [
            Chunk(
                id="lesson_07-c1",
                text="Ngày 23 tháng 9 năm 1945, nhân dân Nam Bộ bắt đầu kháng chiến.",
                page=38,
            )
        ]
        first = AutoExamPipeline._finalize_question(request, compact, chunks, True, 1)
        second = AutoExamPipeline._finalize_question(request, compact, chunks, True, 1)

        self.assertEqual(first.question_id, second.question_id)
        self.assertEqual(first.difficulty, 2)
        self.assertEqual(first.bloom_level, "understand")
        self.assertEqual(first.lesson_id, "lesson_07")
        self.assertEqual(first.generation_condition, "C3")
        self.assertEqual(first.citations[0].chunk_id, "lesson_07-c1")
        self.assertEqual(first.citations[0].page, 38)
        self.assertIn(first.citations[0].quote, chunks[0].text)
        self.assertLessEqual(len(first.citations[0].quote), 300)

    def test_pipeline_rejects_model_question_type_mismatch(self):
        request = AutoExamRequest(
            condition_id="C0",
            lesson_id="lesson_01",
            question_type="multiple_choice",
        )
        essay = QuestionContent.model_validate(
            {
                "question_type": "short_essay",
                "stem": "Phân tích vai trò của tổ chức được đề cập trong bài học.",
                "choices": [],
                "correct_answer": "Trình bày đúng vai trò theo nội dung sách giáo khoa.",
                "explanation": "Đáp án cần chỉ ra vai trò và dẫn chứng lịch sử phù hợp.",
            }
        )
        with self.assertRaisesRegex(ValueError, "expected multiple_choice"):
            AutoExamPipeline._finalize_question(request, essay, [], False, 1)

    def test_non_rag_condition_gets_no_citations(self):
        request = AutoExamRequest(
            condition_id="C2",
            lesson_id="lesson_01",
            question_type="short_essay",
        )
        essay = QuestionContent.model_validate(
            {
                "question_type": "short_essay",
                "stem": "Phân tích vai trò của tổ chức được đề cập trong bài học.",
                "choices": [],
                "correct_answer": "Trình bày đúng vai trò theo nội dung sách giáo khoa.",
                "explanation": "Đáp án cần chỉ ra vai trò và dẫn chứng lịch sử phù hợp.",
            }
        )
        finalized = AutoExamPipeline._finalize_question(request, essay, [], False, 1)
        self.assertEqual(finalized.citations, [])


class RetrievalMetricTests(unittest.TestCase):
    def test_metrics_use_relevance_and_accept_list_input(self):
        result = compute_retrieval_metrics_for_entry(
            "query",
            ["irrelevant", "gold", "other"],
            ["irrelevant", "gold", "other"],
            {"gold"},
        )
        self.assertEqual(result["mrr"], 0.5)
        self.assertEqual(result["hit_rate_1"], 0.0)
        self.assertEqual(result["hit_rate_3"], 1.0)
        self.assertEqual(result["recall"], 1.0)

    def test_rrf_returns_normalized_scores(self):
        dense = [Chunk(id="a", text="a", score=0.7), Chunk(id="b", text="b", score=0.6)]
        keyword = [Chunk(id="b", text="b", score=0.8), Chunk(id="c", text="c", score=0.5)]
        result = VectorService._reciprocal_rank_fusion(dense, keyword, 3)
        self.assertEqual(result[0].id, "b")
        self.assertEqual(result[0].score, 1.0)


class ExperimentConfigTests(unittest.TestCase):
    def test_conditions_are_valid_ablation(self):
        config = load_experiment_config()
        self.assertEqual([item["id"] for item in config["conditions"]], ["C0", "C1", "C2", "C3"])
        self.assertTrue(get_condition("C3").use_rag)
        self.assertTrue(get_condition("C3").use_lora)

    def test_pipeline_uses_explicit_experiment_config(self):
        config = load_experiment_config()
        config["shared"]["seed"] = 123
        config["conditions"][2]["adapter_path"] = "artifacts/adapters/test-v2"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiments.json"
            path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            with patch("app.services.auto_exam_pipeline.VectorService"):
                pipeline = AutoExamPipeline(path)

        self.assertEqual(pipeline.experiment_config_path, path.resolve())
        self.assertEqual(pipeline.shared["seed"], 123)
        self.assertEqual(
            pipeline.conditions["C2"].adapter_path,
            "artifacts/adapters/test-v2",
        )


class HumanEvaluationTests(unittest.TestCase):
    def test_compact_aqg_target_preserves_content_and_excludes_metadata(self):
        source_question = {
            "question_id": "aqg-v1-lesson_01-001",
            "question_type": "multiple_choice",
            "stem": "Sự kiện nào được nêu trong ngữ liệu Lịch sử 12?",
            "choices": [
                {"label": "A", "text": "Phương án A"},
                {"label": "B", "text": "Phương án B"},
                {"label": "C", "text": "Phương án C"},
                {"label": "D", "text": "Phương án D"},
            ],
            "correct_answer": "C",
            "explanation": "Ngữ liệu được duyệt xác nhận phương án C là đúng.",
            "difficulty": 1,
            "bloom_level": "remember",
            "lesson_id": "lesson_01",
            "citations": [{"chunk_id": "c1", "page": 7, "quote": "Dẫn chứng"}],
            "generation_condition": "C3",
        }
        source = {
            "record_id": "aqg-v1-lesson_01-001",
            "instruction": "Sinh một câu hỏi trắc nghiệm.",
            "context": "Ngữ liệu đã duyệt.",
            "response": {"questions": [source_question]},
            "review_status": "teacher_approved",
            "split": "train",
            "approved_content_sha256": "approved-hash",
            "lesson_id": "lesson_01",
            "lesson_number": 1,
            "lesson_title": "Liên hợp quốc",
            "topic_id": "topic_01",
            "difficulty": 1,
            "bloom_level": "remember",
            "source_chunk_ids": ["c1"],
            "source_book_pages": [7],
            "reviewer_id": "teacher-1",
            "review_date": "2026-08-14",
        }

        compact, _ = compact_record(source, "train")
        target = compact["response"]["questions"][0]
        self.assertEqual(tuple(target), TARGET_FIELDS)
        for field in TARGET_FIELDS:
            self.assertEqual(target[field], source_question[field])
        for metadata in (
            "question_id", "difficulty", "bloom_level", "lesson_id",
            "citations", "generation_condition",
        ):
            self.assertNotIn(metadata, target)
        self.assertEqual(
            compact["provenance"]["source_question_id"],
            source_question["question_id"],
        )

    def test_compact_aqg_short_essay_keeps_empty_choices(self):
        source = {
            "record_id": "aqg-v1-lesson_01-002",
            "instruction": "Sinh một câu hỏi tự luận.",
            "context": "Ngữ liệu đã duyệt.",
            "response": {"questions": [{
                "question_id": "aqg-v1-lesson_01-002",
                "question_type": "short_essay",
                "stem": "Trình bày ý nghĩa của sự kiện được nêu trong ngữ liệu.",
                "choices": [],
                "correct_answer": "Ý chính tối thiểu cần có trong câu trả lời.",
                "explanation": "Bài làm cần sử dụng đúng dữ kiện trong ngữ liệu.",
                "difficulty": 2,
                "bloom_level": "understand",
                "lesson_id": "lesson_01",
                "citations": [{"chunk_id": "c1", "page": 7, "quote": "Dẫn chứng"}],
                "generation_condition": "C3",
            }]},
            "review_status": "teacher_approved",
            "split": "validation",
            "approved_content_sha256": "approved-hash",
            "lesson_id": "lesson_01",
            "lesson_number": 1,
            "lesson_title": "Liên hợp quốc",
            "topic_id": "topic_01",
            "difficulty": 2,
            "bloom_level": "understand",
            "source_chunk_ids": ["c1"],
            "source_book_pages": [7],
            "reviewer_id": "teacher-1",
            "review_date": "2026-08-14",
        }

        compact, _ = compact_record(source, "validation")
        self.assertEqual(compact["response"]["questions"][0]["choices"], [])

    def test_trainer_rejects_server_metadata_in_compact_target(self):
        payload = {
            "questions": [{
                "question_type": "short_essay",
                "stem": "Trình bày ý nghĩa của sự kiện được nêu trong ngữ liệu.",
                "choices": [],
                "correct_answer": "Nêu đúng các ý chính đã được giáo viên duyệt.",
                "explanation": "Câu trả lời phải bám sát ngữ liệu sách giáo khoa.",
                "lesson_id": "lesson_01",
            }]
        }
        with self.assertRaisesRegex(ValueError, "must contain exactly"):
            validate_compact_payload(payload)

    def test_aqg_splits_are_balanced_without_chunk_leakage(self):
        records = []
        for lesson_number in range(1, 7):
            lesson_id = f"lesson_{lesson_number:02d}"
            for chunk_number in range(10):
                chunk_id = f"{lesson_id}-chunk-{chunk_number:02d}"
                for item_number in range(10):
                    records.append(
                        {
                            "record_id": f"{chunk_id}-item-{item_number:02d}",
                            "lesson_id": lesson_id,
                            "source_chunk_ids": [chunk_id],
                            "question_type": "multiple_choice" if item_number < 7 else "short_essay",
                            "difficulty": item_number % 3 + 1,
                        }
                    )
        splits = assign_splits(records)
        self.assertEqual({name: len(rows) for name, rows in splits.items()}, {
            "train": 480,
            "validation": 60,
            "test": 60,
        })
        chunk_sets = {
            name: {row["source_chunk_ids"][0] for row in rows}
            for name, rows in splits.items()
        }
        self.assertFalse(chunk_sets["train"] & chunk_sets["validation"])
        self.assertFalse(chunk_sets["train"] & chunk_sets["test"])
        self.assertFalse(chunk_sets["validation"] & chunk_sets["test"])

    def test_aqg_annotation_targets_match_the_preregistered_distribution(self):
        plan = json.loads(
            (ROOT / "research" / "configs" / "aqg_annotation_plan.json").read_text(encoding="utf-8")
        )
        targets = build_targets(plan)
        self.assertEqual(len(targets), 600)
        self.assertEqual(
            {kind: sum(row["question_type"] == kind for row in targets) for kind in plan["target_distribution"]["question_type"]},
            plan["target_distribution"]["question_type"],
        )
        self.assertEqual(
            {level: sum(str(row["difficulty"]) == level for row in targets) for level in plan["target_distribution"]["difficulty"]},
            plan["target_distribution"]["difficulty"],
        )

    def test_applying_correction_preserves_audit_and_recomputes_dates(self):
        source = {
            "chunk_id": "test-chunk",
            "text": "Năm 194S diễn ra một sự kiện.",
            "source": "SGK",
            "pdf_page": 40,
            "book_page": 38,
            "book_id": "history12_kntt_2023_sample",
            "grade": 12,
            "series": "Kết nối tri thức với cuộc sống",
            "review_required": True,
            "review_reasons": ["suspicious_ocr_symbols"],
        }
        reviews = {
            "test-chunk": {
                "review_status": "corrected",
                "corrected_text": "Năm 1945 diễn ra một sự kiện.",
                "reviewer_id": "teacher-test",
                "review_date": "2026-08-02",
                "review_comment": "corrected year",
            }
        }
        reviewed, audit = apply_reviews([source], reviews, workbook_hash="abc123")
        self.assertEqual(len(reviewed), 1)
        self.assertFalse(reviewed[0]["review_required"])
        self.assertEqual(reviewed[0]["time_expressions"], ["1945"])
        self.assertEqual(reviewed[0]["ocr_review_status"], "corrected")
        self.assertTrue(audit[0]["included_in_reviewed_corpus"])

    def test_teacher_rubric_approval_rule(self):
        rubric = json.loads(
            (ROOT / "research" / "rubrics" / "teacher_rubric.json").read_text(encoding="utf-8")
        )
        row = {
            "question_id": "q1",
            "question_type": "multiple_choice",
            "factual_accuracy": "5",
            "source_support": "5",
            "unique_correct_answer": "5",
            "clarity": "4",
            "curriculum_alignment": "4",
            "cognitive_alignment": "4",
            "distractor_quality": "4",
            "pedagogical_language": "4",
            "difficulty_fit": "4",
            "factual_error_found": "false",
            "decision": "approve",
        }
        result = score_row(row, rubric)
        self.assertEqual(result["computed_decision"], "approve")
        self.assertGreaterEqual(result["weighted_score"], 4.2)

    def test_classical_item_helpers(self):
        self.assertGreater(correlation([0, 0, 1, 1], [1, 2, 3, 4]), 0.8)
        alpha = cronbach_alpha([[0, 0, 0], [0, 1, 1], [1, 1, 1], [1, 1, 1]])
        self.assertGreater(alpha, 0.0)


if __name__ == "__main__":
    unittest.main()
