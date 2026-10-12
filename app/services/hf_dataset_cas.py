"""Compare-and-swap writer for the existing single-shard HF dataset.

The exporter fails closed unless the verified revision contains exactly one
file below data/, and that file is a supported Parquet shard. Unknown extensions,
multi-shard layouts, and non-Parquet layouts are rejected rather than silently
ignored.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


def get_verified_dataset_baseline(api: Any, *, repo_id: str, token: str) -> tuple[str, str]:
    """Return (commit SHA, sole Parquet data path) from one verified Hub revision.

    The caller must load the dataset using the returned exact SHA before
    constructing a replacement snapshot.
    """
    info = api.dataset_info(repo_id=repo_id, repo_type="dataset", token=token)
    revision = getattr(info, "sha", None)
    if not isinstance(revision, str) or len(revision) != 40:
        raise RuntimeError("HF CAS refused: remote dataset revision is unavailable")

    entries = api.list_repo_tree(
        repo_id=repo_id,
        repo_type="dataset",
        revision=revision,
        recursive=True,
        token=token,
    )
    # Count every file below data/, not just extensions we already recognize.
    # Otherwise an unknown payload (for example .bin) could evade layout checks.
    paths = []
    for entry in entries:
        path = str(getattr(entry, "path", ""))
        if not path.startswith("data/"):
            continue
        entry_type = getattr(entry, "type", None)
        if entry_type == "directory":
            continue
        paths.append(path)

    if len(paths) != 1 or Path(paths[0]).suffix.lower() != ".parquet":
        raise RuntimeError(
            "HF CAS refused: expected exactly one Parquet data file under data/; "
            "remote dataset layout is multi-file or unsupported"
        )
    return revision, paths[0]


def push_parquet_snapshot_with_cas(
    api: Any,
    dataset: Any,
    *,
    repo_id: str,
    token: str,
    parent_commit: str,
    data_path: str,
    operation_factory: Any = None,
) -> Any:
    """Replace the known single Parquet shard only if the remote head is unchanged.

    parent_commit is the exact revision from which the caller loaded the
    baseline dataset. The Hub rejects the commit if the target revision moved.
    No retry is performed here: a conflict requires a fresh read, re-dedup, and
    a new explicitly reviewed attempt.
    """
    if not isinstance(parent_commit, str) or len(parent_commit) != 40:
        raise RuntimeError("HF CAS refused: baseline commit SHA is invalid")
    if not data_path.startswith("data/") or Path(data_path).suffix.lower() != ".parquet":
        raise RuntimeError("HF CAS refused: data path is not a supported Parquet shard")

    if operation_factory is None:
        from huggingface_hub import CommitOperationAdd
        operation_factory = CommitOperationAdd

    with tempfile.TemporaryDirectory(prefix="omni-hf-cas-") as temp_dir:
        parquet_path = Path(temp_dir) / "snapshot.parquet"
        dataset.to_parquet(str(parquet_path))
        operation = operation_factory(path_in_repo=data_path, path_or_fileobj=str(parquet_path))
        return api.create_commit(
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
            revision="main",
            parent_commit=parent_commit,
            commit_message="Append approved OCR corrections (CAS-protected snapshot)",
            operations=[operation],
        )
