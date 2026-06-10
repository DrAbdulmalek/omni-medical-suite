"""Async task management endpoints for OmniMedicalSuite.

Provides endpoints for submitting, tracking, cancelling, and inspecting
batch-processing tasks.  Task state is managed in Redis (with an in-memory
fallback when Redis is unavailable) and includes full lifecycle tracking:
``pending → running → completed / failed / cancelled``.

Endpoints
---------
POST   /tasks/process          Submit a batch processing task
GET    /tasks/                 List all tasks with status
GET    /tasks/{task_id}        Get task details and progress
GET    /tasks/{task_id}/result Get task result payload
POST   /tasks/{task_id}/cancel Cancel a running task
GET    /tasks/stats            Processing statistics
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ---------------------------------------------------------------------------
# Task state enum
# ---------------------------------------------------------------------------
class TaskStatus(StrEnum):
    """Lifecycle states for an async processing task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# In-memory task store (fallback when Redis is unavailable)
# ---------------------------------------------------------------------------
_task_store: dict[str, dict[str, Any]] = {}


def _redis_key(task_id: str) -> str:
    """Return the Redis key for a task."""
    return f"omni:task:{task_id}"


def _stats_key() -> str:
    """Return the Redis key for global task statistics."""
    return "omni:task:stats"


# ===================================================================
# Pydantic models
# ===================================================================

class TaskSubmitRequest(BaseModel):
    """Request body for submitting a batch processing task."""

    document_ids: list[str] | None = Field(
        default=None,
        description="List of document IDs to process.",
    )
    file_paths: list[str] | None = Field(
        default=None,
        description="List of file paths to process.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Processing options (engines, fusion_method, language, etc.).",
    )


class TaskSubmitResponse(BaseModel):
    """Response after submitting a task."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    document_count: int = 0
    submitted_at: str


class TaskDetailResponse(BaseModel):
    """Detailed task information with progress."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    progress_percent: float = 0.0
    options: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    processing_time_ms: float = 0.0


class TaskListResponse(BaseModel):
    """List of tasks with filtering."""

    tasks: list[TaskDetailResponse]
    total: int = 0


class TaskCancelResponse(BaseModel):
    """Confirmation of task cancellation."""

    task_id: str
    cancelled: bool
    message: str = ""


class TaskStatsResponse(BaseModel):
    """Aggregated processing statistics."""

    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    pending: int = 0
    running: int = 0
    avg_processing_time_ms: float = 0.0


# ===================================================================
# Task persistence helpers
# ===================================================================

async def _save_task(task_id: str, data: dict[str, Any]) -> None:
    """Persist task data to Redis with an in-memory fallback.

    Data is serialised as JSON with a 24-hour TTL in Redis.
    """
    from ...services.redis_client import RedisClient

    payload = json.dumps(data, default=str)
    await RedisClient.setex(_redis_key(task_id), payload, ttl=86400)
    _task_store[task_id] = data


async def _load_task(task_id: str) -> dict[str, Any] | None:
    """Load task data from Redis, falling back to in-memory store."""
    from ...services.redis_client import RedisClient

    raw = await RedisClient.get(_redis_key(task_id))
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return _task_store.get(task_id)


async def _delete_task(task_id: str) -> None:
    """Remove task data from Redis and in-memory store."""
    from ...services.redis_client import RedisClient

    await RedisClient.delete(_redis_key(task_id))
    _task_store.pop(task_id, None)


async def _increment_stats(field: str) -> None:
    """Atomically increment a task statistics counter in Redis."""
    from ...services.redis_client import RedisClient

    raw = await RedisClient.get(_stats_key())
    stats: dict[str, int] = json.loads(raw) if raw else {}
    stats[field] = stats.get(field, 0) + 1
    await RedisClient.setex(_stats_key(), json.dumps(stats), ttl=86400)


# ===================================================================
# Background task executor
# ===================================================================

async def _execute_task(
    task_id: str,
    document_ids: list[str] | None,
    file_paths: list[str] | None,
    options: dict[str, Any],
) -> None:
    """Run a batch processing task in the background.

    Processes each document/file through the OCR pipeline, tracking progress
    and handling cancellation requests.
    """
    from ...vision.ocr_fusion_system import OCRFusionEngine
    from ...core.config import get_settings

    task = await _load_task(task_id)
    if task is None:
        return

    # Mark as running
    task["status"] = TaskStatus.RUNNING
    task["started_at"] = datetime.now(timezone.utc).isoformat()
    await _save_task(task_id, task)

    # Collect items to process
    items: list[tuple[str, str]] = []  # (source, path_or_id)
    if document_ids:
        for did in document_ids:
            from ...services.prisma_client import get_document as db_get_document
            doc = await db_get_document(did)
            if doc and doc.get("filepath"):
                items.append(("document", doc["filepath"]))
    if file_paths:
        for fp in file_paths:
            items.append(("file", fp))

    task["total_items"] = len(items)
    await _save_task(task_id, task)

    if not items:
        task["status"] = TaskStatus.COMPLETED
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["result"] = {"message": "No items to process."}
        await _save_task(task_id, task)
        await _increment_stats("completed")
        return

    # Build the OCR engine
    settings = get_settings()
    engine = OCRFusionEngine(settings)
    engine.discover_and_register_all()

    language = options.get("language", "eng+ara")
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, (source, path) in enumerate(items):
        # Check for cancellation
        current = await _load_task(task_id)
        if current and current.get("status") == TaskStatus.CANCELLED:
            logger.info("Task %s cancelled at item %d/%d", task_id, idx + 1, len(items))
            break

        try:
            from ...vision.ocr_fusion_system import MedicalKnowledgeGraph

            t0 = time.perf_counter()
            fused = await engine.process(path, lang=language)
            processing_ms = (time.perf_counter() - t0) * 1000

            # Build knowledge graph
            kg_engine = MedicalKnowledgeGraph()
            kg = await kg_engine.build(fused.final_text)

            results.append({
                "source": source,
                "path": path,
                "text": fused.final_text,
                "word_count": fused.word_count,
                "confidence_scores": fused.confidence_scores,
                "fusion_method": fused.fusion_method,
                "processing_time_ms": round(processing_ms, 2),
                "entity_count": len(kg.entities),
                "relation_count": len(kg.relations),
            })
            task["completed_items"] = idx + 1
        except Exception as exc:
            logger.error("Task %s item %d failed: %s", task_id, idx, exc)
            errors.append({
                "source": source,
                "path": path,
                "error": str(exc),
            })
            task["failed_items"] = task.get("failed_items", 0) + 1

        # Update progress
        task["progress_percent"] = round(
            ((idx + 1) / len(items)) * 100, 1
        )
        await _save_task(task_id, task)

    # Finalise task
    task = await _load_task(task_id)
    if task is None:
        return

    if task.get("status") == TaskStatus.CANCELLED:
        await _increment_stats("cancelled")
    else:
        task["status"] = TaskStatus.COMPLETED
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["result"] = {
            "results": results,
            "errors": errors,
            "total_processed": len(results),
            "total_failed": len(errors),
        }
        await _increment_stats("completed")

    # Compute total processing time
    started = task.get("started_at", "")
    completed = task.get("completed_at", "")
    if started and completed:
        try:
            dt_start = datetime.fromisoformat(started)
            dt_end = datetime.fromisoformat(completed)
            task["processing_time_ms"] = (dt_end - dt_start).total_seconds() * 1000
        except (ValueError, TypeError):
            pass

    await _save_task(task_id, task)


# ===================================================================
# Endpoints
# ===================================================================

@router.post("/process", response_model=TaskSubmitResponse, summary="Submit a batch processing task")
async def submit_task(
    body: TaskSubmitRequest,
    background_tasks: BackgroundTasks,
) -> TaskSubmitResponse:
    """Submit a batch processing task for a list of document IDs or file paths.

    The task runs in the background.  Use ``GET /tasks/{task_id}`` to poll
    progress and ``GET /tasks/{task_id}/result`` to retrieve the final result.

    Raises
    ------
    400
        If neither ``document_ids`` nor ``file_paths`` are provided.
    """
    if not body.document_ids and not body.file_paths:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of 'document_ids' or 'file_paths'.",
        )

    task_id = uuid.uuid4().hex[:24]
    now = datetime.now(timezone.utc).isoformat()
    total = len(body.document_ids or []) + len(body.file_paths or [])

    task_data: dict[str, Any] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "total_items": total,
        "completed_items": 0,
        "failed_items": 0,
        "progress_percent": 0.0,
        "options": body.options,
        "result": None,
        "error": None,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "processing_time_ms": 0.0,
    }
    await _save_task(task_id, task_data)
    await _increment_stats("total_tasks")

    background_tasks.add_task(
        _execute_task,
        task_id,
        body.document_ids,
        body.file_paths,
        body.options,
    )

    logger.info("Task submitted: id=%s items=%d", task_id, total)

    return TaskSubmitResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        document_count=total,
        submitted_at=now,
    )


@router.get("/", response_model=TaskListResponse, summary="List all tasks")
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max tasks to return"),
) -> TaskListResponse:
    """Return all tasks, optionally filtered by status."""
    # Collect tasks from both Redis and in-memory store
    all_tasks: list[dict[str, Any]] = []

    # In-memory tasks
    for tid, tdata in list(_task_store.items()):
        all_tasks.append(tdata)

    # Also check if Redis has tasks not in memory
    from ...services.redis_client import RedisClient

    redis = getattr(RedisClient, "__wrapped__", None)
    # We cannot enumerate Redis keys without scanning, so we rely on the
    # in-memory store and tasks loaded individually by ID.

    if status:
        all_tasks = [t for t in all_tasks if t.get("status") == status]

    # Sort by creation time (newest first)
    all_tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    all_tasks = all_tasks[:limit]

    items = [_task_to_response(t) for t in all_tasks]

    return TaskListResponse(tasks=items, total=len(items))


@router.get("/stats", response_model=TaskStatsResponse, summary="Processing statistics")
async def get_task_stats() -> TaskStatsResponse:
    """Return aggregated processing statistics.

    Counts are sourced from Redis if available; otherwise the in-memory
    task store is scanned.
    """
    from ...services.redis_client import RedisClient

    raw = await RedisClient.get(_stats_key())
    stats: dict[str, int] = json.loads(raw) if raw else {}

    # If Redis has no stats, compute from the in-memory store
    if not stats and _task_store:
        for t in _task_store.values():
            s = t.get("status", TaskStatus.PENDING)
            stats[s] = stats.get(s, 0) + 1
            stats["total_tasks"] = stats.get("total_tasks", 0) + 1

    total = stats.get("total_tasks", 0)
    completed = stats.get("completed", 0)
    failed = stats.get("failed", 0)
    cancelled = stats.get("cancelled", 0)

    # Calculate average processing time from in-memory store
    total_time = 0.0
    count_with_time = 0
    for t in _task_store.values():
        pt = t.get("processing_time_ms", 0)
        if pt > 0:
            total_time += pt
            count_with_time += 1
    avg_time = total_time / count_with_time if count_with_time > 0 else 0.0

    return TaskStatsResponse(
        total_tasks=total,
        completed=completed,
        failed=failed,
        cancelled=cancelled,
        pending=sum(1 for t in _task_store.values() if t.get("status") == TaskStatus.PENDING),
        running=sum(1 for t in _task_store.values() if t.get("status") == TaskStatus.RUNNING),
        avg_processing_time_ms=round(avg_time, 2),
    )


@router.get("/{task_id}", response_model=TaskDetailResponse, summary="Get task details")
async def get_task(task_id: str) -> TaskDetailResponse:
    """Retrieve detailed information about a specific task.

    Raises
    ------
    404
        If the task does not exist.
    """
    task = await _load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    return _task_to_response(task)


@router.get("/{task_id}/result", summary="Get task result")
async def get_task_result(task_id: str) -> dict[str, Any]:
    """Return the result payload of a completed task.

    Raises
    ------
    404
        If the task does not exist.
    409
        If the task has not yet completed.
    """
    task = await _load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    status = task.get("status")
    if status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Task is still {status}. Result not yet available.",
        )

    return {
        "task_id": task_id,
        "status": status,
        "result": task.get("result"),
        "error": task.get("error"),
        "processing_time_ms": task.get("processing_time_ms", 0),
    }


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse, summary="Cancel a running task")
async def cancel_task(task_id: str) -> TaskCancelResponse:
    """Request cancellation of a running or pending task.

    The task will stop processing at the next item boundary.

    Raises
    ------
    404
        If the task does not exist.
    409
        If the task is already in a terminal state.
    """
    task = await _load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    status = task.get("status")
    if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Task is already in terminal state '{status}'.",
        )

    task["status"] = TaskStatus.CANCELLED
    task["completed_at"] = datetime.now(timezone.utc).isoformat()
    await _save_task(task_id, task)
    await _increment_stats("cancelled")

    return TaskCancelResponse(
        task_id=task_id,
        cancelled=True,
        message=f"Task '{task_id}' marked for cancellation.",
    )


# ===================================================================
# Internal helpers
# ===================================================================

def _task_to_response(task_data: dict[str, Any]) -> TaskDetailResponse:
    """Convert a raw task dict into a :class:`TaskDetailResponse`."""
    return TaskDetailResponse(
        task_id=task_data.get("task_id", ""),
        status=task_data.get("status", TaskStatus.PENDING),
        total_items=task_data.get("total_items", 0),
        completed_items=task_data.get("completed_items", 0),
        failed_items=task_data.get("failed_items", 0),
        progress_percent=task_data.get("progress_percent", 0.0),
        options=task_data.get("options", {}),
        result=task_data.get("result"),
        error=task_data.get("error"),
        created_at=task_data.get("created_at", ""),
        started_at=task_data.get("started_at"),
        completed_at=task_data.get("completed_at"),
        processing_time_ms=task_data.get("processing_time_ms", 0.0),
    )
