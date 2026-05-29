"""
Vector search service using ChromaDB.
Replaces keyword overlap with semantic similarity search.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional

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
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
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
                    metadata={"description": "CobraQ document chunks"},
                )
                self._use_chroma = True
            except Exception as e:
                print(f"[VectorService] ChromaDB init failed: {e}, falling back to keyword search")
                self._use_chroma = False

    # ── Embedding ──────────────────────────────────────────────

    def _get_embedding_function(self):
        """Get embedding function compatible with ChromaDB."""
        if not CHROMA_AVAILABLE:
            return None
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            return SentenceTransformerEmbeddingFunction(model_name=self.embedding_model)
        except Exception:
            try:
                from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
                return OpenAIEmbeddingFunction()
            except Exception:
                return None

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using available backend."""
        ef = self._get_embedding_function()
        if ef:
            return ef(texts)

        # Fallback: deterministic hash-based pseudo-embedding (for dev only)
        import numpy as np
        dim = 384
        embeddings = []
        for text in texts:
            vec = np.zeros(dim, dtype=np.float32)
            for i, ch in enumerate(text):
                vec[hash(ch) % dim] += ord(ch)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            embeddings.append(vec.tolist())
        return embeddings

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
            embeddings = self._embed_texts(texts)
            metadatas = [
                {
                    "doc_id": doc_id,
                    "source": c.source,
                    "page": c.page,
                    "score": c.score,
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
    ) -> list[Chunk]:
        """
        Semantic search for relevant chunks.
        Falls back to keyword search if ChromaDB unavailable.
        """
        if self._use_chroma and self._collection:
            return self._search_vector(query, doc_id, top_k)
        return self._search_keyword(query, doc_id, top_k)

    def _search_vector(
        self,
        query: str,
        doc_id: Optional[str],
        top_k: int,
    ) -> list[Chunk]:
        """ChromaDB vector search."""
        try:
            where_filter = {"doc_id": doc_id} if doc_id else None
            results = self._collection.query(
                query_texts=[query],
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
                    ))
            return chunks
        except Exception as e:
            print(f"[VectorService] Vector search failed: {e}, falling back to keyword")
            return self._search_keyword(query, doc_id, top_k)

    def _search_keyword(
        self,
        query: str,
        doc_id: Optional[str],
        top_k: int,
    ) -> list[Chunk]:
        """Keyword overlap search (fallback)."""
        query_words = set(query.lower().split())
        candidates = []

        if doc_id:
            candidates = self._keyword_fallback.get(doc_id, [])
        else:
            for chunks in self._keyword_fallback.values():
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


vector_service = VectorService()
