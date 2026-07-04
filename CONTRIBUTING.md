# Contributing to Omni Medical Suite

Thank you for your interest in contributing to the Omni Medical Suite! This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Version Compatibility](#version-compatibility)
- [Testing](#testing)
- [Docker Development](#docker-development)
- [Pull Request Process](#pull-request-process)
- [Commit Convention](#commit-convention)
- [Release Process](#release-process)

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/omni-medical-suite.git
   cd omni-medical-suite
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```
4. **Make your changes**
5. **Test** your changes (see [Testing](#testing))
6. **Commit** with conventional commit message
7. **Push** to your fork
8. **Open a Pull Request** using our PR template

## Development Setup

### Prerequisites

- Python 3.11+
- Docker (optional, for containerized development)
- Git

### Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install with version constraints
pip install --upgrade pip
pip install -r requirements.txt
```

### Project Structure

```
omni-medical-suite/
├── desktop/              # Scanner Fixer Pro desktop app
│   ├── scanner_fixer_pro_v2.py
│   ├── hf_connector.py
│   ├── hf_auto_dataset.py
│   └── gradio_scanner_app.py
├── docker/               # Docker configurations
│   ├── Dockerfile.scanner-fixer
│   └── docker-compose.scanner.yml
├── scripts/              # Build & run scripts
│   ├── build-docker.sh
│   ├── run-docker.sh
│   └── run-docker.bat
├── .github/
│   ├── workflows/        # GitHub Actions
│   ├── dependabot.yml    # Dependabot config
│   └── PULL_REQUEST_TEMPLATE/
├── tests/                # Unit tests
└── docs/                 # Documentation
```

## Code Style

We use **black** for formatting and **flake8** for linting.

```bash
# Format all code
black desktop/ docker/ scripts/ tests/

# Check formatting (CI does this)
black --check desktop/ docker/ scripts/ tests/

# Lint
flake8 desktop/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Sort imports
isort desktop/ docker/ scripts/ tests/
```

### Style Rules

- **Line length**: 100 characters (black default)
- **Quotes**: Double quotes for strings
- **Imports**: Grouped as: stdlib → third-party → local
- **Docstrings**: Google style for all public functions
- **Type hints**: Encouraged for function signatures

## Version Compatibility

⚠️ **CRITICAL**: The following version constraints MUST be maintained:

| Package | Constraint | Reason | Impact if Broken |
|---------|-----------|--------|-----------------|
| `huggingface-hub` | `<1.0.0` | `HfFolder` class removed | `ImportError` on startup |
| `pydantic` | `<2.11.0` | Boolean JSON schema crash | `TypeError: bool is not iterable` |
| `gradio` | `>=4.44.0,<5.0.0` | API stability | UI may not render |
| `gradio-client` | `<1.0.0` | Client compatibility | API calls fail |
| `numpy` | `<2.0.0` | OpenCV compatibility | Image processing errors |

### How to Check

```bash
# Verify constraints
pip show huggingface-hub pydantic gradio gradio-client numpy

# Test imports
python -c "from huggingface_hub import HfFolder; print('OK')"
python -c "import pydantic; print(pydantic.__version__)"
```

## Testing

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=html

# Specific test
pytest tests/test_scanner_fixer.py -v
```

### Write Tests

```python
# tests/test_example.py
import pytest
from desktop.scanner_fixer_pro_v2 import AdvancedScannerFixer

def test_deskew_straight_image():
    """Deskew should return ~0° for straight images."""
    fixer = AdvancedScannerFixer()
    # Create test image
    import numpy as np
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    result, metrics = fixer.process(img, {'deskew': True})
    assert abs(metrics['deskew_angle']) < 1.0
```

## Docker Development

### Build Image

```bash
# Build locally
docker build -f docker/Dockerfile.scanner-fixer -t scanner-fixer-pro .

# Build with cache (faster)
docker build -f docker/Dockerfile.scanner-fixer -t scanner-fixer-pro . --build-arg BUILDKIT_INLINE_CACHE=1
```

### Run Modes

```bash
# Web mode (Gradio on port 7860)
docker run -d -p 7860:7860 scanner-fixer-pro

# Desktop mode (Linux with X11)
docker run -it --rm   -e DISPLAY=$DISPLAY   -v /tmp/.X11-unix:/tmp/.X11-unix   scanner-fixer-pro   python desktop/scanner_fixer_pro_v2.py

# Shell for debugging
docker run -it --rm scanner-fixer-pro /bin/bash
```

### Docker Compose

```bash
# Web mode
docker-compose -f docker/docker-compose.scanner.yml up -d scanner-fixer-web

# Desktop mode
docker-compose -f docker/docker-compose.scanner.yml --profile desktop up
```

## Pull Request Process

1. **Before creating PR**:
   - Run `black`, `flake8`, `pytest`
   - Update documentation if needed
   - Check version compatibility table

2. **PR Template**: Fill out ALL sections of the PR template

3. **Review Requirements**:
   - All CI checks must pass
   - At least 1 review approval
   - No unresolved conversations

4. **After Merge**:
   - Delete your branch
   - Monitor CI/CD pipeline

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(desktop): add batch processing` |
| `fix` | Bug fix | `fix(hf): handle connection timeout` |
| `docs` | Documentation | `docs(readme): update setup instructions` |
| `style` | Code style (no logic) | `style: format with black` |
| `refactor` | Code refactoring | `refactor(scanner): extract helper functions` |
| `perf` | Performance | `perf(denoise): optimize NLM parameters` |
| `test` | Tests | `test: add deskew unit tests` |
| `chore` | Build/CI/CD | `chore(deps): update gradio to 4.44.0` |
| `ci` | CI/CD changes | `ci: add multi-platform build` |
| `build` | Build system | `build(docker): add arm64 support` |

### Scopes

- `desktop` - Desktop application
- `web` - Gradio web interface
- `hf` - Hugging Face integration
- `docker` - Docker configuration
- `ci` - GitHub Actions
- `deps` - Dependencies

### Examples

```bash
# Feature
git commit -m "feat(desktop): add perspective correction preview"

# Bug fix with body
git commit -m "fix(hf): handle missing HF_TOKEN gracefully

Previously, the app would crash if HF_TOKEN was not set.
Now it shows a warning and falls back to local processing."

# Breaking change
git commit -m "feat(api)!: change process_image return type

BREAKING CHANGE: process_image now returns tuple (image, metrics)
instead of just image. Update all callers."
```

## Release Process

1. **Update version** in relevant files
2. **Update CHANGELOG.md**
3. **Create tag**:
   ```bash
   git tag -a v2.1.0 -m "Release v2.1.0 - Feature description"
   git push origin v2.1.0
   ```
4. **CI/CD triggers**:
   - Builds Docker image
   - Pushes to GHCR (and Docker Hub if configured)
   - Deploys to HF Space
   - Creates GitHub Release

## Questions?

- Open an [issue](https://github.com/DrAbdulmalek/omni-medical-suite/issues)
- Check existing [discussions](https://github.com/DrAbdulmalek/omni-medical-suite/discussions)
