from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_dockerfile_validates_repository_entrypoint():
    text = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    assert "RUN test -f /app/entrypoint.sh" in text
    assert "chmod 0755 /app/entrypoint.sh" in text
    assert 'ENTRYPOINT ["/app/entrypoint.sh"]' in text
    assert "docker-entrypoint.sh" not in text
