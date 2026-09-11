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
    REPORT_SCHEMA_VERSION,
    assert_full_run_allowed,
    build_execution_contract,
    build_pilot_report,
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

    def test_failed_schema_rows_are_included_in_runtime_metrics(self):
        rows = [
            successful_row("C3", "p1"),
            {
                "condition": "C3",
                "status": "error",
                "failure_stage": "schema_validation",
                "latency_ms": 90000,
                "completion_tokens": 900,
                "peak_vram_mb": 1700,
                "input_truncated": True,
                "error": "ValidationError: duplicate choices",
            },
        ]
        metrics = summarize_condition(rows, "C3")
        self.assertEqual(metrics["telemetry_runs"], 2)
        self.assertEqual(metrics["latency_p95_ms"], 90000.0)
        self.assertEqual(metrics["peak_vram_mb"], 1700.0)
        self.assertEqual(metrics["input_truncation_rate"], 0.5)


class FullRunGuardTests(unittest.TestCase):
    def test_no_go_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pilot decision is not GO"):
            assert_full_run_allowed(
                {"decision": "no_go", "full_experiment_allowed": False},
                MANIFEST_PATH,
                REQUESTS_PATH,
            )

    @staticmethod
    def _guard_fixture(folder: Path):
        manifest_path = folder / "pilot.json"
        requests_path = folder / "requests.jsonl"
        config_path = folder / "experiments.json"
        design_path = folder / "design.json"
        code_path = folder / "runtime.py"
        adapter_path = folder / "adapter"
        adapter_path.mkdir()

        manifest_path.write_text('{"pilot_id":"test"}', encoding="utf-8")
        requests_path.write_text('{"prompt_id":"p1"}\n', encoding="utf-8")
        design_path.write_text('{"selected_prompt_ids":["p1"]}', encoding="utf-8")
        code_path.write_text("PROMPT = 'v1'\n", encoding="utf-8")
        (adapter_path / "adapter_config.json").write_text("{}", encoding="utf-8")
        (adapter_path / "adapter_model.safetensors").write_bytes(b"adapter-v1")
        (adapter_path / "training_manifest.json").write_text("{}", encoding="utf-8")
        (adapter_path / "tokenizer.json").write_text("{}", encoding="utf-8")
        (adapter_path / "chat_template.jinja").write_text("template-v1", encoding="utf-8")
        config_path.write_text(
            json.dumps({
                "conditions": [{
                    "id": "C2",
                    "use_lora": True,
                    "adapter_path": str(adapter_path),
                }]
            }),
            encoding="utf-8",
        )
        code_files = {"test_runtime": code_path}
        contract = build_execution_contract(
            manifest_path=manifest_path,
            requests_path=requests_path,
            experiment_config_path=config_path,
            eval_design_path=design_path,
            code_files=code_files,
        )
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "decision": "go",
            "full_experiment_allowed": True,
            "execution_contract": contract,
        }
        paths = {
            "configuration": config_path,
            "manifest": manifest_path,
            "data": requests_path,
            "design": design_path,
            "adapter": adapter_path / "adapter_model.safetensors",
            "code": code_path,
        }
        arguments = (
            manifest_path,
            requests_path,
            config_path,
            design_path,
        )
        return report, paths, arguments, code_files

    def test_every_contract_group_invalidates_go_report_when_changed(self):
        for target in ("configuration", "manifest", "data", "design", "adapter", "code"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                report, paths, arguments, code_files = self._guard_fixture(Path(directory))
                path = paths[target]
                if target == "configuration":
                    config = json.loads(path.read_text(encoding="utf-8"))
                    config["changed_after_pilot"] = True
                    path.write_text(json.dumps(config), encoding="utf-8")
                else:
                    with path.open("ab") as stream:
                        stream.write(b"\nchanged")
                with self.assertRaisesRegex(ValueError, "execution contract changed"):
                    assert_full_run_allowed(
                        report,
                        *arguments,
                        code_files=code_files,
                    )

    def test_stale_go_report_schema_is_rejected(self):
        report = {
            "schema_version": "2.0",
            "decision": "go",
            "full_experiment_allowed": True,
        }
        with self.assertRaisesRegex(ValueError, "report schema is stale"):
            assert_full_run_allowed(report, MANIFEST_PATH, REQUESTS_PATH)

    def test_incomplete_go_contract_is_rejected(self):
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "decision": "go",
            "full_experiment_allowed": True,
            "execution_contract": {"complete": False},
        }
        with self.assertRaisesRegex(ValueError, "execution contract is incomplete"):
            assert_full_run_allowed(report, MANIFEST_PATH, REQUESTS_PATH)

    def test_report_fails_closed_when_required_code_file_is_missing(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        rows = [
            successful_row(condition, prompt_id)
            for condition in manifest["required_conditions"]
            for prompt_id in manifest["selection"]["selected_prompt_ids"]
        ]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config_path = folder / "experiments.json"
            config_path.write_text('{"conditions":[]}', encoding="utf-8")
            report = build_pilot_report(
                rows,
                manifest,
                manifest_path=MANIFEST_PATH,
                requests_path=REQUESTS_PATH,
                experiment_config_path=config_path,
                eval_design_path=EVAL_DESIGN_PATH,
                code_files={"missing_runtime": folder / "missing.py"},
            )
        self.assertEqual(report["decision"], "no_go")
        self.assertFalse(report["full_experiment_allowed"])
        self.assertFalse(report["execution_contract"]["complete"])
        self.assertTrue(any(
            item["metric"] == "execution_contract_complete"
            for item in report["gate_failures"]
        ))

    def test_default_contract_names_all_runtime_implementations(self):
        contract = build_execution_contract()
        logical_names = {
            entry["logical_name"]
            for entry in contract["files"]["code"].values()
        }
        self.assertTrue({
            "shared_aqg_prompt",
            "runtime_prompt_pipeline",
            "model_provider",
            "question_schema",
            "pilot_evaluator_gate",
            "experiment_runner",
        } <= logical_names)
        if contract["complete"]:
            adapter_names = {Path(path).name for path in contract["files"]["adapter"]}
            self.assertTrue({
                "adapter_model.safetensors",
                "adapter_config.json",
                "training_manifest.json",
                "tokenizer.json",
                "chat_template.jinja",
            } <= adapter_names)
        else:
            missing_paths = {
                item["path"] for item in contract["missing_required_files"]
            }
            self.assertTrue(any("history12_lora_v2_1" in path for path in missing_paths))


if __name__ == "__main__":
    unittest.main()
