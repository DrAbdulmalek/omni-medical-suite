import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_specialty_installer_is_pinned_and_uses_published_asset():
    script = (ROOT / "scripts" / "setup_dictionaries.sh").read_text(encoding="utf-8")
    assert 'TAG="${1:-malek-dictionaries-v2}"' in script
    assert 'ARCHIVE="malek-specialty-dictionaries.tar.gz"' in script
    assert "EXPECTED_SHA256=\"dfb3167b3f05f35f955d70741d5917a8c6f34ac590c92090358e127e351cecd2\"" in script
    assert 'sha256sum "$TMP_ARCHIVE"' in script
    assert "tar" in script and "TMP_ARCHIVE" in script
    assert 'tar --no-same-owner --no-same-permissions -xzf "$TMP_ARCHIVE" -C "$EXTRACT_DIR"' in script


def test_specialty_installer_rejects_deprecated_v1_tag():
    """v1 is a known-insecure artifact and must be refused before download."""
    script = ROOT / "scripts" / "setup_dictionaries.sh"
    result = subprocess.run(
        ["bash", str(script), "malek-dictionaries-v1"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "deprecated" in result.stderr.lower()
    assert "policy-violating" in result.stderr.lower()

    source = script.read_text(encoding="utf-8")
    assert "377f65f33d52df03a44dd759ac3cb145f22718dd446fd6e5cba4f14278c78820" not in source


def test_specialty_installer_rejects_unpinned_release_tags():
    script = ROOT / "scripts" / "setup_dictionaries.sh"
    result = subprocess.run(
        ["bash", str(script), "malek-dictionaries-unknown"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "no pinned sha-256 is registered" in result.stderr.lower()

    source = script.read_text(encoding="utf-8")
    assert 'case "$TAG" in' in source
    assert "No pinned SHA-256 is registered" in source
    assert "*)" in source


def test_specialty_installer_validates_every_published_artifact():
    script = (ROOT / "scripts" / "setup_dictionaries.sh").read_text(encoding="utf-8")
    for name in (
        "orthopedic_surgery.json",
        "anatomy.json",
        "general_medical.json",
        "surgery_general.json",
        "cardiovascular.json",
        "oncology.json",
        "abdomen_pelvis.json",
        "endocrinology.json",
        "_summary.json",
        "_quarantined.json",
        "_monolingual_corpus.json",
        "_hashes.json",
    ):
        assert name in script


def test_specialty_installer_does_not_assume_archive_directory_prefix():
    script = (ROOT / "scripts" / "setup_dictionaries.sh").read_text(encoding="utf-8")
    assert 'find "$EXTRACT_DIR" -type d -print' in script
    assert 'FOUND_SPECIALTY_DIR="$candidate"' in script
    assert '[ -L "$candidate/$file" ]' in script
    assert "complete expected specialty artifact set" in script


def test_specialty_installer_rejects_unsafe_archive_member_paths():
    script = (ROOT / "scripts" / "setup_dictionaries.sh").read_text(encoding="utf-8")
    assert "unsafe path" in script.lower()
    assert 'member="${member#./}"' in script
    assert '"$member" = /*' in script
    assert '"$member" == ../*' in script
    assert '"$member" == */../*' in script
    assert "Archive contains an unsafe path" in script
    assert "tar" in script and "TMP_ARCHIVE" in script


def test_docker_context_keeps_specialty_json_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "data/*" in dockerignore
    assert "!data/dictionaries/" in dockerignore
    assert "!data/dictionaries/specialty/" in dockerignore
    assert "!data/dictionaries/specialty/*.json" in dockerignore


def test_cd_builds_canonical_api_image_after_installing_tm():
    cd = (ROOT / ".github" / "workflows" / "cd.yml").read_text(encoding="utf-8")
    install = cd.index("bash scripts/setup_dictionaries.sh malek-dictionaries-v2")
    docker = cd.index("docker/build-push-action@v5")
    assert install < docker
    assert "file: deploy/Dockerfile.api" in cd
    assert not any(
        "kubectl apply -f k8s/" in line and not line.lstrip().startswith("#")
        for line in cd.splitlines()
    )


def test_ci_workflows_rotate_off_v1():
    """All CI workflows that invoke the installer must call v2, not v1."""
    for wf_name in ("cd.yml", "docker.yml", "release.yml"):
        wf = (ROOT / ".github" / "workflows" / wf_name).read_text(encoding="utf-8")
        assert "bash scripts/setup_dictionaries.sh malek-dictionaries-v2" in wf, (
            f"{wf_name} must call installer with malek-dictionaries-v2"
        )
        assert "bash scripts/setup_dictionaries.sh malek-dictionaries-v1" not in wf, (
            f"{wf_name} must NOT call installer with deprecated malek-dictionaries-v1"
        )


def test_release_builds_same_canonical_api_image():
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "file: deploy/Dockerfile.api" in release
    assert "file: Dockerfile.api" not in release


def test_production_dockerfile_copies_repository_data():
    dockerfile = (ROOT / "deploy" / "Dockerfile.api").read_text(encoding="utf-8")
    assert "COPY . ." in dockerfile


# ─── Behavioral archive contract test ────────────────────────────────────
# Tests the actual published artifact, not just text in the installer.
# Downloads the v2 asset from GitHub at test time. Skips if no network.

import hashlib
import tarfile
import urllib.request
from pathlib import Path

import pytest


V2_PUBLISHED_SHA256 = "dfb3167b3f05f35f955d70741d5917a8c6f34ac590c92090358e127e351cecd2"
V2_DOWNLOAD_URL = (
    "https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/"
    "malek-dictionaries-v2/malek-specialty-dictionaries.tar.gz"
)
EXPECTED_FILES = {
    "orthopedic_surgery.json",
    "anatomy.json",
    "general_medical.json",
    "surgery_general.json",
    "cardiovascular.json",
    "oncology.json",
    "abdomen_pelvis.json",
    "endocrinology.json",
    "_summary.json",
    "_quarantined.json",
    "_monolingual_corpus.json",
    "_hashes.json",
}


@pytest.fixture(scope="module")
def downloaded_v2_archive(tmp_path_factory):
    """Download the published v2 archive once per test session.

    Skips the test if no network access is available.
    """
    target = tmp_path_factory.mktemp("v2-archive") / "malek-specialty-dictionaries.tar.gz"
    try:
        urllib.request.urlretrieve(V2_DOWNLOAD_URL, target)
    except Exception as exc:
        pytest.skip(f"Cannot download published v2 archive: {exc}")
    return target


def test_published_v2_archive_matches_pinned_sha256(downloaded_v2_archive):
    """The downloaded asset's SHA-256 must match the SHA pinned in the installer."""
    actual = hashlib.sha256(downloaded_v2_archive.read_bytes()).hexdigest()
    assert actual == V2_PUBLISHED_SHA256, (
        f"Published v2 SHA drifted from installer pin.\n"
        f"  expected: {V2_PUBLISHED_SHA256}\n"
        f"  actual:   {actual}"
    )


def test_published_v2_archive_member_paths_are_safe(downloaded_v2_archive, tmp_path):
    """No absolute paths, no `..` traversal."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            assert not m.name.startswith("/"), f"Absolute path: {m.name}"
            assert ".." not in Path(m.name).parts, f"Traversal: {m.name}"


def test_published_v2_archive_has_no_symlinks_or_hardlinks(downloaded_v2_archive):
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            assert not m.issym(), f"Symlink: {m.name}"
            assert not m.islnk(), f"Hardlink: {m.name}"


def test_published_v2_archive_has_no_fifo_or_device(downloaded_v2_archive):
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            assert not m.isfifo(), f"FIFO: {m.name}"
            assert not m.ischr(), f"Char device: {m.name}"
            assert not m.isblk(), f"Block device: {m.name}"


def test_published_v2_archive_has_no_duplicate_members(downloaded_v2_archive):
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        names = [m.name for m in tar.getmembers()]
    assert len(names) == len(set(names)), "Duplicate members found"


def test_published_v2_archive_files_are_0644(downloaded_v2_archive):
    """All regular files must be mode 0644 — no executable data files."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            if m.isfile():
                assert (m.mode & 0o7777) == 0o644, (
                    f"Bad file mode for {m.name}: {oct(m.mode)} (expected 0644)"
                )


def test_published_v2_archive_directories_are_0755(downloaded_v2_archive):
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            if m.isdir():
                assert (m.mode & 0o7777) == 0o755, (
                    f"Bad dir mode for {m.name}: {oct(m.mode)} (expected 0755)"
                )


def test_published_v2_archive_has_no_executable_regular_files(downloaded_v2_archive):
    """Specifically the file that broke v1: endocrinology.json + 11 others."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            if m.isfile():
                assert not (m.mode & 0o111), (
                    f"Executable regular file: {m.name} (mode={oct(m.mode)})"
                )


def test_published_v2_archive_has_no_gitkeep(downloaded_v2_archive):
    """The `.gitkeep` file was a policy violation in v1; v2 must not carry it."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            assert m.name != ".gitkeep", ".gitkeep must not be in v2 archive"
            assert not m.name.endswith("/.gitkeep"), (
                f".gitkeep must not appear anywhere in v2 archive: {m.name}"
            )


def test_published_v2_archive_has_expected_file_set(downloaded_v2_archive):
    """All 12 expected JSON files must be present, with no extras."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        found = {Path(m.name).name for m in tar.getmembers() if m.isfile()}
    missing = EXPECTED_FILES - found
    extra = found - EXPECTED_FILES
    assert not missing, f"Missing expected files: {sorted(missing)}"
    assert not extra, f"Unexpected files in archive: {sorted(extra)}"


def test_published_v2_archive_has_normalized_ownership(downloaded_v2_archive):
    """All members must be uid=0, gid=0, uname=root, gname=root."""
    with tarfile.open(downloaded_v2_archive, "r:gz") as tar:
        for m in tar.getmembers():
            assert (m.uid, m.gid, m.uname, m.gname) == (0, 0, "root", "root"), (
                f"Non-normalized ownership for {m.name}: "
                f"uid={m.uid} gid={m.gid} uname={m.uname} gname={m.gname}"
            )
