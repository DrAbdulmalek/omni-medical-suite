"""
Setup script for Omni Medical OCR Pipeline.

Usage:
    pip install .                # install in editable mode
    pip install -e .             # editable (development) install
    python setup.py sdist bdist_wheel   # build distributions
"""

from pathlib import Path

from setuptools import find_packages, setup

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent.resolve()

# Read the long description from README if present
_readme_path = HERE / "README.md"
LONG_DESCRIPTION = _readme_path.read_text(encoding="utf-8") if _readme_path.exists() else ""

# Read version from src/__init__.py
_init_path = HERE / "src" / "__init__.py"
_version = "0.1.0"
if _init_path.exists():
    for line in _init_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            _version = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

# ---------------------------------------------------------------------------
# Requirements (mirrors requirements.txt for pip install)
# ---------------------------------------------------------------------------

REQUIRED = [
    # Core ML / OCR
    "torch>=2.0.0,<3.0.0",
    "transformers>=4.36.0",
    "pytesseract>=0.3.10",
    "easyocr>=1.7.0",
    "paddleocr>=2.7.0",
    "paddlepaddle>=2.5.0",
    # Image processing
    "opencv-python-headless>=4.8.0",
    "Pillow>=10.0.0",
    "numpy>=1.24.0,<2.0.0",
    # PDF handling
    "PyMuPDF>=1.23.0",
    "pdf2image>=1.16.0",
    # Arabic text
    "arabic-reshaper>=3.0.0",
    "python-bidi>=0.4.2",
    # Spell checking
    "python-Levenshtein>=0.21.0",
    # Web UI
    "gradio>=4.0.0",
    # API
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    # Config
    "PyYAML>=6.0.1",
]

EXTRAS = {
    "llm": [
        # Uncomment one or both LLM backends for spell-check fallback:
        # "jais>=1.0.0",
        # "instructlab>=0.1.0",
    ],
    "translate": [
        "deep-translator>=1.11.0",
    ],
    "dev": [
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "black>=23.0.0",
        "isort>=5.12.0",
        "mypy>=1.7.0",
        "ruff>=0.1.0",
    ],
    "all": [],   # populated below
}
# "all" extra = union of everything
EXTRAS["all"] = list({pkg for group in EXTRAS.values() for pkg in group})

# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

ENTRY_POINTS = {
    "console_scripts": [
        "omni-medical-ocr=src.cli:main",
    ],
}

# ---------------------------------------------------------------------------
# Setup call
# ---------------------------------------------------------------------------

setup(
    name="omni-medical-ocr-pipeline",
    version=_version,
    description="Comprehensive Arabic medical OCR pipeline with multi-engine fusion",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="DrAbdulmalek",
    author_email="drmohammedabdulmalek@gmail.com",
    url="https://github.com/DrAbdulmalek/omni-medical-ocr-pipeline",
    license="MIT",
    license_files=["LICENSE"],

    # Package discovery
    packages=find_packages(where=".", include=["src*", "config*"]),
    package_dir={"": "."},

    python_requires=">=3.10",

    install_requires=REQUIRED,
    extras_require=EXTRAS,
    entry_points=ENTRY_POINTS,

    # Classifiers (PyPI)
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Arabic",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Text Processing :: Optical Character Recognition",
    ],

    keywords=[
        "ocr", "arabic", "medical", "tesseract", "easyocr", "paddleocr",
        "trocr", "prescription", "handwriting", "spell-checking",
        "deep-learning", "computer-vision",
    ],

    # Include non-Python files (config templates, dictionaries, etc.)
    package_data={
        "src": ["**/*.yaml", "**/*.json", "**/*.txt"],
        "config": ["**/*.yaml", "**/*.json"],
    },
    include_package_data=True,

    zip_safe=False,
)
