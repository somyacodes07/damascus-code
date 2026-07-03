"""
Semantic Memory — Qdrant vector similarity search
===================================================
Semantic memory enables retrieval by meaning, not just by exact match.
Text is converted to vector embeddings and stored in Qdrant.
Queries find the most relevant memories based on semantic similarity.

Storage: Qdrant (vector store) + MemoryRecord in PostgreSQL (authoritative)

Phase 1 implementation:
- Store embeddings using Ollama's embedding API (nomic-embed-text model)
- Retrieve by cosine similarity
- Memory scoping by workspace_id as Qdrant payload filter
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from damascus.config import settings
from damascus.shared.vector import get_qdrant

log = structlog.get_logger(__name__)


async def _get_embedding(text: str) -> list[float] | None:
    """
    Generate a text embedding using the configured model provider.
    V1: Uses Ollama's nomic-embed-text model.
    Returns None if embedding cannot be generated.
    """
    if not settings.models.ollama.enabled:
        log.warning("Ollama not enabled — skipping semantic embedding")
        return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.models.ollama.endpoint}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
    except Exception as exc:
        log.warning("Failed to generate embedding", error=str(exc))
        return None


class SemanticMemory:
    """
    Manages semantic vector memory in Qdrant.
    Every stored memory record can have a corresponding vector embedding
    that enables similarity-based retrieval.
    """

    async def store_embedding(
        self,
        *,
        memory_id: str,
        workspace_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Generate and store a vector embedding for a memory record.
        Returns the embedding_id (Qdrant point ID) or None if skipped.
        """
        embedding = await _get_embedding(text)
        if embedding is None:
            return None

        client = await get_qdrant()
        point_id = str(uuid.uuid4())

        from qdrant_client.models import PointStruct
        await client.upsert(
            collection_name=settings.qdrant.collection_memories,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "memory_id": memory_id,
                        "workspace_id": workspace_id,
                        "text_preview": text[:500],
                        **(metadata or {}),
                    },
                )
            ],
        )

        log.debug("Stored semantic embedding", memory_id=memory_id, point_id=point_id)
        return point_id

    async def search(
        self,
        *,
        workspace_id: str,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Find the most semantically similar memories for a query.
        Results are filtered by workspace_id and sorted by similarity score.
        """
        embedding = await _get_embedding(query)
        if embedding is None:
            log.warning("Cannot perform semantic search — embedding unavailable")
            return []

        client = await get_qdrant()
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        results = await client.search(
            collection_name=settings.qdrant.collection_memories,
            query_vector=embedding,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="workspace_id",
                        match=MatchValue(value=workspace_id),
                    )
                ]
            ),
        )

        return [
            {
                "memory_id": r.payload.get("memory_id"),
                "score": r.score,
                "text_preview": r.payload.get("text_preview"),
                "embedding_id": r.id,
            }
            for r in results
        ]

    async def delete_embedding(self, embedding_id: str) -> None:
        """Remove a vector from Qdrant (e.g., when memory is archived)."""
        client = await get_qdrant()
        await client.delete(
            collection_name=settings.qdrant.collection_memories,
            points_selector=[embedding_id],
        )


# Module-level singleton
semantic_memory = SemanticMemory()
