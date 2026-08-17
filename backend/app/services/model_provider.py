"""Pluggable text-generation backends for CobraQ experiments."""

from __future__ import annotations

from dataclasses import dataclass
import gc
from pathlib import Path
import time
from typing import Protocol

from app.core.config import get_settings


class ModelBackendError(RuntimeError):
    pass


@dataclass(slots=True)
class GenerationOutput:
    text: str
    model_id: str
    adapter_id: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    peak_vram_mb: float = 0.0
    original_prompt_tokens: int = 0
    input_truncated: bool = False


class TextGenerationBackend(Protocol):
    def generate(self, prompt: str, *, max_new_tokens: int, temperature: float, top_p: float) -> GenerationOutput:
        ...


class OpenAICompatibleBackend:
    """Reference/API backend. It is not the target C0-C3 deployment backend."""

    def __init__(self, model_id: str | None = None):
        settings = get_settings()
        api_key = settings.grok_api_key or settings.ai_api_key or settings.anthropic_api_key
        if not api_key:
            raise ModelBackendError("No API key configured for the reference backend")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ModelBackendError("Install the openai package to use the API backend") from error
        self.model_id = model_id or settings.ai_model
        self.client = OpenAI(api_key=api_key, base_url=settings.ai_base_url)

    def generate(self, prompt: str, *, max_new_tokens: int, temperature: float, top_p: float) -> GenerationOutput:
        started = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là hệ thống AQG môn Lịch sử 12. Chỉ trả về JSON hợp lệ.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        usage = response.usage
        return GenerationOutput(
            text=(response.choices[0].message.content or "").strip(),
            model_id=self.model_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )


class LocalTransformersBackend:
    """Lazy local SLM backend with optional PEFT adapter."""

    def __init__(self, model_id: str, adapter_path: str = "", seed: int = 42):
        self.model_id = model_id
        self.adapter_path = adapter_path
        self.seed = seed
        self._tokenizer = None
        self._model = None
        self._torch = None

    def _load(self):
        if self._model is not None:
            return
        if self.adapter_path and not Path(self.adapter_path).exists():
            raise ModelBackendError(f"LoRA adapter not found: {self.adapter_path}")
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise ModelBackendError(
                "Local SLM dependencies are missing. Install requirements-research.txt."
            ) from error
        self._torch = torch
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        tokenizer_source = self.adapter_path or self.model_id
        self._tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, use_fast=True)
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        model_kwargs = {"torch_dtype": torch.float32}
        if torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig
            except ImportError as error:
                raise ModelBackendError("Install bitsandbytes for local 4-bit CUDA inference") from error
            compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            model_kwargs = {
                "quantization_config": BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=compute_dtype,
                ),
                "torch_dtype": compute_dtype,
                "device_map": "auto",
            }
        self._model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)
        if self.adapter_path:
            adapter = Path(self.adapter_path)
            try:
                from peft import PeftModel
            except ImportError as error:
                raise ModelBackendError("Install peft to load the LoRA adapter") from error
            self._model = PeftModel.from_pretrained(self._model, str(adapter))
        self._model.eval()

    def generate(self, prompt: str, *, max_new_tokens: int, temperature: float, top_p: float) -> GenerationOutput:
        self._load()
        torch = self._torch
        tokenizer = self._tokenizer
        model = self._model
        started = time.perf_counter()
        model_context = int(getattr(model.config, "max_position_embeddings", 2048))
        max_input_length = max(256, model_context - max_new_tokens)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=False)
        original_prompt_tokens = int(inputs["input_ids"].shape[1])
        input_truncated = original_prompt_tokens > max_input_length
        if input_truncated:
            prefix_length = max_input_length // 2
            suffix_length = max_input_length - prefix_length
            for key, value in inputs.items():
                if value.ndim == 2 and value.shape[1] == original_prompt_tokens:
                    inputs[key] = torch.cat(
                        (value[:, :prefix_length], value[:, -suffix_length:]),
                        dim=1,
                    )
        device = next(model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        do_sample = temperature > 0
        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "pad_token_id": tokenizer.pad_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if do_sample:
            generation_kwargs.update(temperature=temperature, top_p=top_p)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            output = model.generate(**inputs, **generation_kwargs)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        generated = output[0][inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(generated, skip_special_tokens=True).strip()
        return GenerationOutput(
            text=text,
            model_id=self.model_id,
            adapter_id=self.adapter_path,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=int(inputs["input_ids"].shape[1]),
            completion_tokens=int(generated.shape[0]),
            peak_vram_mb=(
                round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
                if torch.cuda.is_available()
                else 0.0
            ),
            original_prompt_tokens=original_prompt_tokens,
            input_truncated=input_truncated,
        )

    def close(self):
        self._model = None
        self._tokenizer = None
        gc.collect()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
        self._torch = None


def create_backend(
    name: str,
    *,
    model_id: str,
    adapter_path: str = "",
    seed: int = 42,
) -> TextGenerationBackend:
    normalized = name.strip().lower()
    if normalized == "local":
        return LocalTransformersBackend(model_id, adapter_path, seed=seed)
    if normalized in {"api", "openai-compatible"}:
        if adapter_path:
            raise ModelBackendError("The API reference backend cannot load a local LoRA adapter")
        return OpenAICompatibleBackend(model_id=None)
    raise ModelBackendError(f"Unknown model backend: {name}")
