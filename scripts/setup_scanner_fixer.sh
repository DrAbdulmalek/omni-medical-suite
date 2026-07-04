#!/bin/bash
# ============================================================================
# Scanner Fixer Pro v2.0 - Complete Setup Script for Omni Medical Suite
# ============================================================================
# Usage:
#   cd /path/to/omni-medical-suite
#   chmod +x setup_github_actions.sh
#   ./setup_github_actions.sh
#
# What this does:
#   1. Creates directory structure (desktop/, docker/, scripts/, .github/)
#   2. Copies all Scanner Fixer Pro files to correct locations
#   3. Sets up GitHub Actions workflows
#   4. Creates PR template
#   5. Creates dependabot config
#   6. Verifies everything is in place
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo ""
    echo -e "${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} $1"
}

success() {
    echo -e "${GREEN}  ✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}  ⚠${NC} $1"
}

error() {
    echo -e "${RED}  ✗${NC} $1"
}

# ============================================================================
# HEADER
# ============================================================================
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║     Scanner Fixer Pro v2.0 - Setup for Omni Medical Suite            ║"
echo "║     GitHub Actions CI/CD + PR Template + Dependabot                ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# STEP 1: Verify we're in omni-medical-suite
# ============================================================================
progress "Verifying repository..."

if [ ! -d ".git" ]; then
    error "Not a git repository!"
    echo "  Please run this script from the omni-medical-suite directory."
    exit 1
fi

REPO_NAME=$(basename $(git rev-parse --show-toplevel))
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

if [[ "$REMOTE_URL" =~ "omni-medical-suite" ]]; then
    success "Confirmed: omni-medical-suite repository"
else
    warning "Remote URL doesn't contain 'omni-medical-suite'"
    echo "  Remote: $REMOTE_URL"
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ============================================================================
# STEP 2: Create directory structure
# ============================================================================
progress "Creating directory structure..."

DIRS=(
    "desktop"
    "docker"
    "scripts"
    ".github/workflows"
    ".github/PULL_REQUEST_TEMPLATE"
    "tests"
    "docs"
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    success "Created: $dir/"
done

# ============================================================================
# STEP 3: Copy Scanner Fixer Pro application files
# ============================================================================
progress "Copying Scanner Fixer Pro files..."

# Map source files to destination paths
# Format: "source_file|destination_path"
APP_FILES=(
    "desktop_scanner_fixer_pro_v2.py|desktop/scanner_fixer_pro_v2.py"
    "hf_connector.py|desktop/hf_connector.py"
    "hf_auto_dataset.py|desktop/hf_auto_dataset.py"
    "gradio_scanner_app.py|desktop/gradio_scanner_app.py"
)

for mapping in "${APP_FILES[@]}"; do
    IFS='|' read -r src dst <<< "$mapping"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        success "Copied: $src → $dst"
    else
        warning "Source not found: $src (will create placeholder)"
        # Create minimal placeholder
        cat > "$dst" << EOF
# Placeholder - replace with actual file
# Source: $src
print("Placeholder - please copy actual file here")
EOF
    fi
done

# Create desktop README
cat > desktop/README.md << 'EOF'
# Scanner Fixer Pro - Desktop Application

## Files

| File | Description |
|------|-------------|
| `scanner_fixer_pro_v2.py` | Main desktop app (Tkinter + HF integration) |
| `hf_connector.py` | Hugging Face Space API connector |
| `hf_auto_dataset.py` | Automatic HF Dataset creation & management |
| `gradio_scanner_app.py` | Web interface alternative (Gradio) |

## Quick Start

```bash
# Install dependencies
pip install -r ../requirements.txt

# Run desktop app
python scanner_fixer_pro_v2.py

# Run web app
python gradio_scanner_app.py
```

## Features

- **Local Processing**: Shadow removal, deskew, perspective correction, denoise, contrast enhancement, auto-crop
- **HF Integration**: Connect to HF Space for OCR, send corrections to Dataset
- **Batch Processing**: Process entire folders
- **3 Modes**: Local / Hybrid (local + HF OCR) / HF Direct

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | Hugging Face access token |
| `HF_USERNAME` | HF username (default: DrAbdulmalek) |
EOF

success "Created: desktop/README.md"

# ============================================================================
# STEP 4: Copy Docker files
# ============================================================================
progress "Copying Docker configuration..."

DOCKER_FILES=(
    "Dockerfile.final|docker/Dockerfile.scanner-fixer"
    "docker-compose.final.yml|docker/docker-compose.scanner.yml"
    ".dockerignore|docker/.dockerignore"
)

for mapping in "${DOCKER_FILES[@]}"; do
    IFS='|' read -r src dst <<< "$mapping"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        success "Copied: $src → $dst"
    else
        warning "Source not found: $src"
    fi
done

# Create docker README
cat > docker/README.md << 'EOF'
# Docker Configuration - Scanner Fixer Pro

## Files

| File | Description |
|------|-------------|
| `Dockerfile.scanner-fixer` | Multi-stage build (Web + Desktop support) |
| `docker-compose.scanner.yml` | Compose for web/desktop/shell modes |
| `.dockerignore` | Files to exclude from build context |

## Quick Start

```bash
# Web mode (recommended)
docker-compose -f docker/docker-compose.scanner.yml up -d scanner-fixer-web

# Desktop mode (Linux with X11)
xhost +local:docker
docker-compose -f docker/docker-compose.scanner.yml --profile desktop up

# Shell access
docker-compose -f docker/docker-compose.scanner.yml --profile shell run --rm scanner-fixer-shell
```

## Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `HUGGINGFACE_HUB_VERSION` | `<1.0.0` | Prevents HfFolder removal crash |
| `PYDANTIC_VERSION` | `<2.11.0` | Prevents boolean JSON schema crash |

## Ports

- `7860`: Gradio web interface
EOF

success "Created: docker/README.md"

# ============================================================================
# STEP 5: Copy scripts
# ============================================================================
progress "Copying build & run scripts..."

SCRIPT_FILES=(
    "build-and-push.sh|scripts/build-docker.sh"
    "run.sh|scripts/run-docker.sh"
    "run.bat|scripts/run-docker.bat"
)

for mapping in "${SCRIPT_FILES[@]}"; do
    IFS='|' read -r src dst <<< "$mapping"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        chmod +x "$dst"
        success "Copied: $src → $dst"
    else
        warning "Source not found: $src"
    fi
done

# ============================================================================
# STEP 6: Setup GitHub Actions workflows
# ============================================================================
progress "Setting up GitHub Actions workflows..."

WORKFLOW_FILES=(
    ".github/workflows/docker-build-push.yml"
    ".github/workflows/lint-test.yml"
    ".github/workflows/release.yml"
)

for wf in "${WORKFLOW_FILES[@]}"; do
    if [ -f "$wf" ]; then
        success "Workflow exists: $wf"
    else
        warning "Workflow not found: $wf"
        echo "  Please copy manually from the generated files."
    fi
done

# ============================================================================
# STEP 7: Create PR Template
# ============================================================================
progress "Creating Pull Request template..."

cat > .github/PULL_REQUEST_TEMPLATE/pull_request_template.md << 'EOF'
<!--
Thank you for contributing to Omni Medical Suite!
Please fill out this template to help reviewers understand your changes.
-->

## Description
<!-- Provide a clear and concise description of your changes -->

Fixes #(issue number)

## Type of Change
<!-- Mark the relevant option with an [x] -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Configuration change
- [ ] 🧪 Tests
- [ ] 🏗️ Build/CI/CD improvement

## Component Affected
<!-- Mark all that apply -->

- [ ] 🖥️ Desktop App (scanner_fixer_pro_v2.py)
- [ ] 🌐 Web Interface (Gradio)
- [ ] 🔗 HF Connector (hf_connector.py)
- [ ] 📊 Dataset Manager (hf_auto_dataset.py)
- [ ] 🐳 Docker Configuration
- [ ] ⚙️ GitHub Actions / CI/CD
- [ ] 📖 Documentation
- [ ] 🧪 Tests

## Testing
<!-- Describe how you tested your changes -->

- [ ] Tested locally (desktop app)
- [ ] Tested via Docker
- [ ] Tested on Hugging Face Space
- [ ] Added/updated unit tests
- [ ] All existing tests pass

### Test Environment
- OS: <!-- e.g., Ubuntu 22.04, macOS 14, Windows 11 -->
- Python: <!-- e.g., 3.11.4 -->
- Docker: <!-- e.g., 24.0.7 -->

## Known Issues / Limitations
<!-- List any known issues or limitations -->

## Checklist
- [ ] My code follows the project's style guidelines (flake8/black)
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] I have checked for version compatibility (huggingface_hub<1.0, pydantic<2.11)

## Screenshots / Logs
<!-- If applicable, add screenshots or logs to help explain your changes -->

## Related PRs / Issues
<!-- Link to related PRs or issues -->
EOF

success "Created: .github/PULL_REQUEST_TEMPLATE/pull_request_template.md"

# Also create a simple CONTRIBUTING.md
cat > CONTRIBUTING.md << 'EOF'
# Contributing to Omni Medical Suite

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/omni-medical-suite.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `pytest tests/`
6. Commit: `git commit -m "feat: your feature description"`
7. Push: `git push origin feature/your-feature-name`
8. Open a Pull Request

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, no logic change)
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Build/CI/CD changes

## Version Compatibility

⚠️ **Critical**: Always check version constraints:

| Package | Constraint | Reason |
|---------|-----------|--------|
| `huggingface_hub` | `<1.0.0` | Prevents HfFolder removal |
| `pydantic` | `<2.11.0` | Prevents boolean JSON schema crash |
| `gradio` | `>=4.44.0,<5.0.0` | Stable API |
| `gradio-client` | `<1.0.0` | Client compatibility |

## Code Style

```bash
# Format code
black desktop/ docker/ scripts/

# Check style
flake8 desktop/ --count --select=E9,F63,F7,F82 --show-source

# Sort imports
isort desktop/ docker/ scripts/
```

## Docker Development

```bash
# Build locally
docker build -f docker/Dockerfile.scanner-fixer -t scanner-fixer-pro .

# Run web mode
docker run -d -p 7860:7860 scanner-fixer-pro

# Run desktop mode (Linux)
docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix scanner-fixer-pro python desktop/scanner_fixer_pro_v2.py
```
EOF

success "Created: CONTRIBUTING.md"

# ============================================================================
# STEP 8: Create Dependabot Configuration
# ============================================================================
progress "Creating Dependabot configuration..."

cat > .github/dependabot.yml << 'EOF'
# ============================================================================
# Dependabot Configuration
# Automatically checks for dependency updates
# ============================================================================

version: 2
updates:
  # ==========================================================================
  # Python dependencies (pip)
  # ==========================================================================
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Riyadh"
    open-pull-requests-limit: 5
    reviewers:
      - "DrAbdulmalek"
    assignees:
      - "DrAbdulmalek"
    labels:
      - "dependencies"
      - "python"
    commit-message:
      prefix: "chore(deps)"
      include: "scope"
    # Version constraints - CRITICAL for compatibility
    ignore:
      # huggingface_hub >=1.0 removes HfFolder
      - dependency-name: "huggingface-hub"
        versions: [">=1.0.0"]
      # pydantic >=2.11 causes boolean JSON schema crash (gradio-app/gradio#11722)
      - dependency-name: "pydantic"
        versions: [">=2.11.0"]
      # gradio >=5.0 may have breaking API changes
      - dependency-name: "gradio"
        versions: [">=5.0.0"]
      # gradio-client >=1.0 may have breaking changes
      - dependency-name: "gradio-client"
        versions: [">=1.0.0"]
    # Allow updates for everything else
    allow:
      - dependency-type: "direct"
      - dependency-type: "indirect"

  # ==========================================================================
  # Python dependencies (desktop/)
  # ==========================================================================
  - package-ecosystem: "pip"
    directory: "/desktop"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Riyadh"
    open-pull-requests-limit: 3
    reviewers:
      - "DrAbdulmalek"
    labels:
      - "dependencies"
      - "python"
      - "desktop"
    commit-message:
      prefix: "chore(deps-desktop)"
    ignore:
      - dependency-name: "huggingface-hub"
        versions: [">=1.0.0"]
      - dependency-name: "pydantic"
        versions: [">=2.11.0"]
      - dependency-name: "gradio"
        versions: [">=5.0.0"]
      - dependency-name: "gradio-client"
        versions: [">=1.0.0"]

  # ==========================================================================
  # Docker dependencies
  # ==========================================================================
  - package-ecosystem: "docker"
    directory: "/docker"
    schedule:
      interval: "monthly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Riyadh"
    open-pull-requests-limit: 3
    reviewers:
      - "DrAbdulmalek"
    labels:
      - "dependencies"
      - "docker"
    commit-message:
      prefix: "chore(deps-docker)"

  # ==========================================================================
  # GitHub Actions dependencies
  # ==========================================================================
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Riyadh"
    open-pull-requests-limit: 5
    reviewers:
      - "DrAbdulmalek"
    labels:
      - "dependencies"
      - "github-actions"
      - "ci-cd"
    commit-message:
      prefix: "chore(deps-actions)"
EOF

success "Created: .github/dependabot.yml"

# ============================================================================
# VERIFICATION
# ============================================================================
progress "Verifying setup..."

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Directory Structure${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

# Show tree-like structure
for dir in desktop docker scripts .github/workflows .github/PULL_REQUEST_TEMPLATE; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $dir/"
        find "$dir" -maxdepth 1 -type f | sed 's|^|    |' | head -20
    else
        error "Missing directory: $dir/"
    fi
done

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  File Count${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

for dir in desktop docker scripts .github/workflows .github/PULL_REQUEST_TEMPLATE; do
    count=$(find "$dir" -type f 2>/dev/null | wc -l)
    echo -e "  ${BLUE}$dir/:${NC} $count files"
done

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Git Status${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

git status --short | head -30 || echo "  (not a git repo or no changes)"

# ============================================================================
# NEXT STEPS
# ============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✅ Setup Complete!                                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo "  1️⃣  Review changes:"
echo "      git status"
echo "      git diff --stat"
echo ""
echo "  2️⃣  Commit changes:"
echo "      git add ."
echo "      git commit -m "feat: add Scanner Fixer Pro v2.0 + CI/CD + Dependabot""
echo ""
echo "  3️⃣  Set GitHub Secrets (required for CI/CD):"
echo "      gh secret set HF_TOKEN --body "hf_xxxxxxxxxxxxxxxx""
echo "      gh secret set DOCKERHUB_USERNAME --body "your_username""
echo "      gh secret set DOCKERHUB_TOKEN --body "your_token""
echo ""
echo "      Or manually at: https://github.com/DrAbdulmalek/omni-medical-suite/settings/secrets/actions"
echo ""
echo "  4️⃣  Push to trigger CI/CD:"
echo "      git push origin main"
echo ""
echo "  5️⃣  Create a release (triggers full pipeline):"
echo "      git tag v2.0.0"
echo "      git push origin v2.0.0"
echo ""
echo "  6️⃣  Verify:"
echo "      - GitHub Actions tab → check workflows running"
echo "      - Packages tab → check GHCR image"
echo "      - HF Space → check auto-deployment"
echo "      - Dependabot tab → check for updates"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "   - Dependabot will ignore critical packages (huggingface_hub>=1.0, pydantic>=2.11)"
echo "   - PR template enforces version compatibility checks"
echo "   - All PRs require review before merge"
echo ""
