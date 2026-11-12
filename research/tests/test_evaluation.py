import math
import unittest
from unittest.mock import patch

from evaluation.metrics.research_quality import corpus_bleu, rouge_l, evaluate_quality
from research.analyze_study import analyze
from backend.app.research.schemas import SourceChunk
from backend.app.research.retrieval import search


class QualityTests(unittest.TestCase):
    def test_identical_text_and_reordered_text(self):
        text = "Liên hợp quốc được thành lập năm 1945"
        self.assertAlmostEqual(corpus_bleu([(text, text)]), 1)
        self.assertAlmostEqual(rouge_l(text, text), 1)
        self.assertLess(rouge_l("a b c", "c b a"), 1)

    def test_bleu_penalizes_missing_ngrams_and_short_text(self):
        self.assertEqual(corpus_bleu([("a b c d", "x y z t")]), 0)
        self.assertEqual(corpus_bleu([("a", "a")]), 0)
        self.assertEqual(rouge_l("", ""), 0)

    def test_entities_and_unreviewed_factuality_are_separate(self):
        rows = [{"id":"1", "prediction":"a b c d", "reference":"a b c d",
                 "predicted_entities":[{"type":"YEAR", "text":"1945"},{"type":"PERSON", "text":"A"}],
                 "gold_entities":[{"type":"YEAR", "text":"1945"},{"type":"PERSON", "text":"B"}]}]
        result = evaluate_quality(rows)
        self.assertEqual(result["entity_f1"], .5)
        self.assertIsNone(result["hallucination_rate"])
        self.assertFalse(result["factuality_complete"])
        rows[0].update(historical_factuality="incorrect", reviewer_id="teacher", reviewed_at="2026-11-12")
        self.assertEqual(evaluate_quality(rows)["hallucination_rate"], 1)

    def test_factuality_requires_human_identity(self):
        row = {"id":"1", "prediction":"x", "reference":"y", "predicted_entities":[], "gold_entities":[], "historical_factuality":"correct"}
        with self.assertRaises(ValueError): evaluate_quality([row])

    def test_duplicate_quality_ids_rejected(self):
        with self.assertRaises(ValueError): evaluate_quality([{"id":"1"},{"id":"1"}])


class StudyTests(unittest.TestCase):
    def rows(self):
        return [{"participant_id":str(i), "group":g, "pre_test":pre, "post_test":post}
                for i,(g,pre,post) in enumerate([
                    ("experimental",5,7),("experimental",4,7),("experimental",6,8),
                    ("control",5,6),("control",4,4.5),("control",6,7)])]

    def test_gain_welch_and_group_summary(self):
        report = analyze(self.rows())
        self.assertEqual(report["groups"]["experimental"]["n"], 3)
        self.assertAlmostEqual(report["groups"]["experimental"]["mean_gain"], 7/3)
        self.assertTrue(math.isfinite(report["welch_gain"]["p_two_sided"]))

    def test_missing_or_duplicate_student_is_not_imputed(self):
        rows = self.rows(); rows[0]["pre_test"] = ""
        with self.assertRaises(ValueError): analyze(rows)
        rows = self.rows(); rows[0]["participant_id"] = rows[1]["participant_id"]
        with self.assertRaises(ValueError): analyze(rows)

    def test_zero_variance_not_reported_as_significant(self):
        rows = self.rows()
        for row in rows: row.update(pre_test=5, post_test=6)
        result = analyze(rows)
        self.assertIsNone(result["welch_gain"]["p_two_sided"])

    def test_small_group_and_nonfinite_score_rejected(self):
        with self.assertRaises(ValueError): analyze(self.rows()[:3])
        rows = self.rows(); rows[0]["post_test"] = float('nan')
        with self.assertRaises(ValueError): analyze(rows)


class HybridTests(unittest.TestCase):
    def test_dense_unavailable_is_explicit_not_keyword_disguised_as_dense(self):
        c = SourceChunk(id="c", text="Liên hợp quốc được thành lập năm 1945 nhằm duy trì hòa bình và an ninh quốc tế.",
                        source="SGK", source_sha256="0" * 64, book_page=7, pdf_page=9, lesson_id=1,
                        lesson_title="Liên hợp quốc", topic_id=1, provenance="review_pdf_extract")
        with patch('backend.app.research.retrieval.local_encoder', side_effect=OSError('missing model')):
            with self.assertRaisesRegex(RuntimeError, "embedding"):
                search([c], "Liên hợp quốc", mode="hybrid", approved_only=False)


if __name__ == '__main__': unittest.main()
