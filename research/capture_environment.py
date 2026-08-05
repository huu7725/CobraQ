"""Capture the software/hardware profile required for reproducible experiments."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "research" / "environment.json")
    args = parser.parse_args()
    packages = {}
    for name in (
        "torch", "transformers", "peft", "accelerate", "sentence-transformers",
        "chromadb", "fastapi", "pydantic",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not-installed"
    torch_info = {"installed": False, "cuda_available": False}
    try:
        import torch

        torch_info = {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "gpu_count": torch.cuda.device_count(),
            "gpus": [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())],
        }
    except ImportError:
        pass
    profile = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "python": sys.version,
        "python_executable": sys.executable,
        "torch": torch_info,
        "packages": packages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
