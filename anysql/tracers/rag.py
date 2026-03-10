"""
anysql/tracers/rag.py
RAG tracer for UC5 — RAG Quality Forensics.

Usage:
    rag = RAGTracer(db)

    query_id = rag.before_retrieval("What is FedRAMP?")
    chunks = vector_db.search(query, top_k=5)
    rag.after_retrieval(query_id, chunks)

    # ... generate answer ...

    rag.record_eval(query_id=query_id, score=0.85, actual=answer)

    # Now query:
    db.rag_failure_modes()    # retrieval vs generation failure analysis
    db.chunk_quality_ranking() # which source docs produce bad answers?
    db.similarity_calibration() # does high cosine score = good answer?
"""

import uuid
from datetime import datetime, timezone
from typing import Optional


class RAGTracer:
    def __init__(self, db):
        self._db = db

    def before_retrieval(self, query: str, session_id: Optional[str] = None) -> str:
        """Returns a query_id — pass to after_retrieval() and record_eval()."""
        return str(uuid.uuid4())

    def after_retrieval(
        self, query_id: str, chunks: list,
        session_id: Optional[str] = None,
        embedding_model: Optional[str] = None,
        normalize_fn=None,
    ) -> None:
        """
        Record retrieved chunks into rag.chunks.
        Auto-detects: LangChain (doc, score) tuples, LlamaIndex NodeWithScore, plain dicts.
        Pass normalize_fn(chunk) -> dict for custom formats.
        """
        records = []
        for rank, chunk in enumerate(chunks):
            n = self._normalize(chunk, normalize_fn)
            records.append({
                "retrieval_id":    str(uuid.uuid4()),
                "query_id":        query_id,
                "session_id":      session_id,
                "chunk_id":        n.get("chunk_id", str(uuid.uuid4())),
                "source_doc":      n.get("source_doc"),
                "chunk_text":      n.get("chunk_text"),
                "similarity_score": n.get("similarity_score"),
                "rank":            rank + 1,
                "chunks_retrieved": len(chunks),
                "embedding_model": embedding_model,
                "retrieved_at":    datetime.now(timezone.utc).isoformat(),
            })
        if records:
            self._db.insert("rag.chunks", records)

    def record_eval(
        self, query_id: str, score: float,
        expected: Optional[str] = None, actual: Optional[str] = None,
        model: Optional[str] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        **dim_scores,
    ) -> str:
        eval_id = str(uuid.uuid4())
        self._db.insert("eval.results", [{
            "eval_id":        eval_id,
            "query_id":       query_id,
            "prompt_id":      prompt_id,
            "prompt_version": prompt_version,
            "model":          model,
            "expected":       expected,
            "actual":         actual,
            "score":          score,
            "passed":         score >= 0.7,
            "score_factuality":   dim_scores.get("factuality"),
            "score_tone":         dim_scores.get("tone"),
            "score_safety":       dim_scores.get("safety"),
            "score_completeness": dim_scores.get("completeness"),
            "evaluated_at":   datetime.now(timezone.utc).isoformat(),
        }])
        return eval_id

    def _normalize(self, chunk, normalize_fn) -> dict:
        if normalize_fn:
            return normalize_fn(chunk)
        # LangChain: (Document, score) tuple
        if isinstance(chunk, tuple) and len(chunk) == 2:
            doc, score = chunk
            return {"chunk_id": getattr(doc, "id", str(uuid.uuid4())),
                    "chunk_text": getattr(doc, "page_content", str(doc)),
                    "similarity_score": float(score) if score is not None else None,
                    "source_doc": (getattr(doc, "metadata", {}) or {}).get("source")}
        # LlamaIndex: NodeWithScore
        if hasattr(chunk, "node") and hasattr(chunk, "score"):
            node = chunk.node
            return {"chunk_id": getattr(node, "node_id", str(uuid.uuid4())),
                    "chunk_text": getattr(node, "text", None),
                    "similarity_score": float(chunk.score) if chunk.score is not None else None,
                    "source_doc": (getattr(node, "metadata", {}) or {}).get("file_name")}
        # Plain dict
        if isinstance(chunk, dict):
            return {"chunk_id": chunk.get("id", chunk.get("chunk_id", str(uuid.uuid4()))),
                    "chunk_text": chunk.get("text", chunk.get("content", chunk.get("page_content"))),
                    "similarity_score": chunk.get("score", chunk.get("similarity_score")),
                    "source_doc": chunk.get("source", chunk.get("source_doc"))}
        return {"chunk_id": str(uuid.uuid4()), "chunk_text": str(chunk),
                "similarity_score": None, "source_doc": None}
