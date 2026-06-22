"""System resource monitoring for OmniMedicalSuite.

Collects CPU, memory, disk, optional GPU, and internet-connectivity
information into a single :class:`SystemResources` dataclass that can be
serialised for API responses or used to gate heavy workloads.
"""

from __future__ import annotations

import logging
import socket
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import psutil

__all__ = [
    "SystemResources",
    "get_system_resources",
    "format_resources",
    "is_resource_sufficient",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPU detection (optional – torch is a heavy dependency)
# ---------------------------------------------------------------------------
_torch_available = False
_torch_cuda = None

try:
    import torch  # type: ignore[import-untyped]

    _torch_available = True
    _torch_cuda = torch.cuda
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class SystemResources:
    """Snapshot of system resource utilisation."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    gpu_available: bool = False
    gpu_name: str | None = None
    gpu_memory_mb: int | None = None
    gpu_memory_used_mb: int | None = None
    internet_available: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------
def _collect_cpu() -> float:
    """Return CPU utilisation as a percentage (0–100)."""
    return psutil.cpu_percent(interval=0.5)


def _collect_memory() -> tuple[float, float, float, float]:
    """Return ``(percent, used_gb, total_gb)``."""
    mem = psutil.virtual_memory()
    return mem.percent, mem.used / (1024**3), mem.total / (1024**3)


def _collect_disk() -> tuple[float, float]:
    """Return ``(used_gb, total_gb)`` for the root partition."""
    try:
        usage = shutil.disk_usage("/")
        return usage.used / (1024**3), usage.total / (1024**3)
    except Exception as exc:
        logger.warning("Failed to collect disk usage: %s", exc)
        return 0.0, 0.0


def _collect_gpu() -> tuple[bool, str | None, int | None, int | None]:
    """Return ``(available, name, memory_mb, memory_used_mb)``."""
    if not _torch_available or _torch_cuda is None:
        return False, None, None, None
    try:
        if not _torch_cuda.is_available():
            return False, None, None, None
        device_name: str = _torch_cuda.get_device_name(0)
        total_mem: int = _torch_cuda.get_device_properties(0).total_mem // (1024**2)
        # Force a synchronised memory query for used memory
        _torch_cuda.synchronize()
        allocated: int = _torch_cuda.memory_allocated(0) // (1024**2)
        return True, device_name, total_mem, allocated
    except Exception as exc:
        logger.warning("GPU detection failed: %s", exc)
        return False, None, None, None


def _check_internet() -> bool:
    """Attempt a lightweight TCP connection to check internet reachability."""
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3):
            return True
    except (OSError, socket.timeout):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_system_resources() -> SystemResources:
    """Collect and return a fresh :class:`SystemResources` snapshot."""
    cpu = _collect_cpu()
    mem_pct, mem_used, mem_total = _collect_memory()
    disk_used, disk_total = _collect_disk()
    gpu_avail, gpu_name, gpu_mem, gpu_mem_used = _collect_gpu()
    internet = _check_internet()

    return SystemResources(
        cpu_percent=round(cpu, 1),
        memory_percent=round(mem_pct, 1),
        memory_used_gb=round(mem_used, 2),
        memory_total_gb=round(mem_total, 2),
        disk_used_gb=round(disk_used, 2),
        disk_total_gb=round(disk_total, 2),
        gpu_available=gpu_avail,
        gpu_name=gpu_name,
        gpu_memory_mb=gpu_mem,
        gpu_memory_used_mb=gpu_mem_used,
        internet_available=internet,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def format_resources(resources: SystemResources) -> dict[str, object]:
    """Convert a :class:`SystemResources` to a plain dict suitable for JSON."""
    return asdict(resources)


def is_resource_sufficient(
    requirements: dict[str, float],
) -> tuple[bool, list[str]]:
    """Check whether current resources satisfy *requirements*.

    Parameters
    ----------
    requirements:
        Mapping of requirement name → threshold.  Supported keys:

        - ``cpu_percent_max`` – maximum allowed CPU utilisation (default 90)
        - ``memory_percent_max`` – maximum allowed memory utilisation (default 90)
        - ``disk_free_gb_min`` – minimum free disk space in GB (default 1)
        - ``gpu_required`` – whether a GPU is mandatory (default 0 → False)

    Returns
    -------
    tuple[bool, list[str]]
        ``(sufficient, violations)`` where *violations* is a list of
        human-readable messages describing each failed requirement.
    """
    resources = get_system_resources()
    violations: list[str] = []

    cpu_max = requirements.get("cpu_percent_max", 90.0)
    if resources.cpu_percent > cpu_max:
        violations.append(
            f"CPU usage {resources.cpu_percent}% exceeds limit of {cpu_max}%"
        )

    mem_max = requirements.get("memory_percent_max", 90.0)
    if resources.memory_percent > mem_max:
        violations.append(
            f"Memory usage {resources.memory_percent}% exceeds limit of {mem_max}%"
        )

    disk_free_min = requirements.get("disk_free_gb_min", 1.0)
    disk_free = resources.disk_total_gb - resources.disk_used_gb
    if disk_free < disk_free_min:
        violations.append(
            f"Free disk space {disk_free:.2f} GB is below minimum {disk_free_min} GB"
        )

    gpu_required = bool(requirements.get("gpu_required", 0))
    if gpu_required and not resources.gpu_available:
        violations.append("GPU is required but not available")

    return len(violations) == 0, violations
