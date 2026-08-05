"""Corpus utilities for the Grade 12 History knowledge base.

The module deliberately keeps OCR text traceable to a PDF page. It performs
conservative normalization and never rewrites dates or proper names because a
plausible auto-correction can become a historical factual error.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha1
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable, Optional


_YEAR_RE = re.compile(r"(?<!\d)(?:1[5-9]\d{2}|20\d{2})(?!\d)")
_DATE_RE = re.compile(
    r"(?i)\b(?:ngày\s+)?\d{1,2}\s*[-/]\s*\d{1,2}"
    r"(?:\s*[-/]\s*(?:1[5-9]\d{2}|20\d{2}))?\b"
)
_ENTITY_RE = re.compile(
    r"\b(?:[A-ZĐÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    r"ÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ][\wÀ-ỹ-]+(?:\s+|$)){2,6}",
    flags=re.UNICODE,
)
_QUESTION_STARTS = (
    "hãy ", "trình bày ", "nêu ", "phân tích ", "giải thích ",
    "so sánh ", "vì sao ", "tại sao ", "theo em ",
)
_ENTITY_STOP = {
    "Học xong", "Em có biết", "Kết nối", "Tư liệu", "Hình",
    "Luyện tập", "Vận dụng", "Câu hỏi", "Nội dung",
}
_SUSPICIOUS_SYMBOL_RE = re.compile(r"[§£«»\\|]{1,}|[—_]{3,}")


@dataclass(slots=True)
class HistoryChunk:
    chunk_id: str
    text: str
    source: str
    pdf_page: int
    book_page: int
    book_id: str
    grade: int
    series: str
    topic_id: str = ""
    topic_title: str = ""
    lesson_id: str = ""
    lesson_number: Optional[int] = None
    lesson_title: str = ""
    section_title: str = ""
    segment_type: str = "content"
    time_expressions: list[str] = field(default_factory=list)
    entity_candidates: list[str] = field(default_factory=list)
    ocr_confidence: Optional[float] = None
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    ocr_review_status: str = "not_required"
    ocr_reviewer_id: str = ""
    ocr_review_date: str = ""
    ocr_review_comment: str = ""
    ocr_original_text_sha256: str = ""
    ocr_review_workbook_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_book_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def normalize_ocr_text(text: str) -> str:
    """Normalize layout noise without guessing factual spellings."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u00ad", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=[A-Za-zÀ-ỹĐđ])-\n(?=[A-Za-zÀ-ỹĐđ])", "", text)
    text = re.sub(r"[ \t]+", " ", text)

    blocks: list[str] = []
    current: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        current.append(line)
    if current:
        blocks.append(" ".join(current))

    cleaned: list[str] = []
    for block in blocks:
        block = re.sub(r"\s+([,.;:!?])", r"\1", block)
        block = re.sub(r"([,.;:!?])(?=[A-Za-zÀ-ỹĐđ])", r"\1 ", block)
        block = re.sub(r"\s{2,}", " ", block).strip()
        if block:
            cleaned.append(block)
    return "\n\n".join(cleaned)


def lookup_scope(config: dict[str, Any], book_page: int) -> dict[str, Any]:
    for topic in config.get("topics", []):
        if topic["book_page_start"] <= book_page <= topic["book_page_end"]:
            scope = {
                "topic_id": topic["topic_id"],
                "topic_title": topic["title"],
                "lesson_id": "",
                "lesson_number": None,
                "lesson_title": "",
            }
            for lesson in topic.get("lessons", []):
                if lesson["book_page_start"] <= book_page <= lesson["book_page_end"]:
                    scope.update(
                        lesson_id=lesson["lesson_id"],
                        lesson_number=lesson["number"],
                        lesson_title=lesson["title"],
                    )
                    break
            return scope
    for appendix in config.get("appendices", []):
        if appendix["book_page_start"] <= book_page <= appendix["book_page_end"]:
            return {
                "topic_id": appendix["appendix_id"],
                "topic_title": appendix["title"],
                "lesson_id": "",
                "lesson_number": None,
                "lesson_title": "",
            }
    return {
        "topic_id": "front_or_back_matter",
        "topic_title": "Phần đầu/cuối sách",
        "lesson_id": "",
        "lesson_number": None,
        "lesson_title": "",
    }


def extract_time_expressions(text: str) -> list[str]:
    values = list(_DATE_RE.findall(text)) + list(_YEAR_RE.findall(text))
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def extract_entity_candidates(text: str, limit: int = 20) -> list[str]:
    candidates: list[str] = []
    for match in _ENTITY_RE.finditer(text):
        value = re.sub(r"\s+", " ", match.group(0)).strip(" .,:;()[]")
        if len(value) < 5 or any(value.startswith(stop) for stop in _ENTITY_STOP):
            continue
        words = value.split()
        if len(words) > 2 and value.isupper():
            continue
        if value not in candidates:
            candidates.append(value)
        if len(candidates) >= limit:
            break
    return candidates


def detect_segment_type(text: str) -> str:
    lowered = text.lower().lstrip("?@©1234567890.) ")
    if lowered.startswith(_QUESTION_STARTS) or text.rstrip().endswith("?"):
        return "question_prompt"
    if lowered.startswith("tư liệu"):
        return "source_box"
    if lowered.startswith("hình "):
        return "figure_caption"
    if lowered.startswith(("luyện tập", "vận dụng")):
        return "exercise"
    return "content"


def _looks_like_heading(text: str) -> bool:
    if not text or len(text) > 180:
        return False
    letters = [char for char in text if char.isalpha()]
    upper_ratio = sum(char.isupper() for char in letters) / max(len(letters), 1)
    return upper_ratio > 0.55 or bool(re.match(r"^(?:BÀI\s+\d+|\d+[.)]?\s+|[a-z]\))", text, re.I))


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZĐÀ-Ỵ])", paragraph)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def chunk_page_text(
    text: str,
    *,
    pdf_page: int,
    config: dict[str, Any],
    source: str,
    ocr_confidence: Optional[float] = None,
    max_chars: int = 1400,
    min_chars: int = 280,
    overlap_paragraphs: int = 1,
) -> list[HistoryChunk]:
    normalized = normalize_ocr_text(text)
    if not normalized:
        return []

    offset = int(config["page_mapping"].get("pdf_to_book_offset", 0))
    book_page = pdf_page + offset
    scope = lookup_scope(config, book_page)
    book = config["book"]
    paragraphs: list[str] = []
    for paragraph in normalized.split("\n\n"):
        paragraphs.extend(_split_long_paragraph(paragraph, max_chars))

    groups: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        para_len = len(paragraph) + (2 if current else 0)
        if current and current_len + para_len > max_chars:
            groups.append(current)
            current = current[-overlap_paragraphs:] if overlap_paragraphs else []
            current_len = sum(len(item) + 2 for item in current)
        current.append(paragraph)
        current_len += para_len
    if current:
        if groups and sum(len(item) for item in current) < min_chars:
            groups[-1].extend(current[overlap_paragraphs:] if overlap_paragraphs else current)
        else:
            groups.append(current)

    chunks: list[HistoryChunk] = []
    current_heading = ""
    for index, group in enumerate(groups, start=1):
        for paragraph in group:
            if _looks_like_heading(paragraph):
                current_heading = paragraph[:180]
                break
        chunk_text = "\n\n".join(group).strip()
        review_reasons: list[str] = []
        if ocr_confidence is not None and ocr_confidence < 80:
            review_reasons.append("ocr_confidence_below_80")
        if len(chunk_text) < min_chars:
            review_reasons.append("short_chunk")
        if "�" in chunk_text:
            review_reasons.append("unicode_replacement_character")
        if _SUSPICIOUS_SYMBOL_RE.search(chunk_text):
            review_reasons.append("suspicious_ocr_symbols")
        nonstandard = sum(
            1
            for char in chunk_text
            if not (char.isalnum() or char.isspace() or char in ".,;:!?()[]{}'\"“”‘’/-–—%+@©")
        )
        if nonstandard > 4:
            review_reasons.append("high_nonstandard_character_count")
        digest = sha1(
            f"{book['book_id']}|{pdf_page}|{index}|{chunk_text}".encode("utf-8")
        ).hexdigest()[:12]
        chunks.append(
            HistoryChunk(
                chunk_id=f"h12-p{pdf_page:03d}-c{index:02d}-{digest}",
                text=chunk_text,
                source=source,
                pdf_page=pdf_page,
                book_page=book_page,
                book_id=book["book_id"],
                grade=int(book["grade"]),
                series=book["series"],
                topic_id=scope["topic_id"],
                topic_title=scope["topic_title"],
                lesson_id=scope["lesson_id"],
                lesson_number=scope["lesson_number"],
                lesson_title=scope["lesson_title"],
                section_title=current_heading,
                segment_type=detect_segment_type(chunk_text),
                time_expressions=extract_time_expressions(chunk_text),
                entity_candidates=extract_entity_candidates(chunk_text),
                ocr_confidence=ocr_confidence,
                review_required=bool(review_reasons),
                review_reasons=review_reasons,
                ocr_review_status="pending" if review_reasons else "not_required",
            )
        )
    return chunks


def write_jsonl(records: Iterable[dict[str, Any]], path: str | Path) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def load_chunks(path: str | Path) -> list[HistoryChunk]:
    chunks: list[HistoryChunk] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                chunks.append(HistoryChunk(**json.loads(line)))
    return chunks
