"""Mechanical provenance checks do not certify historical or pedagogical correctness."""
from __future__ import annotations

import re

from .schemas import Citation, Question, SourceChunk, normalize
from .retrieval import evidence_issue


def citation_for(chunk: SourceChunk) -> Citation:
    return Citation(chunk_id=chunk.id, source=chunk.source, book_page=chunk.book_page,
                    pdf_page=chunk.pdf_page, quote=chunk.text)


def check_question(question: Question, citations: list[Citation], chunks: list[SourceChunk]) -> dict:
    by_id = {c.id: c for c in chunks}
    issues = []
    if not citations:
        issues.append("missing_citation")
    valid = []
    for citation in citations:
        chunk = by_id.get(citation.chunk_id)
        if chunk is None:
            issues.append("unknown_chunk")
            continue
        if (citation.source != chunk.source or citation.book_page != chunk.book_page
                or citation.pdf_page != chunk.pdf_page or not normalize(citation.quote)
                or normalize(citation.quote) not in normalize(chunk.text)):
            issues.append("citation_mismatch")
            continue
        valid.append(chunk)
        if chunk.review_status != "teacher_approved":
            issues.append("unapproved_source")
        if evidence_issue(chunk):
            issues.append("insufficient_evidence")
    # Distractor dates are intentionally excluded: only the keyed answer is a factual claim.
    answer = question.choices[question.correct_answer] if question.choices else question.correct_answer
    claim = question.stem + " " + answer + " " + question.explanation
    years = set(re.findall(r"\b(?:1\d{3}|20\d{2})\b", claim))
    source_years = set(re.findall(r"\b(?:1\d{3}|20\d{2})\b", " ".join(c.text for c in valid)))
    if years - source_years:
        issues.append("unsupported_year")
    return {"status": "needs_teacher_review", "provenance_valid": bool(citations) and
            not any(i in issues for i in ("unknown_chunk", "citation_mismatch", "missing_citation")),
            "automatic_checks_passed": not issues, "semantic_support": "not_assessed",
            "issues": sorted(set(issues))}
