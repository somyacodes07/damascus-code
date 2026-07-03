"""
MinIO Connection — Object Storage
==================================
Provides the MinIO client for large file storage:
research artifacts, benchmark datasets, exported memories.

Credentials: DAMASCUS_STORAGE_* (see config.py)
"""

from __future__ import annotations

from minio import Minio

from damascus.config import settings

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_minio_client: Minio | None = None


def get_storage() -> Minio:
    """Return the shared MinIO client, creating if needed."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.storage.endpoint,
            access_key=settings.storage.access_key,
            secret_key=settings.storage.secret_key,
            secure=settings.storage.secure,
        )
    return _minio_client


async def ensure_buckets() -> None:
    """
    Ensure required MinIO buckets exist.
    Called on application startup.
    """
    client = get_storage()
    bucket = settings.storage.bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def ping_storage() -> bool:
    """Check if MinIO is reachable. Returns True on success."""
    try:
        client = get_storage()
        client.list_buckets()
        return True
    except Exception:
        return False
