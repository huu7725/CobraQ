"""Train the CobraQ LoRA adapter on reviewed Grade 12 History AQG data.

Expected JSONL fields:
  instruction: generation request
  context: optional textbook evidence
  response: valid JSON answer following the CobraQ question schema
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import random
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "research" / "configs" / "experiments.json"

# Running this file directly places ``research/`` first on sys.path. Its local
# ``datasets/`` data directory can then be mistaken for the optional Hugging
# Face ``datasets`` package by Transformers.
SCRIPT_DIR = str(Path(__file__).resolve().parent)
while SCRIPT_DIR in sys.path:
    sys.path.remove(SCRIPT_DIR)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "adapters" / "history12_lora")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--max-train-examples", type=int)
    parser.add_argument("--max-validation-examples", type=int)
    parser.add_argument(
        "--longest-first",
        action="store_true",
        help="Sort by tokenized length before limiting examples; useful for VRAM smoke tests.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Positive value overrides epochs; intended for deterministic smoke tests.",
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=10,
        help="Save a recoverable checkpoint every N optimizer steps during full training.",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        nargs="?",
        const="auto",
        help="Resume from a checkpoint path, or use 'auto' to select the latest checkpoint.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = {"instruction", "response"} - record.keys()
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {sorted(missing)}")
            if record.get("review_status") != "teacher_approved":
                raise ValueError(
                    f"{path}:{line_number} is not teacher_approved; unreviewed AQG data must not be trained"
                )
            records.append(record)
    if not records:
        raise ValueError(f"No training records found in {path}")
    return records


def format_prompt(record: dict) -> str:
    context = (record.get("context") or "").strip()
    context_block = f"\n### Ngữ liệu SGK\n{context}\n" if context else "\n"
    return (
        "Bạn là hệ thống sinh câu hỏi Lịch sử 12. Chỉ trả về JSON hợp lệ, "
        "không thêm Markdown.\n"
        f"### Yêu cầu\n{record['instruction'].strip()}\n"
        f"{context_block}### Trả lời\n"
    )


def main() -> int:
    args = parse_args()
    os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
    try:
        import torch
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            Trainer,
            TrainingArguments,
            set_seed,
        )
        from transformers.trainer_utils import get_last_checkpoint
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    except ImportError as error:
        raise SystemExit(
            "Missing research dependencies. Install requirements-research.txt first. "
            f"Original error: {error}"
        )

    config = json.loads(args.config.read_text(encoding="utf-8"))
    shared = config["shared"]
    lora = shared["lora"]
    model_id = args.model or shared["base_model"]
    seed = int(shared["seed"])
    random.seed(seed)
    set_seed(seed)

    if not torch.cuda.is_available() and not args.allow_cpu:
        raise SystemExit(
            "CUDA GPU was not detected. LoRA training is intentionally stopped to avoid an "
            "impractically slow CPU run. Use --allow-cpu only for a smoke test."
        )
    if args.qlora and not torch.cuda.is_available():
        raise SystemExit("QLoRA requires a CUDA-capable GPU in this training script")

    train_records = load_jsonl(args.train)
    validation_records = load_jsonl(args.validation) if args.validation else []
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.longest_first:
        def tokenized_length(record: dict) -> int:
            response = json.dumps(record["response"], ensure_ascii=False)
            return len(tokenizer(format_prompt(record) + response, add_special_tokens=True)["input_ids"])

        train_records.sort(key=tokenized_length, reverse=True)
        validation_records.sort(key=tokenized_length, reverse=True)
    if args.max_train_examples is not None:
        train_records = train_records[:args.max_train_examples]
    if args.max_validation_examples is not None:
        validation_records = validation_records[:args.max_validation_examples]
    if not train_records:
        raise ValueError("No training examples remain after applying --max-train-examples")

    class AQGDataset(Dataset):
        def __init__(self, records: list[dict]):
            self.items = []
            for record in records:
                prompt = format_prompt(record)
                response = record["response"]
                if not isinstance(response, str):
                    response = json.dumps(response, ensure_ascii=False)
                prompt_ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
                response_ids = tokenizer(response + tokenizer.eos_token, add_special_tokens=False)["input_ids"]
                input_ids = (prompt_ids + response_ids)[: args.max_length]
                prompt_length = min(len(prompt_ids), len(input_ids))
                labels = [-100] * prompt_length + input_ids[prompt_length:]
                self.items.append({"input_ids": input_ids, "labels": labels})

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            return self.items[index]

    def collate(batch):
        max_length = max(len(item["input_ids"]) for item in batch)
        input_ids, labels, attention_mask = [], [], []
        for item in batch:
            padding = max_length - len(item["input_ids"])
            input_ids.append(item["input_ids"] + [tokenizer.pad_token_id] * padding)
            labels.append(item["labels"] + [-100] * padding)
            attention_mask.append([1] * len(item["input_ids"]) + [0] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
        }

    quantization_config = None
    if args.qlora:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quantization_config,
        torch_dtype=(torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else None),
        device_map="auto" if torch.cuda.is_available() else None,
    )
    if args.qlora:
        model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    peft_config = LoraConfig(
        r=int(lora["rank"]),
        lora_alpha=int(lora["alpha"]),
        lora_dropout=float(lora["dropout"]),
        target_modules=list(lora["target_modules"]),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)

    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output / "checkpoints"
    resume_checkpoint = args.resume_from_checkpoint
    if resume_checkpoint == "auto":
        resume_checkpoint = get_last_checkpoint(str(checkpoint_dir)) if checkpoint_dir.exists() else None
        if resume_checkpoint:
            print(f"Resuming from latest checkpoint: {resume_checkpoint}")
        else:
            print(f"No checkpoint found in {checkpoint_dir}; starting from step 0")
    elif resume_checkpoint:
        resume_checkpoint = str(Path(resume_checkpoint).resolve())
        if not Path(resume_checkpoint).is_dir():
            raise ValueError(f"Checkpoint directory does not exist: {resume_checkpoint}")

    training_args = TrainingArguments(
        output_dir=str(checkpoint_dir),
        num_train_epochs=float(lora["epochs"]),
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=int(lora["gradient_accumulation_steps"]),
        learning_rate=float(lora["learning_rate"]),
        warmup_ratio=float(lora["warmup_ratio"]),
        logging_steps=10,
        save_strategy="no" if args.max_steps > 0 else "steps",
        save_steps=args.save_steps,
        save_total_limit=2,
        eval_strategy="no" if args.max_steps > 0 else ("epoch" if validation_records else "no"),
        bf16=bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
        fp16=bool(torch.cuda.is_available() and not torch.cuda.is_bf16_supported()),
        report_to=[],
        seed=seed,
        data_seed=seed,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=AQGDataset(train_records),
        eval_dataset=AQGDataset(validation_records) if validation_records else None,
        data_collator=collate,
    )
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    started = time.time()
    result = trainer.train(resume_from_checkpoint=resume_checkpoint)
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)

    packages = {}
    for package in ("torch", "transformers", "peft", "accelerate"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = "not-installed"
    manifest = {
        "base_model": model_id,
        "train_file": str(args.train.resolve()),
        "validation_file": str(args.validation.resolve()) if args.validation else None,
        "train_examples": len(train_records),
        "validation_examples": len(validation_records),
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "max_steps": args.max_steps,
        "save_steps": args.save_steps,
        "resumed_from_checkpoint": resume_checkpoint,
        "global_step": trainer.state.global_step,
        "epochs_completed": trainer.state.epoch,
        "seed": seed,
        "qlora": args.qlora,
        "lora": lora,
        "train_runtime_seconds": round(time.time() - started, 2),
        "train_metrics": result.metrics,
        "eval_history": [
            entry for entry in trainer.state.log_history if "eval_loss" in entry
        ],
        "training_log": trainer.state.log_history,
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "peak_vram_mb": (
            round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
            if torch.cuda.is_available() else 0
        ),
        "packages": packages,
    }
    (args.output / "training_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
