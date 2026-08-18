"""Load a trained CobraQ adapter and run one held-out generation check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
BACKEND_DIR = str(ROOT / "backend")
while SCRIPT_DIR in sys.path:
    sys.path.remove(SCRIPT_DIR)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.question_schema import ModelGenerationEnvelope
from research.train_lora import format_prompt, load_jsonl


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter",
        type=Path,
        default=ROOT / "artifacts" / "adapters" / "history12_lora_v2",
    )
    parser.add_argument(
        "--test",
        type=Path,
        default=ROOT / "data" / "research" / "aqg_v2" / "approved" / "test.jsonl",
    )
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--max-input-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=1280)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


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
    if args.index < 0 or args.index >= len(records):
        raise ValueError(f"--index must be in [0, {len(records) - 1}]")
    record = records[args.index]

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

    prompt = format_prompt(record)
    original_prompt_tokens = len(tokenizer(prompt, add_special_tokens=True)["input_ids"])
    context_window = int(getattr(model.config, "max_position_embeddings", 2048))
    input_budget = context_window - args.max_new_tokens
    if input_budget < 1:
        raise ValueError(
            f"--max-new-tokens={args.max_new_tokens} leaves no room in the "
            f"{context_window}-token context window"
        )
    effective_max_input = min(args.max_input_length, input_budget)
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=effective_max_input,
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
    latency_seconds = time.perf_counter() - started
    generated_text = tokenizer.decode(
        output_ids[0, inputs["input_ids"].shape[1] :],
        skip_special_tokens=True,
    ).strip()
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

    report = {
        "adapter": str(adapter_path),
        "base_model": peft_config.base_model_name_or_path,
        "test_file": str(args.test.resolve()),
        "test_index": args.index,
        "record_id": record.get("sample_id") or record.get("record_id"),
        "prompt_tokens": int(inputs["input_ids"].shape[1]),
        "original_prompt_tokens": original_prompt_tokens,
        "input_truncated": int(inputs["input_ids"].shape[1]) < original_prompt_tokens,
        "context_window": context_window,
        "generated_tokens": int(output_ids.shape[1] - inputs["input_ids"].shape[1]),
        "latency_seconds": round(latency_seconds, 3),
        "peak_vram_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
        "valid_json": valid_json,
        "parse_error": parse_error,
        "valid_schema": valid_schema,
        "schema_error": schema_error,
        "generated_text": generated_text,
        "parsed_output": parsed_output,
        "expected_response": record["response"],
    }
    output_path = args.output or (adapter_path / "verification_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
