"""Evidence-grounded factuality checks for CobraQ question records."""

from __future__ import annotations

from collections import Counter
import re
import unicodedata
from typing import Any

from backend.app.services.trust_layer import extract_fact_markers


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join(re.findall(r"[0-9a-z]+", value))


def _correct_answer_text(question: dict[str, Any]) -> str:
    answer = str(question.get("correct_answer") or "")
    if question.get("question_type") == "multiple_choice":
        for choice in question.get("choices") or []:
            if choice.get("label") == answer:
                return str(choice.get("text") or "")
    return answer


def evaluate_question_factuality(
    question: dict[str, Any],
    chunk_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    condition = question.get("generation_condition", "")
    citations = question.get("citations") or []
    cited_chunks = [chunk_map[item.get("chunk_id")] for item in citations if item.get("chunk_id") in chunk_map]
    evidence = "\n".join(str(chunk.get("text") or "") for chunk in cited_chunks)
    claim_text = "\n".join(
        [
            str(question.get("stem") or ""),
            _correct_answer_text(question),
            str(question.get("explanation") or ""),
        ]
    )
    unsupported_facts = sorted(extract_fact_markers(claim_text) - extract_fact_markers(evidence))
    invalid_citations = [item.get("chunk_id") for item in citations if item.get("chunk_id") not in chunk_map]
    unsupported_quotes = []
    for citation in citations:
        chunk = chunk_map.get(citation.get("chunk_id"))
        if not chunk:
            continue
        quote = _normalize(str(citation.get("quote") or ""))
        source = _normalize(str(chunk.get("text") or ""))
        if not quote or quote not in source:
            unsupported_quotes.append(citation.get("chunk_id"))

    critical_errors = []
    if condition in {"C1", "C3"} and not citations:
        critical_errors.append("missing_rag_citation")
    if invalid_citations:
        critical_errors.append("invalid_chunk_id")
    if unsupported_quotes:
        critical_errors.append("quote_not_found_in_source")
    if unsupported_facts:
        critical_errors.append("unsupported_time_fact")

    choices = question.get("choices") or []
    if question.get("question_type") == "multiple_choice":
        labels = [choice.get("label") for choice in choices]
        texts = [_normalize(str(choice.get("text") or "")) for choice in choices]
        if len(choices) != 4 or question.get("correct_answer") not in labels:
            critical_errors.append("invalid_multiple_choice_contract")
        if len(set(texts)) != len(texts):
            critical_errors.append("duplicate_choice")

    return {
        "factual_error": bool(critical_errors),
        "critical_errors": critical_errors,
        "unsupported_facts": unsupported_facts,
        "invalid_citations": invalid_citations,
        "unsupported_quotes": unsupported_quotes,
        "citation_count": len(citations),
        "valid_citation_count": len(citations) - len(invalid_citations),
        "fact_support_rate": (
            round(1 - len(unsupported_facts) / len(extract_fact_markers(claim_text)), 4)
            if extract_fact_markers(claim_text) else 1.0
        ),
    }


def aggregate_factuality(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"questions": 0, "factual_error_rate": 0.0, "mean_fact_support_rate": 0.0}
    errors = sum(bool(item.get("factual_error")) for item in results)
    support = [float(item.get("fact_support_rate", 0.0)) for item in results]
    reasons = Counter(reason for item in results for reason in item.get("critical_errors", []))
    return {
        "questions": len(results),
        "factual_error_rate": round(errors / len(results), 4),
        "mean_fact_support_rate": round(sum(support) / len(support), 4),
        "critical_error_counts": dict(reasons),
    }
