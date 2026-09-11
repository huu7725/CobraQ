"""Load one CobraQ adapter and verify a deterministic held-out batch on GPU."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
BACKEND_DIR = str(ROOT / "backend")
while SCRIPT_DIR in sys.path:
    sys.path.remove(SCRIPT_DIR)
for path in (str(ROOT), BACKEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from research.train_lora import format_prompt, load_jsonl  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter",
        type=Path,
        default=ROOT / "artifacts" / "adapters" / "history12_lora_v2_1",
    )
    parser.add_argument(
        "--test",
        type=Path,
        default=ROOT / "data" / "research" / "aqg_v2" / "approved" / "test.jsonl",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--index", type=int, help="Backward-compatible single record index")
    selection.add_argument(
        "--indices",
        help="Comma-separated explicit record indices, for example 0,4,11",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Deterministic evenly spaced batch size when no explicit index is supplied",
    )
    parser.add_argument("--max-input-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=1280)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit with code 2 unless every selected output passes strict runtime schema",
    )
    return parser.parse_args()


def parse_explicit_indices(value: str) -> list[int]:
    try:
        indices = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise ValueError("--indices must be comma-separated integers") from error
    if not indices:
        raise ValueError("--indices must contain at least one index")
    if len(indices) != len(set(indices)):
        raise ValueError("--indices must not contain duplicates")
    return indices


def select_indices(
    record_count: int,
    *,
    index: int | None = None,
    indices: str | None = None,
    count: int = 10,
) -> list[int]:
    if record_count < 1:
        raise ValueError("Held-out test set is empty")
    if index is not None:
        selected = [index]
    elif indices is not None:
        selected = parse_explicit_indices(indices)
    else:
        if count < 1:
            raise ValueError("--count must be at least 1")
        size = min(count, record_count)
        if size == 1:
            selected = [0]
        else:
            selected = [
                round(position * (record_count - 1) / (size - 1))
                for position in range(size)
            ]
    invalid = [value for value in selected if value < 0 or value >= record_count]
    if invalid:
        raise ValueError(
            f"Held-out indices must be in [0, {record_count - 1}]; invalid={invalid}"
        )
    return selected


def validate_generated_text(generated_text: str) -> dict[str, Any]:
    from app.services.question_schema import ModelGenerationEnvelope

    try:
        parsed_output = json.loads(generated_text)
        valid_json = True
        parse_error = None
    except json.JSONDecodeError as error:
        parsed_output = None
        valid_json = False
        parse_error = str(error)

    valid_schema = False
    schema_error = None
    if valid_json:
        try:
            ModelGenerationEnvelope.model_validate(parsed_output)
            valid_schema = True
        except ValueError as error:
            schema_error = str(error)
    failure_stage = "none" if valid_schema else (
        "schema_validation" if valid_json else "json_parse"
    )
    return {
        "valid_json": valid_json,
        "parse_error": parse_error,
        "valid_schema": valid_schema,
        "schema_error": schema_error,
        "failure_stage": failure_stage,
        "parsed_output": parsed_output,
    }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[position], 3)


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    valid_json = sum(bool(item["valid_json"]) for item in results)
    valid_schema = sum(bool(item["valid_schema"]) for item in results)
    latencies = [float(item["latency_seconds"]) for item in results]
    return {
        "samples": total,
        "valid_json": valid_json,
        "valid_json_rate": round(valid_json / total, 4) if total else 0.0,
        "valid_schema": valid_schema,
        "valid_schema_rate": round(valid_schema / total, 4) if total else 0.0,
        "all_schema_valid": bool(total) and valid_schema == total,
        "failure_stage_counts": dict(sorted(Counter(
            str(item["failure_stage"]) for item in results
        ).items())),
        "input_truncation_rate": (
            round(sum(bool(item["input_truncated"]) for item in results) / total, 4)
            if total else 0.0
        ),
        "latency_p50_seconds": percentile(latencies, 0.50),
        "latency_p95_seconds": percentile(latencies, 0.95),
        "mean_latency_seconds": round(statistics.fmean(latencies), 3) if latencies else None,
        "peak_vram_mb": round(max(
            (float(item["peak_vram_mb"]) for item in results), default=0.0
        ), 2),
        "scope_note": (
            "This verifies JSON/runtime schema and inference telemetry only; "
            "it does not approve historical factuality or pedagogy."
        ),
    }


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        import torch
        from peft import PeftConfig, PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as error:
        raise SystemExit(f"Missing inference dependencies: {error}")

    if not torch.cuda.is_available():
        raise SystemExit("A CUDA GPU is required for the 4-bit adapter verification")

    records = load_jsonl(args.test)
    selected_indices = select_indices(
        len(records), index=args.index, indices=args.indices, count=args.count
    )
    adapter_path = args.adapter.resolve()
    peft_config = PeftConfig.from_pretrained(adapter_path)
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        peft_config.base_model_name_or_path,
        quantization_config=quantization_config,
        dtype=compute_dtype,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    context_window = int(getattr(model.config, "max_position_embeddings", 2048))
    input_budget = context_window - args.max_new_tokens
    if input_budget < 1:
        raise ValueError(
            f"--max-new-tokens={args.max_new_tokens} leaves no room in the "
            f"{context_window}-token context window"
        )
    effective_max_input = min(args.max_input_length, input_budget)

    results: list[dict[str, Any]] = []
    for index in selected_indices:
        record = records[index]
        prompt = format_prompt(record, tokenizer)
        original_prompt_tokens = len(
            tokenizer(prompt, add_special_tokens=False)["input_ids"]
        )
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=effective_max_input,
            add_special_tokens=False,
        ).to(model.device)
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
            )
        torch.cuda.synchronize()
        latency_seconds = time.perf_counter() - started
        generated_text = tokenizer.decode(
            output_ids[0, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        ).strip()
        validation = validate_generated_text(generated_text)
        results.append({
            "test_index": index,
            "record_id": record.get("sample_id") or record.get("record_id"),
            "question_type": record["response"]["questions"][0]["question_type"],
            "prompt_tokens": int(inputs["input_ids"].shape[1]),
            "original_prompt_tokens": original_prompt_tokens,
            "input_truncated": int(inputs["input_ids"].shape[1]) < original_prompt_tokens,
            "generated_tokens": int(output_ids.shape[1] - inputs["input_ids"].shape[1]),
            "latency_seconds": round(latency_seconds, 3),
            "peak_vram_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
            "generated_text": generated_text,
            "expected_response": record["response"],
            **validation,
        })

    report = {
        "schema_version": "2.0",
        "adapter": str(adapter_path),
        "base_model": peft_config.base_model_name_or_path,
        "test_file": str(args.test.resolve()),
        "selection": {
            "method": "explicit" if args.index is not None or args.indices else "evenly_spaced",
            "indices": selected_indices,
        },
        "context_window": context_window,
        "max_input_length": effective_max_input,
        "max_new_tokens": args.max_new_tokens,
        "summary": summarize_results(results),
        "results": results,
    }
    output_path = args.output or (adapter_path / "verification_batch_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_invalid and not report["summary"]["all_schema_valid"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
