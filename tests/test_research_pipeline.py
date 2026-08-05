from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.experiment_config import get_condition, load_experiment_config
from app.services.auto_exam_pipeline import AutoExamPipeline
from app.services.history_corpus import chunk_page_text, load_book_config, lookup_scope
from app.services.question_schema import GeneratedQuestion
from app.services.trust_layer import Chunk, TrustLayer, extract_fact_markers
from app.services.vector_service import VectorService
from evaluation.metrics.factuality import evaluate_question_factuality
from evaluation.metrics.retrieval import compute_retrieval_metrics_for_entry
from research.analyze_student_items import correlation, cronbach_alpha
from research.apply_ocr_review import apply_reviews
from research.prepare_ocr_review import classify
from research.score_teacher_rubric import score_row


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


class HumanEvaluationTests(unittest.TestCase):
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
