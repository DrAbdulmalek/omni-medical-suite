from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_specialty_installer_is_pinned_and_uses_published_asset():
    script = (ROOT / "scripts" / "setup_dictionaries.sh").read_text(encoding="utf-8")
    assert 'TAG="${1:-malek-dictionaries-v1}"' in script
    assert 'ARCHIVE="malek-specialty-dictionaries.tar.gz"' in script
    assert "EXPECTED_V1_SHA256=\"377f65f33d52df03a44dd759ac3cb145f22718dd446fd6e5cba4f14278c78820\"" in script
    assert 'sha256sum "$TMP_ARCHIVE"' in script
    assert 'tar xzf "$TMP_ARCHIVE" -C "$EXTRACT_DIR"' in script


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


def test_docker_context_keeps_specialty_json_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "data/*" in dockerignore
    assert "!data/dictionaries/" in dockerignore
    assert "!data/dictionaries/specialty/" in dockerignore
    assert "!data/dictionaries/specialty/*.json" in dockerignore


def test_cd_builds_canonical_api_image_after_installing_tm():
    cd = (ROOT / ".github" / "workflows" / "cd.yml").read_text(encoding="utf-8")
    install = cd.index("bash scripts/setup_dictionaries.sh malek-dictionaries-v1")
    docker = cd.index("docker/build-push-action@v5")
    assert install < docker
    assert "file: deploy/Dockerfile.api" in cd
    assert "kubectl apply -f k8s/" not in cd


def test_production_dockerfile_copies_repository_data():
    dockerfile = (ROOT / "deploy" / "Dockerfile.api").read_text(encoding="utf-8")
    assert "COPY . ." in dockerfile
