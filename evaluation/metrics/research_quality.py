"""Reproducible text-overlap / exact entity metrics; semantic correctness needs human labels."""
from __future__ import annotations

from collections import Counter
import math

from backend.app.research.schemas import normalize


def rouge_l(prediction: str, reference: str) -> float:
    left, right = normalize(prediction).split(), normalize(reference).split()
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0]
        for j, other in enumerate(right, 1):
            current.append(previous[j - 1] + 1 if token == other else max(previous[j], current[-1]))
        previous = current
    lcs = previous[-1]
    return 2 * lcs / (len(left) + len(right)) if left or right else 0.0


def corpus_bleu(pairs: list[tuple[str, str]]) -> float:
    """BLEU-4 on [0,1], one reference, no smoothing, NFKC/casefold word tokenization."""
    matches, totals, pred_length, ref_length = [0] * 4, [0] * 4, 0, 0
    for prediction, reference in pairs:
        pred, ref = normalize(prediction).split(), normalize(reference).split()
        pred_length += len(pred); ref_length += len(ref)
        for n in range(1, 5):
            p = Counter(tuple(pred[i:i+n]) for i in range(len(pred) - n + 1))
            r = Counter(tuple(ref[i:i+n]) for i in range(len(ref) - n + 1))
            matches[n-1] += sum((p & r).values()); totals[n-1] += sum(p.values())
    if not pred_length or any(m == 0 or t == 0 for m, t in zip(matches, totals)):
        return 0.0
    brevity = min(1.0, math.exp(1 - ref_length / pred_length))
    return brevity * math.exp(sum(math.log(m / t) for m, t in zip(matches, totals)) / 4)


def evaluate_quality(rows: list[dict]) -> dict:
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Quality evaluation requires nonempty, unique item IDs")
    tp = fp = fn = 0
    labeled = []
    for row in rows:
        def entities(key):
            return {(e["type"], normalize(e["text"])) for e in row[key]}
        predicted, gold = entities("predicted_entities"), entities("gold_entities")
        tp += len(predicted & gold); fp += len(predicted - gold); fn += len(gold - predicted)
        label = row.get("historical_factuality", "unreviewed")
        if label not in {"correct", "incorrect", "unreviewed"}:
            raise ValueError("Invalid factuality label")
        if label != "unreviewed":
            if not row.get("reviewer_id") or not row.get("reviewed_at"):
                raise ValueError("Factuality labels require teacher identity and date")
            from datetime import date
            date.fromisoformat(row["reviewed_at"])
            labeled.append(label)
    pairs = [(r["prediction"], r["reference"]) for r in rows]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"total": len(rows), "bleu_4": corpus_bleu(pairs),
            "rouge_l_f1": sum(rouge_l(p, r) for p, r in pairs) / len(pairs),
            "entity_precision": precision, "entity_recall": recall,
            "entity_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
            "entity_matching": "exact_normalized_type_and_text", "factuality_reviewed": len(labeled),
            "hallucination_rate": labeled.count("incorrect") / len(labeled) if labeled else None,
            "factuality_complete": len(labeled) == len(rows),
            "notice": "Text overlap and entity agreement do not certify historical correctness."}
