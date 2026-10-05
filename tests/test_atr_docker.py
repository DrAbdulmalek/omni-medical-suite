"""ATR-F2 — اختبارات Docker (STRUCTURE_ONLY).

docker غير متوفر في بيئة الاختبار → التحقق بنيوي ساكن فقط:
سلامة YAML، عناصر Dockerfile المطلوبة، الإقصاءات، ومتطلبات ATR.
حالة المرحلة: PARTIALLY PROVEN (ملفات مكتملة غير مبنية).
"""
from __future__ import annotations

from pathlib import Path

import pytest

# حارس CI (ATR-04d): yaml متاح عادةً، لكن الحارس يمنع collection error في أي
# بيئة تفتقده — اختبارات بنيوية ساكنة بلا تبعيات ثقيلة أخرى.
yaml = pytest.importorskip("yaml", reason="docker-compose validation requires pyyaml")

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE = REPO_ROOT / "docker-compose.atr.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile.atr"
DOCKERIGNORE = REPO_ROOT / "Dockerfile.atr.dockerignore"
REQUIREMENTS = REPO_ROOT / "requirements-atr.txt"


# ---------------------------------------------------------------------------
# docker-compose.atr.yml
# ---------------------------------------------------------------------------
def test_compose_is_valid_yaml():
    assert COMPOSE.exists(), "docker-compose.atr.yml مفقود"
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "services" in data


def test_compose_services_and_ports():
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = data["services"]
    assert "correction-server" in services
    assert "training-ui" in services

    cs = services["correction-server"]
    assert "5000:5000" in cs["ports"]
    assert cs["restart"] == "unless-stopped"
    assert cs["build"]["dockerfile"] == "Dockerfile.atr"
    assert "./output:/app/output" in cs["volumes"]

    tu = services["training-ui"]
    assert "5001:5001" in tu["ports"]
    assert tu["restart"] == "unless-stopped"
    volumes = tu["volumes"]
    assert "./output:/app/output" in volumes
    assert "./models:/app/models" in volumes


def test_compose_gpu_section_is_optional_and_documented():
    raw = COMPOSE.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    devices = (data["services"]["training-ui"]
               ["deploy"]["resources"]["reservations"]["devices"])
    assert devices[0]["driver"] == "nvidia"
    assert devices[0]["capabilities"] == ["gpu"]
    # التعليق الإرشادي لحذف القسم بلا GPU (نص عربي صريح)
    assert "احذف قسم deploy" in raw
    # خدمة التصحيح لا تحمل قسم GPU
    assert "deploy" not in data["services"]["correction-server"]


def test_compose_does_not_shadow_root_compose():
    """ملف المنظومة الجذري docker-compose.yml يبقى موجودًا وغير مستبدل."""
    root_compose = REPO_ROOT / "docker-compose.yml"
    assert root_compose.exists()
    assert root_compose.resolve() != COMPOSE.resolve()


# ---------------------------------------------------------------------------
# Dockerfile.atr
# ---------------------------------------------------------------------------
def test_dockerfile_required_elements():
    assert DOCKERFILE.exists(), "Dockerfile.atr مفقود"
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM python:3.10-slim" in text
    assert "EXPOSE 5000 5001" in text
    # متطلبات النظام — libgl1 (بديل libgl1-mesa-glx في bookworm، انحراف موثق)
    assert "libgl1" in text
    assert "libglib2.0-0" in text
    assert "poppler-utils" in text
    # المتطلبات قبل الكود (طبقة cache)
    assert "COPY requirements-atr.txt" in text
    assert "COPY ahw/ ./ahw/" in text
    assert text.index("requirements-atr.txt") < text.index("COPY ahw/")
    # CMD افتراضي = خادم التصحيح على 5000
    assert "correction_server.py" in text
    assert text.strip().splitlines()[-1].startswith("CMD")


def test_dockerfile_root_untouched():
    root_dockerfile = REPO_ROOT / "Dockerfile"
    assert root_dockerfile.exists()
    assert root_dockerfile.resolve() != DOCKERFILE.resolve()


# ---------------------------------------------------------------------------
# .dockerignore sidecar + requirements-atr.txt
# ---------------------------------------------------------------------------
def test_dockerignore_covers_required_patterns():
    assert DOCKERIGNORE.exists(), "Dockerfile.atr.dockerignore مفقود"
    lines = {ln.strip() for ln in
             DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")}
    for pattern in ("output/", "models/", ".git/", ".secrets/", "*.pdf",
                    "batch_*/", "node_modules/"):
        assert pattern in lines, f"النمط {pattern} ناقص من الإقصاءات"


def test_requirements_atr_present_with_key_deps():
    assert REQUIREMENTS.exists()
    text = REQUIREMENTS.read_text(encoding="utf-8").lower()
    for dep in ("torch", "transformers", "flask", "flask-socketio",
                "pymupdf", "pandas", "openpyxl", "jiwer",
                "opencv-python-headless"):
        assert dep in text, f"{dep} ناقص من requirements-atr.txt"
    # ATR-04c: pin صار محايد الإصدار (dual-evidence 4.57.6 + 5.12.1) — لا <5 cap.
    # نتحقق أن التوثيق مزدوج-الدليل موجود بدل الـcap القديم.
    assert "dual-evidence" in text or "4.57.6" in text or "5.12.1" in text, \
        "requirements-atr.txt يجب أن يوثّق دليل الإصدارين (ATR-04c)"


@pytest.mark.parametrize("path", [COMPOSE, DOCKERFILE, DOCKERIGNORE,
                                  REQUIREMENTS])
def test_atr_docker_files_are_new_not_overwrites(path):
    """كل ملفات F2 جديدة بأسماء ATR — لا استبدال لأي ملف منظومة قائم."""
    assert path.name.endswith((".atr", "-atr.txt", "Dockerfile.atr",
                               "docker-compose.atr.yml")) or \
        path.name in ("Dockerfile.atr", "docker-compose.atr.yml",
                      "Dockerfile.atr.dockerignore", "requirements-atr.txt")
