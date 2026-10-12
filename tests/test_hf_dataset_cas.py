"""Offline tests for compare-and-swap HF dataset writes."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.hf_dataset_cas import (
    get_verified_dataset_baseline,
    push_parquet_snapshot_with_cas,
)


class FakeEntry:
    def __init__(self, path: str):
        self.path = path


class FakeAPI:
    def __init__(self, paths=None, sha="a" * 40, commit_error=None):
        self.paths = paths if paths is not None else ["data/train-00000-of-00001.parquet"]
        self.sha = sha
        self.commit_error = commit_error
        self.commit_kwargs = None

    def dataset_info(self, **kwargs):
        return SimpleNamespace(sha=self.sha)

    def list_repo_tree(self, **kwargs):
        assert kwargs["revision"] == self.sha
        return [FakeEntry(path) for path in self.paths]

    def create_commit(self, **kwargs):
        self.commit_kwargs = kwargs
        if self.commit_error:
            raise self.commit_error
        return SimpleNamespace(oid="b" * 40)


def test_baseline_is_pinned_to_one_supported_parquet_file():
    api = FakeAPI()
    sha, path = get_verified_dataset_baseline(
        api, repo_id="owner/dataset", token="test-token"
    )
    assert sha == "a" * 40
    assert path == "data/train-00000-of-00001.parquet"


@pytest.mark.parametrize(
    "paths",
    [
        [],
        ["data/train-00000-of-00001.parquet", "data/train-00001-of-00002.parquet"],
        ["data/train.csv"],
    ],
)
def test_unknown_or_multifile_layout_fails_closed(paths):
    api = FakeAPI(paths=paths)
    with pytest.raises(RuntimeError, match="layout"):
        get_verified_dataset_baseline(api, repo_id="owner/dataset", token="test-token")


def test_missing_remote_sha_fails_closed():
    api = FakeAPI(sha=None)
    with pytest.raises(RuntimeError, match="revision"):
        get_verified_dataset_baseline(api, repo_id="owner/dataset", token="test-token")


def test_commit_uses_exact_parent_commit_and_preserves_target_path():
    api = FakeAPI()
    captured = {}

    class FakeDataset:
        def to_parquet(self, path):
            Path(path).write_bytes(b"mock parquet bytes")

    def fake_operation_factory(*, path_in_repo, path_or_fileobj):
        captured["operation"] = (path_in_repo, Path(path_or_fileobj).read_bytes())
        return SimpleNamespace(path_in_repo=path_in_repo)

    result = push_parquet_snapshot_with_cas(
        api,
        FakeDataset(),
        repo_id="owner/dataset",
        token="test-token",
        parent_commit="a" * 40,
        data_path="data/train-00000-of-00001.parquet",
        operation_factory=fake_operation_factory,
    )

    assert result.oid == "b" * 40
    assert api.commit_kwargs["parent_commit"] == "a" * 40
    assert api.commit_kwargs["revision"] == "main"
    assert api.commit_kwargs["repo_type"] == "dataset"
    assert captured["operation"] == (
        "data/train-00000-of-00001.parquet",
        b"mock parquet bytes",
    )


def test_stale_parent_conflict_is_propagated_without_retry():
    conflict = RuntimeError("parent commit mismatch: remote head advanced")
    api = FakeAPI(commit_error=conflict)

    class FakeDataset:
        def to_parquet(self, path):
            Path(path).write_bytes(b"mock parquet bytes")

    with pytest.raises(RuntimeError, match="remote head advanced"):
        push_parquet_snapshot_with_cas(
            api,
            FakeDataset(),
            repo_id="owner/dataset",
            token="test-token",
            parent_commit="a" * 40,
            data_path="data/train-00000-of-00001.parquet",
            operation_factory=lambda **kwargs: SimpleNamespace(**kwargs),
        )
    assert api.commit_kwargs["parent_commit"] == "a" * 40
