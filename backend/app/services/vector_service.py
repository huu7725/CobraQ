"""
Vector search service using ChromaDB.
Replaces keyword overlap with semantic similarity search.
"""

from __future__ import annotations
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Optional
import unicodedata

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from .trust_layer import Chunk


class VectorService:
    """
    ChromaDB-backed vector store for semantic chunk search.
    Falls back to in-memory keyword search if ChromaDB unavailable.
    """

    def __init__(
        self,
        persist_dir: str = "data/chroma_db",
        collection_name: str = "cobraq_chunks",
        embedding_model: Optional[str] = None,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model or os.getenv(
            "COBRAQ_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
        )
        self._client = None
        self._collection = None
        self._embedding_function = None
        self._embedding_initialized = False
        self._use_chroma = False
        self._keyword_fallback: dict[str, list[Chunk]] = {}

        if CHROMA_AVAILABLE:
            try:
                Path(persist_dir).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "description": "CobraQ document chunks",
                        "hnsw:space": "cosine",
                        "embedding_model": self.embedding_model,
                    },
                )
                self._use_chroma = True
            except Exception as e:
                print(f"[VectorService] ChromaDB init failed: {e}, falling back to keyword search")
                self._use_chroma = False

    # ── Embedding ──────────────────────────────────────────────

    def _get_embedding_function(self):
        """Get embedding function compatible with ChromaDB."""
        if self._embedding_initialized:
            return self._embedding_function
        self._embedding_initialized = True
        if not CHROMA_AVAILABLE:
            return None
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            self._embedding_function = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model)
        except Exception:
            try:
                from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
                self._embedding_function = OpenAIEmbeddingFunction()
            except Exception:
                self._embedding_function = None
        return self._embedding_function

    def _embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """Generate embeddings using available backend."""
        ef = self._get_embedding_function()
        if ef:
            prefix = ""
            if "e5" in self.embedding_model.lower():
                prefix = "query: " if is_query else "passage: "
            return ef([prefix + text for text in texts])
        raise RuntimeError(
            f"Embedding model unavailable: {self.embedding_model}. "
            "Install sentence-transformers or use keyword retrieval."
        )

    @staticmethod
    def _metadata_value(value):
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    # ── Chunk operations ───────────────────────────────────────

    def upsert_chunks(self, doc_id: str, chunks: list[Chunk]):
        """
        Store or update chunks for a document.
        Creates embeddings and persists to ChromaDB.
        """
        if not chunks:
            return

        # Always keep in-memory fallback
        self._keyword_fallback[doc_id] = chunks

        if not self._use_chroma or not self._collection:
            return

        try:
            ids = [c.id for c in chunks]
            texts = [c.text for c in chunks]
            embeddings = self._embed_texts(texts, is_query=False)
            metadatas = [
                {
                    "doc_id": doc_id,
                    "source": c.source,
                    "page": c.page,
                    **{
                        key: self._metadata_value(value)
                        for key, value in c.metadata.items()
                    },
                }
                for c in chunks
            ]

            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
        except Exception as e:
            print(f"[VectorService] ChromaDB upsert failed: {e}")

    def delete_doc(self, doc_id: str):
        """Delete all chunks for a document."""
        if doc_id in self._keyword_fallback:
            del self._keyword_fallback[doc_id]

        if self._use_chroma and self._collection:
            try:
                self._collection.delete(where={"doc_id": doc_id})
            except Exception as e:
                print(f"[VectorService] ChromaDB delete failed: {e}")

    # ── Search ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        doc_id: Optional[str] = None,
        top_k: int = 5,
        mode: str = "hybrid",
        filters: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Semantic search for relevant chunks.
        Falls back to keyword search if ChromaDB unavailable.
        """
        mode = mode.lower()
        if mode not in {"dense", "keyword", "hybrid"}:
            raise ValueError("mode must be one of: dense, keyword, hybrid")
        if mode == "keyword" or not self._use_chroma or not self._collection:
            return self._search_keyword(query, doc_id, top_k, filters=filters)
        if mode == "dense":
            return self._search_vector(query, doc_id, top_k, filters=filters)
        dense = self._search_vector(query, doc_id, top_k * 3, filters=filters)
        keyword = self._search_keyword(query, doc_id, top_k * 3, filters=filters)
        return self._reciprocal_rank_fusion(dense, keyword, top_k)

    @staticmethod
    def _build_where(doc_id: Optional[str], filters: Optional[dict]):
        clauses = []
        if doc_id:
            clauses.append({"doc_id": doc_id})
        for key, value in (filters or {}).items():
            if value is not None and value != "":
                clauses.append({key: value})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _search_vector(
        self,
        query: str,
        doc_id: Optional[str],
        top_k: int,
        filters: Optional[dict] = None,
    ) -> list[Chunk]:
        """ChromaDB vector search."""
        try:
            where_filter = self._build_where(doc_id, filters)
            query_embedding = self._embed_texts([query], is_query=True)[0]
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results["documents"] and results["documents"][0]:
                for i, doc_text in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    dist = results["distances"][0][i] if results["distances"] else 0.0
                    chunks.append(Chunk(
                        id=results["ids"][0][i],
                        text=doc_text,
                        source=meta.get("source", ""),
                        page=meta.get("page", 0),
                        score=1.0 - min(dist, 1.0),
                        metadata={key: value for key, value in meta.items() if key not in {"source", "page", "doc_id"}},
                    ))
            return chunks
        except Exception as e:
            print(f"[VectorService] Vector search failed: {e}, falling back to keyword")
            return self._search_keyword(query, doc_id, top_k, filters=filters)

    def _search_keyword(
        self,
        query: str,
        doc_id: Optional[str],
        top_k: int,
        filters: Optional[dict] = None,
    ) -> list[Chunk]:
        """Keyword overlap search (fallback)."""
        query_words = self._tokenize(query)
        candidates: list[Chunk] = []

        if doc_id:
            candidates = self._keyword_fallback.get(doc_id, [])
        else:
            for chunks in self._keyword_fallback.values():
                candidates.extend(chunks)

        if not candidates and self._use_chroma and self._collection:
            try:
                result = self._collection.get(
                    where=self._build_where(doc_id, filters),
                    include=["documents", "metadatas"],
                )
                for index, text in enumerate(result.get("documents") or []):
                    meta = (result.get("metadatas") or [{}])[index] or {}
                    candidates.append(
                        Chunk(
                            id=result["ids"][index],
                            text=text,
                            source=meta.get("source", ""),
                            page=meta.get("page", 0),
                            metadata={key: value for key, value in meta.items() if key not in {"source", "page", "doc_id"}},
                        )
                    )
            except Exception as error:
                print(f"[VectorService] Keyword candidate load failed: {error}")

        if filters:
            candidates = [
                chunk for chunk in candidates
                if all(chunk.metadata.get(key) == value for key, value in filters.items() if value not in (None, ""))
            ]

        scored = []
        for chunk in candidates:
            chunk_words = self._tokenize(chunk.text)
            if not chunk_words:
                continue
            overlap = len(query_words & chunk_words)
            score = overlap / max(len(query_words), 1)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = []
        for score, chunk in scored[:top_k]:
            chunk.score = score
            result.append(chunk)
        return result

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = unicodedata.normalize("NFD", (text or "").lower())
        folded = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        folded = folded.replace("đ", "d")
        return {token for token in folded.replace("-", " ").split() if len(token) > 1}

    @staticmethod
    def _reciprocal_rank_fusion(dense: list[Chunk], keyword: list[Chunk], top_k: int) -> list[Chunk]:
        scores: dict[str, float] = {}
        chunks: dict[str, Chunk] = {}
        for ranking in (dense, keyword):
            for rank, chunk in enumerate(ranking, start=1):
                scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (60 + rank)
                chunks.setdefault(chunk.id, chunk)
        ordered = sorted(scores, key=scores.get, reverse=True)[:top_k]
        if not ordered:
            return []
        max_score = max(scores[item] for item in ordered)
        for chunk_id in ordered:
            # Normalize RRF into [0, 1] so TrustLayer confidence thresholds remain meaningful.
            chunks[chunk_id].score = scores[chunk_id] / max_score
        return [chunks[chunk_id] for chunk_id in ordered]

    @property
    def is_vector_enabled(self) -> bool:
        return self._use_chroma

    def get_stats(self) -> dict:
        """Return collection stats."""
        total = 0
        if self._use_chroma and self._collection:
            try:
                total = self._collection.count()
            except Exception:
                pass
        return {
            "vector_enabled": self._use_chroma,
            "total_chunks": total,
            "docs_in_memory": len(self._keyword_fallback),
            "persist_dir": self.persist_dir,
            "model": self.embedding_model,
        }


@lru_cache(maxsize=1)
def get_vector_service() -> VectorService:
    """Create the default store only when a caller explicitly requests it."""
    return VectorService()
