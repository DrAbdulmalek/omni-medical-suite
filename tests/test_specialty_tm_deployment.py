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
