"""Secondary lexical/semantic text metrics for AQG outputs.

These metrics are intentionally secondary to factuality and teacher review.
"""

from __future__ import annotations

from typing import Sequence


def compute_text_quality(
    predictions: Sequence[str],
    references: Sequence[str],
    *,
    language: str = "vi",
) -> dict[str, float]:
    if len(predictions) != len(references) or not predictions:
        raise ValueError("predictions and references must be non-empty and have equal length")
    try:
        import sacrebleu
        from rouge_score import rouge_scorer
        from bert_score import score as bert_score
    except ImportError as error:
        raise RuntimeError(
            "Install requirements-research.txt to compute BLEU, ROUGE and BERTScore"
        ) from error

    bleu = sacrebleu.corpus_bleu(list(predictions), [list(references)]).score
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
    rouge = [scorer.score(reference, prediction) for prediction, reference in zip(predictions, references)]
    _, _, bert_f1 = bert_score(list(predictions), list(references), lang=language, verbose=False)
    return {
        "bleu": round(float(bleu), 4),
        "rouge1_f1": round(sum(item["rouge1"].fmeasure for item in rouge) / len(rouge), 4),
        "rouge2_f1": round(sum(item["rouge2"].fmeasure for item in rouge) / len(rouge), 4),
        "rougeL_f1": round(sum(item["rougeL"].fmeasure for item in rouge) / len(rouge), 4),
        "bertscore_f1": round(float(bert_f1.mean()), 4),
    }
