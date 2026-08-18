"""Evaluate the preregistered 10x4 pilot and decide whether a full run is allowed."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import unicodedata
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics.factuality import evaluate_question_factuality  # noqa: E402


DEFAULT_MANIFEST = ROOT / "research" / "configs" / "pilot_v2.json"
DEFAULT_EXPERIMENT_CONFIG = ROOT / "research" / "configs" / "experiments.json"
DEFAULT_EVAL_DESIGN = ROOT / "research" / "configs" / "eval_design_v2.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(float(ordered[index]), 4)


def select_pilot_requests(
    requests: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    """Select the frozen pilot IDs in manifest order and validate its strata."""
    selected_ids = manifest["selection"]["selected_prompt_ids"]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Pilot manifest contains duplicate prompt IDs")
    if len(selected_ids) != int(manifest["sample_size_per_condition"]):
        raise ValueError("Pilot manifest size does not match sample_size_per_condition")
    by_id = {str(row.get("prompt_id")): row for row in requests}
    missing = [prompt_id for prompt_id in selected_ids if prompt_id not in by_id]
    if missing:
        raise ValueError(f"Pilot prompt IDs missing from request set: {missing}")
    selected = [by_id[prompt_id] for prompt_id in selected_ids]

    targets = manifest["selection"]["target_distribution"]
    for field in ("topic_id", "difficulty", "question_type"):
        actual = Counter(str(row[field]) for row in selected)
        expected = Counter({str(key): int(value) for key, value in targets[field].items()})
        if actual != expected:
            raise ValueError(
                f"Pilot {field} distribution changed: actual={dict(actual)} expected={dict(expected)}"
            )
    distinct_lessons = len({row["lesson_id"] for row in selected})
    if distinct_lessons != int(targets["distinct_lessons"]):
        raise ValueError(
            f"Pilot distinct lesson count changed: {distinct_lessons} != {targets['distinct_lessons']}"
        )
    return selected


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join(re.findall(r"[0-9a-z]+", value))


def _failure_stage(row: dict[str, Any]) -> str:
    if row.get("status") == "ok":
        return "none"
    message = str(row.get("error") or "")
    if "JSONDecodeError" in message:
        return "json_parse"
    if "ValidationError" in message or "ValueError" in message:
        return "schema_validation"
    return "runtime"


def _jaccard(left: str, right: str) -> float:
    left_tokens = set(_fold(left).split())
    right_tokens = set(_fold(right).split())
    if not left_tokens and not right_tokens:
        return 1.0
    return len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)


def evaluate_mcq_structure(question: dict[str, Any]) -> dict[str, Any]:
    """Check distractor structure only; semantic plausibility remains a human task."""
    choices = question.get("choices") or []
    labels = [str(item.get("label") or "") for item in choices]
    texts = [str(item.get("text") or "") for item in choices]
    normalized = [_fold(text) for text in texts]
    pairs = [
        (left_index, right_index, _jaccard(texts[left_index], texts[right_index]))
        for left_index in range(len(texts))
        for right_index in range(left_index + 1, len(texts))
    ]
    exact_duplicate = len(set(normalized)) != len(normalized)
    contained_pair = False
    for left, right, _ in pairs:
        shorter, longer = sorted((normalized[left], normalized[right]), key=len)
        if len(shorter) >= 20 and shorter in longer:
            contained_pair = True
            break
    high_overlap_pair = any(score >= 0.8 for _, _, score in pairs)
    contract_valid = (
        len(choices) == 4
        and set(labels) == {"A", "B", "C", "D"}
        and question.get("correct_answer") in labels
        and all(normalized)
    )
    return {
        "contract_valid": contract_valid,
        "exact_duplicate": exact_duplicate,
        "contained_pair": contained_pair,
        "high_overlap_pair": high_overlap_pair,
        "structural_valid": (
            contract_valid and not exact_duplicate and not contained_pair and not high_overlap_pair
        ),
        "max_pairwise_token_jaccard": round(max((score for _, _, score in pairs), default=0.0), 4),
    }


def _citation_valid(question: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> bool:
    citations = question.get("citations") or []
    if not citations:
        return False
    for citation in citations:
        chunk = chunks.get(str(citation.get("chunk_id") or ""))
        if not chunk or int(citation.get("page") or 0) != int(chunk.get("page") or 0):
            return False
        quote = _fold(str(citation.get("quote") or ""))
        evidence = _fold(str(chunk.get("text") or ""))
        if not quote or quote not in evidence:
            return False
    return True


def summarize_condition(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    stages = [_failure_stage(row) for row in rows]
    successful = [row for row in rows if row.get("status") == "ok"]
    questions = [question for row in successful for question in row.get("questions", [])]
    run_count = len(rows)
    parsed_count = sum(stage in {"none", "schema_validation"} for stage in stages)
    latencies = [float(row["latency_ms"]) for row in successful if row.get("latency_ms") is not None]
    vram = [float(row["peak_vram_mb"]) for row in successful if row.get("peak_vram_mb") is not None]
    truncation = [bool(row.get("input_truncated")) for row in successful]
    throughputs = [
        float(row.get("completion_tokens", 0)) / (float(row["latency_ms"]) / 1000)
        for row in successful
        if float(row.get("latency_ms") or 0) > 0
    ]

    factuality_rows = []
    citation_checks = []
    mcq_checks = []
    for row in successful:
        chunks = {str(item["chunk_id"]): item for item in row.get("retrieved_chunks", [])}
        for question in row.get("questions", []):
            evaluation_question = dict(question)
            evaluation_question.pop("auto_evaluation", None)
            if condition in {"C0", "C2"}:
                evaluation_question["citations"] = [
                    {
                        "chunk_id": chunk_id,
                        "page": item.get("page", 0),
                        "quote": item.get("text", ""),
                    }
                    for chunk_id, item in chunks.items()
                ]
            factuality_rows.append(evaluate_question_factuality(evaluation_question, chunks))
            if condition in {"C1", "C3"}:
                citation_checks.append(_citation_valid(question, chunks))
            if question.get("question_type") == "multiple_choice":
                mcq_checks.append(evaluate_mcq_structure(question))

    auto_evaluations = [
        question.get("auto_evaluation") or {}
        for question in questions
        if question.get("auto_evaluation") is not None
    ]
    factual_errors = [bool(item.get("factual_error")) for item in factuality_rows]
    fact_support = [float(item.get("fact_support_rate", 0.0)) for item in factuality_rows]
    unsupported_time = [bool(item.get("unsupported_facts")) for item in factuality_rows]

    def rate(values: list[bool]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "runs": run_count,
        "successful_runs": len(successful),
        "failure_stage_counts": dict(sorted(Counter(stages).items())),
        "json_valid_rate": round(parsed_count / run_count, 4) if run_count else 0.0,
        "schema_valid_rate": round(len(successful) / run_count, 4) if run_count else 0.0,
        "runtime_error_rate": round(stages.count("runtime") / run_count, 4) if run_count else 0.0,
        "questions": len(questions),
        "auto_verified_rate": rate([
            item.get("status") == "auto_verified" for item in auto_evaluations
        ]),
        "automatic_factual_error_rate": rate(factual_errors),
        "mean_fact_support_rate": round(statistics.fmean(fact_support), 4) if fact_support else None,
        "unsupported_time_fact_rate": rate(unsupported_time),
        "citation_valid_rate": rate(citation_checks),
        "citation_questions": len(citation_checks),
        "mcq_questions": len(mcq_checks),
        "distractor_contract_valid_rate": rate([
            item["contract_valid"] for item in mcq_checks
        ]),
        "distractor_structural_valid_rate": rate([
            item["structural_valid"] for item in mcq_checks
        ]),
        "high_overlap_choice_rate": rate([
            item["high_overlap_pair"] for item in mcq_checks
        ]),
        "input_truncation_rate": rate(truncation),
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "peak_vram_mb": round(max(vram), 4) if vram else None,
        "mean_completion_tokens_per_second": (
            round(statistics.fmean(throughputs), 4) if throughputs else None
        ),
    }


def evaluate_gate(
    condition_metrics: dict[str, dict[str, Any]], manifest: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    gate = manifest["gate"]

    def require(
        condition: str, metric: str, operator: str, threshold: float, value: Any
    ) -> None:
        passed = value is not None and (
            (operator == ">=" and float(value) >= threshold)
            or (operator == "<=" and float(value) <= threshold)
            or (operator == "==" and float(value) == threshold)
        )
        if not passed:
            failures.append({
                "condition": condition,
                "metric": metric,
                "observed": value,
                "operator": operator,
                "threshold": threshold,
            })

    common = gate["all_conditions"]
    for condition in manifest["required_conditions"]:
        metrics = condition_metrics.get(condition, {})
        require(condition, "runs", "==", float(common["required_runs"]), metrics.get("runs"))
        require(
            condition,
            "runtime_error_rate",
            "<=",
            float(common["max_runtime_error_rate"]),
            metrics.get("runtime_error_rate"),
        )

    for condition in manifest["required_conditions"]:
        for key, threshold in gate[condition].items():
            if key == "require_peak_vram_measurement":
                if threshold and not (condition_metrics.get(condition, {}).get("peak_vram_mb") or 0) > 0:
                    failures.append({
                        "condition": condition,
                        "metric": "peak_vram_measurement_present",
                        "observed": False,
                        "operator": "==",
                        "threshold": True,
                    })
                continue
            if key.startswith("min_"):
                metric = key[4:]
                operator = ">="
            elif key.startswith("max_"):
                metric = key[4:]
                operator = "<="
            else:
                raise ValueError(f"Unknown gate threshold: {key}")
            require(
                condition,
                metric,
                operator,
                float(threshold),
                condition_metrics.get(condition, {}).get(metric),
            )

    rag_gate = gate["rag_conditions"]
    for condition in rag_gate["conditions"]:
        metrics = condition_metrics.get(condition, {})
        require(
            condition,
            "citation_questions",
            ">=",
            float(rag_gate["min_valid_questions"]),
            metrics.get("citation_questions"),
        )
        require(
            condition,
            "citation_valid_rate",
            ">=",
            float(rag_gate["min_citation_valid_rate"]),
            metrics.get("citation_valid_rate"),
        )
    return ("go" if not failures else "no_go"), failures


def artifact_fingerprint(
    experiment_config_path: Path = DEFAULT_EXPERIMENT_CONFIG,
) -> dict[str, Any]:
    config = json.loads(experiment_config_path.read_text(encoding="utf-8"))
    adapter_files: dict[str, str | None] = {}
    seen_paths = set()
    for condition in config.get("conditions", []):
        adapter = condition.get("adapter_path")
        if not condition.get("use_lora") or not adapter or adapter in seen_paths:
            continue
        seen_paths.add(adapter)
        adapter_path = Path(adapter)
        if not adapter_path.is_absolute():
            adapter_path = ROOT / adapter_path
        for name in ("adapter_model.safetensors", "adapter_config.json", "training_manifest.json"):
            path = adapter_path / name
            key = str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)
            adapter_files[key] = sha256_file(path) if path.is_file() else None
    return {
        "experiment_config_sha256": sha256_file(experiment_config_path),
        "adapter_files_sha256": dict(sorted(adapter_files.items())),
    }


def build_pilot_report(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    requests_path: Path | None = None,
    experiment_config_path: Path = DEFAULT_EXPERIMENT_CONFIG,
    eval_design_path: Path = DEFAULT_EVAL_DESIGN,
) -> dict[str, Any]:
    conditions = manifest["required_conditions"]
    selected_ids = manifest["selection"]["selected_prompt_ids"]
    condition_metrics = {
        condition: summarize_condition(
            [row for row in rows if row.get("condition") == condition], condition
        )
        for condition in conditions
    }
    decision, failures = evaluate_gate(condition_metrics, manifest)
    observed_ids = {
        condition: sorted(
            str(row.get("prompt_id") or "")
            for row in rows
            if row.get("condition") == condition
        )
        for condition in conditions
    }
    expected_ids = sorted(selected_ids)
    for condition, ids in observed_ids.items():
        if ids != expected_ids:
            decision = "no_go"
            failures.append({
                "condition": condition,
                "metric": "pilot_prompt_ids_match_manifest",
                "observed": ids,
                "operator": "==",
                "threshold": expected_ids,
            })
    fingerprint = artifact_fingerprint(experiment_config_path)
    return {
        "schema_version": "2.0",
        "pilot_id": manifest["pilot_id"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "full_experiment_allowed": decision == "go",
        "gate_failures": failures,
        "sample_size_per_condition": manifest["sample_size_per_condition"],
        "selected_prompt_ids": selected_ids,
        "conditions": condition_metrics,
        "fingerprint": {
            "pilot_manifest_sha256": sha256_file(manifest_path),
            "requests_sha256": sha256_file(requests_path) if requests_path else None,
            "eval_design_sha256": sha256_file(eval_design_path),
            **fingerprint,
        },
        "metric_scope": {
            "automatic_factuality": "time markers plus citation/quote support; teacher review still required",
            "distractor_quality": "structural checks only; plausibility requires blinded teacher review",
        },
    }


def assert_full_run_allowed(
    report: dict[str, Any],
    manifest_path: Path,
    requests_path: Path,
    experiment_config_path: Path = DEFAULT_EXPERIMENT_CONFIG,
    eval_design_path: Path = DEFAULT_EVAL_DESIGN,
) -> None:
    if report.get("decision") != "go" or not report.get("full_experiment_allowed"):
        raise ValueError("Full experiment is blocked because the pilot decision is not GO")
    current = {
        "pilot_manifest_sha256": sha256_file(manifest_path),
        "requests_sha256": sha256_file(requests_path),
        "eval_design_sha256": sha256_file(eval_design_path),
        **artifact_fingerprint(experiment_config_path),
    }
    recorded = report.get("fingerprint") or {}
    mismatches = [key for key, value in current.items() if recorded.get(key) != value]
    if mismatches:
        raise ValueError(
            "Full experiment is blocked because pilot artifacts changed: " + ", ".join(mismatches)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--requests", type=Path)
    parser.add_argument("--experiment-config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG)
    parser.add_argument("--eval-design", type=Path, default=DEFAULT_EVAL_DESIGN)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = load_jsonl(args.results)
    report = build_pilot_report(
        rows,
        manifest,
        manifest_path=args.manifest,
        requests_path=args.requests,
        experiment_config_path=args.experiment_config,
        eval_design_path=args.eval_design,
    )
    output = args.output or args.results.with_suffix(".pilot_report.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
