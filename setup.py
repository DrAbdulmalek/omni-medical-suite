from setuptools import setup, find_packages

setup(
    name="bilingual-extractor",
    version="1.0.0",
    description="Arabic-English Medical Parallel Corpus Extraction System",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="BilingualExtractor Team",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "sentence-transformers>=2.2.0",
        "scipy>=1.9.0",
        "pandas>=1.5.0",
        "openpyxl>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
        ],
        "gpu": [
            "torch>=2.0.0",
            "transformers>=4.25.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "bilingual-extract=term_extractor.term_extractor:main",
        ],
    },
)
