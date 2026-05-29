import re
from dataclasses import dataclass, field
from typing import Optional


def _count_tokens(text: str) -> int:
    """Count tokens (word-level approximation, cross-platform)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


@dataclass
class Chunk:
    id: str
    text: str
    source: str = ""
    page: int = 0
    score: float = 0.0


@dataclass
class Citation:
    chunk_id: str
    text: str
    source: str
    page: int
    confidence: float


@dataclass
class TrustResult:
    answer: str
    blocked: bool
    block_reason: str = ""
    citations: list[Citation] = field(default_factory=list)
    source_coverage: float = 0.0


class TrustLayer:
    """
    Trust Layer cho AI responses.
    - Yêu cầu citation bắt buộc cho mỗi câu trả lời.
    - Chặn output nếu không đủ evidence threshold.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        min_chunks: int = 1,
        max_context_length: int = 8000,
    ):
        self.min_confidence = min_confidence
        self.min_chunks = min_chunks
        self.max_context_length = max_context_length
        self._chunk_store: dict[str, list[Chunk]] = {}

    def store_chunks(self, doc_id: str, chunks: list[Chunk]):
        """Lưu chunks sau khi chunk hóa document."""
        self._chunk_store[doc_id] = chunks

    def get_chunks(self, doc_id: str) -> list[Chunk]:
        return self._chunk_store.get(doc_id, [])

    def retrieve_chunks(
        self,
        query: str,
        doc_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[Chunk]:
        """
        Semantic search đơn giản bằng keyword overlap.
        Thay bằng vector search (ChromaDB) khi cần.
        """
        query_words = set(query.lower().split())
        candidates = []
        if doc_id:
            candidates = self.get_chunks(doc_id)
        else:
            for chunks in self._chunk_store.values():
                candidates.extend(chunks)

        scored = []
        for chunk in candidates:
            chunk_words = set(chunk.text.lower().split())
            if not chunk_words:
                continue
            overlap = len(query_words & chunk_words)
            score = overlap / max(len(query_words), 1)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def should_block(self, chunks: list[Chunk], answer: str) -> tuple[bool, str]:
        """
        Kiểm tra xem có nên chặn response không.
        Returns: (blocked, reason)
        """
        if not chunks:
            return True, "Không tìm thấy thông tin liên quan trong ngữ liệu."

        if len(chunks) < self.min_chunks:
            return True, f"Cần ít nhất {self.min_chunks} đoạn trích dẫn, chỉ có {len(chunks)}."

        low_conf = [c for c in chunks if c.score < self.min_confidence]
        if len(low_conf) > len(chunks) * 0.5:
            return True, "Độ chính xác trích dẫn quá thấp."

        no_info_phrases = [
            "không biết", "không có", "không tìm thấy",
            "không rõ", "không thể", "tôi không",
        ]
        if any(p in answer.lower() for p in no_info_phrases):
            if not chunks:
                return True, "Không có thông tin trong ngữ liệu để trả lời."

        return False, ""

    def build_context(
        self,
        chunks: list[Chunk],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Ghép chunks thành context string, giới hạn bằng token count."""
        max_tok = max_tokens or self.max_context_length
        parts = []
        total_tok = 0
        for chunk in chunks:
            text = chunk.text.strip()
            tok_count = _count_tokens(text)
            ref = f"[Nguồn: {chunk.source}"
            if chunk.page:
                ref += f", Trang {chunk.page}"
            ref += "]"
            entry = f"{text}\n{ref}"
            entry_tok = tok_count + _count_tokens(ref)
            if total_tok + entry_tok > max_tok:
                break
            parts.append(entry)
            total_tok += entry_tok
        return "\n\n".join(parts)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        if _count_tokens(text) <= max_tokens:
            return text
        words = text.split()
        result = []
        tok_count = 0
        for word in words:
            tok_count += 1
            if tok_count > max_tokens:
                result.append("...")
                break
            result.append(word)
        return " ".join(result)

    def format_citation(self, chunk: Chunk) -> str:
        """Format một citation thành string hiển thị."""
        ref = f"📄 {chunk.source}"
        if chunk.page:
            ref += f" — Trang {chunk.page}"
        return f'"{chunk.text[:200]}{"..." if len(chunk.text) > 200 else ""}"\n   ({ref})'

    def parse_response_with_citations(self, raw_response: str) -> tuple[str, list[Citation]]:
        """
        Parse AI response để tách answer và citations.
        Hỗ trợ format có sẵn: ANSWER: ... SOURCES: ...
        """
        citations = []
        answer = raw_response

        answer_match = re.search(
            r'ANSWER:\s*(.+?)(?:\nSOURCES:|$)', raw_response, re.DOTALL | re.IGNORECASE
        )
        sources_match = re.search(
            r'SOURCES?:\s*(.+?)(?:\n\n|$)', raw_response, re.DOTALL | re.IGNORECASE
        )

        if answer_match:
            answer = answer_match.group(1).strip()

        if sources_match:
            src_text = sources_match.group(1).strip()
            src_lines = [s.strip() for s in src_text.split("\n") if s.strip()]
            for i, line in enumerate(src_lines):
                citations.append(Citation(
                    chunk_id=f"citation_{i+1}",
                    text=line.strip('"').strip("'"),
                    source="Ngữ liệu",
                    page=0,
                    confidence=0.8,
                ))

        return answer, citations

    def evaluate(self, response: str, chunks: list[Chunk]) -> dict:
        """
        Đánh giá quality của response.
        Returns dict với hallucination metrics.
        """
        blocked, reason = self.should_block(chunks, response)

        cited_texts = set()
        for chunk in chunks:
            words = set(chunk.text.lower().split())
            cited_texts.update(w for w in words if len(w) > 3)

        response_words = set(response.lower().split())
        uncited = [w for w in response_words if len(w) > 3 and w not in cited_texts]
        hallucination_rate = len(uncited) / max(len(response_words), 1)

        return {
            "blocked": blocked,
            "block_reason": reason,
            "hallucination_rate": round(hallucination_rate, 4),
            "citation_count": len(chunks),
            "source_coverage": min(len(chunks) / max(self.min_chunks, 1), 1.0),
        }


trust_layer = TrustLayer()
