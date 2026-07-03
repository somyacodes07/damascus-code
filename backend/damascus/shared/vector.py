"""
Qdrant Connection — Semantic Vector Memory
==========================================
Provides the async Qdrant client for the Semantic Memory layer.
Handles vector embedding storage and similarity search.

Credentials: DAMASCUS_QDRANT_URL (see config.py)
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from damascus.config import settings

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_qdrant_client: AsyncQdrantClient | None = None


async def get_qdrant() -> AsyncQdrantClient:
    """Return the shared Qdrant async client, creating if needed."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(url=settings.qdrant.url)
    return _qdrant_client


async def close_qdrant() -> None:
    """Close the Qdrant connection. Call on application shutdown."""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None


async def ensure_collections() -> None:
    """
    Ensure required Qdrant collections exist.
    Called on application startup.
    """
    client = await get_qdrant()

    # Memories collection — stores semantic embeddings for memory records
    existing = await client.get_collections()
    collection_names = {c.name for c in existing.collections}

    if settings.qdrant.collection_memories not in collection_names:
        await client.create_collection(
            collection_name=settings.qdrant.collection_memories,
            vectors_config=VectorParams(
                size=settings.qdrant.vector_size,
                distance=Distance.COSINE,
            ),
        )


async def ping_qdrant() -> bool:
    """Check if Qdrant is reachable. Returns True on success."""
    try:
        client = await get_qdrant()
        collections = await client.get_collections()
        return collections is not None
    except Exception:
        return False
