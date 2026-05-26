"""Async Prisma client singleton with CRUD helpers.

Wraps :class:`prisma.PrismaClient` in a module-level singleton that is safe
for use with ``asyncio``.  Call :func:`init_db` during application startup
and :func:`close_db` during shutdown.

CRUD helper methods cover the most common operations for users and documents.
More complex queries should use :func:`get_prisma` directly.
"""

from __future__ import annotations

import logging
from typing import Any

from prisma import PrismaClient
from prisma.errors import PrismaError

__all__ = [
    "get_prisma",
    "init_db",
    "close_db",
    "create_user",
    "get_user",
    "update_user",
    "create_document",
    "get_document",
    "list_documents",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
_prisma_client: PrismaClient | None = None


def _ensure_client() -> PrismaClient:
    """Return the module-level :class:`PrismaClient`, creating one if needed."""
    global _prisma_client  # noqa: PLW0603
    if _prisma_client is None:
        _prisma_client = PrismaClient()
    return _prisma_client


def get_prisma() -> PrismaClient:
    """Return the active :class:`PrismaClient` singleton.

    The client is **not** automatically connected.  Call :func:`init_db` (or
    ``await client.connect()``) before first use.
    """
    return _ensure_client()


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Connect to the database and ensure required tables exist.

    This function is idempotent – calling it multiple times has no effect.
    """
    client = _ensure_client()
    try:
        if client.is_connected():
            logger.debug("Prisma client already connected.")
            return
        await client.connect()
        logger.info("Connected to database: %s", client._datasource["url"])  # type: ignore[protected-access]
    except PrismaError as exc:
        logger.error("Failed to connect to database: %s", exc)
        raise


async def close_db() -> None:
    """Disconnect the Prisma client and release resources."""
    global _prisma_client  # noqa: PLW0603
    if _prisma_client is None:
        return
    try:
        if _prisma_client.is_connected():
            await _prisma_client.disconnect()
            logger.info("Disconnected from database.")
    except PrismaError as exc:
        logger.warning("Error while disconnecting from database: %s", exc)
    finally:
        _prisma_client = None


# ---------------------------------------------------------------------------
# User CRUD helpers
# ---------------------------------------------------------------------------
async def create_user(
    *,
    email: str,
    name: str,
    password_hash: str,
    role: str = "viewer",
) -> dict[str, Any]:
    """Create a new user and return the stored record as a dict.

    Parameters
    ----------
    email:
        Unique e-mail address.
    name:
        Display name.
    password_hash:
        Pre-hashed password (use :func:`app.core.security.hash_password`).
    role:
        Access role – ``"viewer"``, ``"editor"``, or ``"admin"``.
    """
    client = get_prisma()
    user = await client.user.create(
        data={
            "email": email,
            "name": name,
            "passwordHash": password_hash,
            "role": role,
        },
    )
    return _model_to_dict(user)


async def get_user(user_id: str) -> dict[str, Any] | None:
    """Fetch a single user by *user_id*.  Returns ``None`` if not found."""
    client = get_prisma()
    user = await client.user.find_unique(where={"id": user_id})
    return _model_to_dict(user) if user else None


async def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Fetch a single user by *email*.  Returns ``None`` if not found."""
    client = get_prisma()
    user = await client.user.find_unique(where={"email": email})
    return _model_to_dict(user) if user else None


async def update_user(
    user_id: str,
    *,
    name: str | None = None,
    password_hash: str | None = None,
    role: str | None = None,
) -> dict[str, Any] | None:
    """Update selected fields of an existing user.

    Fields that are ``None`` are left unchanged.  Returns the updated record
    or ``None`` if the user does not exist.
    """
    client = get_prisma()
    data: dict[str, Any] = {}
    if name is not None:
        data["name"] = name
    if password_hash is not None:
        data["passwordHash"] = password_hash
    if role is not None:
        data["role"] = role

    if not data:
        return await get_user(user_id)

    user = await client.user.update(
        where={"id": user_id},
        data=data,
    )
    return _model_to_dict(user)


# ---------------------------------------------------------------------------
# Document CRUD helpers
# ---------------------------------------------------------------------------
async def create_document(
    *,
    filename: str,
    filepath: str,
    user_id: str,
    mime_type: str = "application/octet-stream",
    file_size_bytes: int = 0,
) -> dict[str, Any]:
    """Create a new document record.

    Parameters
    ----------
    filename:
        Original file name.
    filepath:
        Server-side storage path.
    user_id:
        Owning user's ID (foreign key).
    mime_type:
        MIME type of the uploaded file.
    file_size_bytes:
        Size of the file in bytes.
    """
    client = get_prisma()
    doc = await client.document.create(
        data={
            "filename": filename,
            "filepath": filepath,
            "userId": user_id,
            "mimeType": mime_type,
            "fileSizeBytes": file_size_bytes,
        },
    )
    return _model_to_dict(doc)


async def get_document(document_id: str) -> dict[str, Any] | None:
    """Fetch a single document by *document_id*.  Returns ``None`` if not found."""
    client = get_prisma()
    doc = await client.document.find_unique(
        where={"id": document_id},
        include={"user": True},
    )
    return _model_to_dict(doc) if doc else None


async def list_documents(
    *,
    user_id: str | None = None,
    skip: int = 0,
    take: int = 20,
) -> list[dict[str, Any]]:
    """Return a paginated list of documents.

    Parameters
    ----------
    user_id:
        Filter by owning user.  When ``None`` all documents are returned.
    skip:
        Number of records to skip (offset).
    take:
        Maximum number of records to return.
    """
    client = get_prisma()
    where: dict[str, Any] = {}
    if user_id is not None:
        where["userId"] = user_id

    docs = await client.document.find_many(
        where=where,
        skip=skip,
        take=take,
        order={"createdAt": "desc"},
        include={"user": True},
    )
    return [_model_to_dict(d) for d in docs]


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------
def _model_to_dict(model: Any) -> dict[str, Any]:
    """Convert a Prisma model instance to a plain :class:`dict`.

    Handles ``datetime`` serialisation to ISO-8601 strings recursively.
    """
    if model is None:
        return {}
    if isinstance(model, dict):
        return {k: _model_to_dict(v) for k, v in model.items()}
    if isinstance(model, list):
        return [_model_to_dict(item) for item in model]
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "__dict__"):
        result: dict[str, Any] = {}
        for key, value in model.__dict__.items():
            if key.startswith("_"):
                continue
            result[key] = _model_to_dict(value)
        return result
    return model  # type: ignore[return-value]
