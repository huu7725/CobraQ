"""Load and validate CobraQ ablation conditions C0-C3."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "research" / "configs" / "experiments.json"


@dataclass(frozen=True, slots=True)
class ExperimentCondition:
    id: str
    name: str
    use_rag: bool
    use_lora: bool
    purpose: str
    adapter_path: str = ""


def load_experiment_config(path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        config = json.load(stream)
    conditions = config.get("conditions", [])
    ids = [item.get("id") for item in conditions]
    if ids != ["C0", "C1", "C2", "C3"]:
        raise ValueError("Experiment conditions must be ordered C0, C1, C2, C3")
    expected = {
        "C0": (False, False),
        "C1": (True, False),
        "C2": (False, True),
        "C3": (True, True),
    }
    for item in conditions:
        if (item["use_rag"], item["use_lora"]) != expected[item["id"]]:
            raise ValueError(f"Invalid ablation switches for {item['id']}")
    return config


def get_condition(condition_id: str, path: str | Path = DEFAULT_PATH) -> ExperimentCondition:
    config = load_experiment_config(path)
    for item in config["conditions"]:
        if item["id"] == condition_id:
            return ExperimentCondition(**item)
    raise KeyError(f"Unknown condition: {condition_id}")
