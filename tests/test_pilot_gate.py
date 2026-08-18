from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.evaluate_pilot import (  # noqa: E402
    artifact_fingerprint,
    assert_full_run_allowed,
    evaluate_gate,
    select_pilot_requests,
    summarize_condition,
)


MANIFEST_PATH = ROOT / "research" / "configs" / "pilot_v2.json"
REQUESTS_PATH = ROOT / "research" / "datasets" / "eval_requests.jsonl"
EVAL_DESIGN_PATH = ROOT / "research" / "configs" / "eval_design_v2.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def question(condition: str) -> dict:
    citations = []
    if condition in {"C1", "C3"}:
        citations = [{
            "chunk_id": "chunk-1",
            "page": 7,
            "quote": "Năm 1945, sự kiện lịch sử diễn ra.",
        }]
    return {
        "question_type": "multiple_choice",
        "stem": "Theo ngữ liệu, nhận định nào sau đây phản ánh đúng sự kiện năm 1945?",
        "choices": [
            {"label": "A", "text": "Sự kiện lịch sử diễn ra tại Việt Nam."},
            {"label": "B", "text": "ASEAN chính thức được thành lập."},
            {"label": "C", "text": "Liên minh châu Âu mở rộng thành viên."},
            {"label": "D", "text": "Chiến tranh lạnh hoàn toàn chấm dứt."},
        ],
        "correct_answer": "A",
        "explanation": "Năm 1945, sự kiện lịch sử diễn ra tại Việt Nam.",
        "difficulty": 1,
        "bloom_level": "remember",
        "lesson_id": "lesson_01",
        "generation_condition": condition,
        "citations": citations,
        "auto_evaluation": {
            "status": "auto_verified",
            "fact_support_rate": 1.0,
            "unsupported_facts": [],
            "hallucination_detected": False,
            "citation_valid": True,
        },
    }


def successful_row(condition: str, prompt_id: str) -> dict:
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "status": "ok",
        "latency_ms": 50000,
        "completion_tokens": 500,
        "peak_vram_mb": 1200,
        "input_truncated": False,
        "retrieved_chunks": [{
            "chunk_id": "chunk-1",
            "page": 7,
            "text": "Năm 1945, sự kiện lịch sử diễn ra tại Việt Nam.",
        }],
        "questions": [question(condition)],
    }


class PilotSelectionTests(unittest.TestCase):
    def test_full_request_set_covers_all_lessons_and_registered_distribution(self):
        requests = load_jsonl(REQUESTS_PATH)
        self.assertEqual(len(requests), 40)
        self.assertEqual(len({row["lesson_id"] for row in requests}), 17)
        self.assertEqual(
            {level: sum(row["difficulty"] == level for row in requests) for level in (1, 2, 3)},
            {1: 14, 2: 13, 3: 13},
        )
        self.assertEqual(
            {
                kind: sum(row["question_type"] == kind for row in requests)
                for kind in ("multiple_choice", "short_essay")
            },
            {"multiple_choice": 27, "short_essay": 13},
        )

    def test_frozen_pilot_covers_registered_strata(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        selected = select_pilot_requests(load_jsonl(REQUESTS_PATH), manifest)
        self.assertEqual(len(selected), 10)
        self.assertEqual(len({row["lesson_id"] for row in selected}), 10)
        self.assertEqual({row["topic_id"] for row in selected}, {
            "topic_01", "topic_02", "topic_03", "topic_04", "topic_05", "topic_06"
        })


class PilotMetricTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.prompt_ids = self.manifest["selection"]["selected_prompt_ids"]

    def test_valid_10x4_pilot_passes_gate(self):
        metrics = {
            condition: summarize_condition(
                [successful_row(condition, prompt_id) for prompt_id in self.prompt_ids],
                condition,
            )
            for condition in self.manifest["required_conditions"]
        }
        decision, failures = evaluate_gate(metrics, self.manifest)
        self.assertEqual(decision, "go")
        self.assertEqual(failures, [])
        self.assertEqual(metrics["C3"]["citation_valid_rate"], 1.0)
        self.assertEqual(metrics["C3"]["distractor_structural_valid_rate"], 1.0)

    def test_schema_failures_keep_full_experiment_blocked(self):
        metrics = {}
        for condition in self.manifest["required_conditions"]:
            rows = [successful_row(condition, prompt_id) for prompt_id in self.prompt_ids]
            if condition == "C3":
                rows[:2] = [{
                    "condition": condition,
                    "prompt_id": self.prompt_ids[index],
                    "status": "error",
                    "error_type": "ModelBackendError",
                    "error": "ValidationError: invalid choices",
                } for index in range(2)]
            metrics[condition] = summarize_condition(rows, condition)
        decision, failures = evaluate_gate(metrics, self.manifest)
        self.assertEqual(decision, "no_go")
        self.assertTrue(any(
            item["condition"] == "C3" and item["metric"] == "schema_valid_rate"
            for item in failures
        ))

    def test_json_and_schema_failures_are_reported_separately(self):
        rows = [
            {
                "condition": "C3",
                "status": "error",
                "error": "JSONDecodeError: Expecting value",
            },
            {
                "condition": "C3",
                "status": "error",
                "error": "ValidationError: duplicate choices",
            },
            successful_row("C3", "lesson_01-d1"),
        ]
        metrics = summarize_condition(rows, "C3")
        self.assertEqual(metrics["json_valid_rate"], 0.6667)
        self.assertEqual(metrics["schema_valid_rate"], 0.3333)
        self.assertEqual(metrics["failure_stage_counts"]["json_parse"], 1)
        self.assertEqual(metrics["failure_stage_counts"]["schema_validation"], 1)


class FullRunGuardTests(unittest.TestCase):
    def test_no_go_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pilot decision is not GO"):
            assert_full_run_allowed(
                {"decision": "no_go", "full_experiment_allowed": False},
                MANIFEST_PATH,
                REQUESTS_PATH,
            )

    def test_changed_request_file_invalidates_go_report(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest_path = folder / "pilot.json"
            requests_path = folder / "requests.jsonl"
            config_path = folder / "experiments.json"
            manifest_path.write_text("{}", encoding="utf-8")
            requests_path.write_text('{"prompt_id":"p1"}\n', encoding="utf-8")
            config_path.write_text('{"conditions":[]}', encoding="utf-8")
            from research.evaluate_pilot import sha256_file

            report = {
                "decision": "go",
                "full_experiment_allowed": True,
                "fingerprint": {
                    "pilot_manifest_sha256": sha256_file(manifest_path),
                    "requests_sha256": sha256_file(requests_path),
                    "eval_design_sha256": sha256_file(EVAL_DESIGN_PATH),
                    **artifact_fingerprint(config_path),
                },
            }
            requests_path.write_text('{"prompt_id":"p2"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requests_sha256"):
                assert_full_run_allowed(
                    report, manifest_path, requests_path, config_path, EVAL_DESIGN_PATH
                )


if __name__ == "__main__":
    unittest.main()
