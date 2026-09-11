from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.verify_adapter import (  # noqa: E402
    parse_explicit_indices,
    select_indices,
    summarize_results,
)


class AdapterBatchSelectionTests(unittest.TestCase):
    def test_evenly_spaced_default_is_deterministic(self):
        self.assertEqual(select_indices(60, count=5), [0, 15, 30, 44, 59])
        self.assertEqual(select_indices(3, count=10), [0, 1, 2])

    def test_single_and_explicit_indices_remain_supported(self):
        self.assertEqual(select_indices(60, index=4), [4])
        self.assertEqual(select_indices(60, indices="0, 4,11"), [0, 4, 11])
        with self.assertRaisesRegex(ValueError, "duplicates"):
            parse_explicit_indices("1,1")
        with self.assertRaisesRegex(ValueError, "invalid"):
            select_indices(3, indices="0,3")

    def test_summary_separates_json_schema_and_truncation(self):
        results = [
            {
                "valid_json": True,
                "valid_schema": True,
                "failure_stage": "none",
                "input_truncated": False,
                "latency_seconds": 1.0,
                "peak_vram_mb": 500,
            },
            {
                "valid_json": True,
                "valid_schema": False,
                "failure_stage": "schema_validation",
                "input_truncated": True,
                "latency_seconds": 3.0,
                "peak_vram_mb": 700,
            },
            {
                "valid_json": False,
                "valid_schema": False,
                "failure_stage": "json_parse",
                "input_truncated": False,
                "latency_seconds": 2.0,
                "peak_vram_mb": 600,
            },
        ]
        summary = summarize_results(results)
        self.assertEqual(summary["valid_json_rate"], 0.6667)
        self.assertEqual(summary["valid_schema_rate"], 0.3333)
        self.assertEqual(summary["input_truncation_rate"], 0.3333)
        self.assertEqual(summary["peak_vram_mb"], 700)
        self.assertFalse(summary["all_schema_valid"])


if __name__ == "__main__":
    unittest.main()
