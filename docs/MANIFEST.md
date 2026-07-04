
# ============================================================================
# Scanner Fixer Pro v2.0 - Complete File Manifest
# ============================================================================
# Generated: 2026-07-04
# Author: Dr. Abdulmalek Tamer Al-husseini
# Project: Omni Medical Suite
# ============================================================================

## 1. APPLICATION FILES (Python)

| File | Description | Destination in omni-medical-suite |
|------|-------------|--------------------------------|
| desktop_scanner_fixer_pro_v2.py | Main desktop app (Tkinter + HF) | desktop/scanner_fixer_pro_v2.py |
| hf_connector.py | HF Space API connector | desktop/hf_connector.py |
| hf_auto_dataset.py | HF Dataset manager | desktop/hf_auto_dataset.py |
| gradio_scanner_app.py | Web interface (Gradio) | desktop/gradio_scanner_app.py |

## 2. DOCKER FILES

| File | Description | Destination |
|------|-------------|-------------|
| Dockerfile.final | Multi-stage build (Web + Desktop) | docker/Dockerfile.scanner-fixer |
| Dockerfile.web | Web-only (smaller) | docker/Dockerfile.web |
| Dockerfile.desktop | Desktop-only | docker/Dockerfile.desktop |
| docker-compose.final.yml | Production compose | docker/docker-compose.scanner.yml |
| .dockerignore | Build context exclusions | docker/.dockerignore |

## 3. GITHUB ACTIONS CI/CD

| File | Description | Destination |
|------|-------------|-------------|
| docker-build-push.yml | Build, push, deploy to HF | .github/workflows/ |
| lint-test.yml | Lint (flake8/black) + pytest | .github/workflows/ |
| release.yml | GitHub Release with changelog | .github/workflows/ |

## 4. PULL REQUEST TEMPLATE

| File | Description | Destination |
|------|-------------|-------------|
| pull_request_template.md | Comprehensive PR template | .github/PULL_REQUEST_TEMPLATE/ |

## 5. DEPENDABOT CONFIGURATION

| File | Description | Destination |
|------|-------------|-------------|
| dependabot.yml | Auto-update dependencies with constraints | .github/dependabot.yml |

## 6. SCRIPTS

| File | Description | Destination |
|------|-------------|-------------|
| setup_github_actions.sh | One-command setup for omni-medical-suite | (run from repo root) |
| build-and-push.sh | Build + push Docker image | scripts/build-docker.sh |
| run.sh | Runner for Linux/macOS | scripts/run-docker.sh |
| run.bat | Runner for Windows | scripts/run-docker.bat |

## 7. DOCUMENTATION

| File | Description | Destination |
|------|-------------|-------------|
| README_SCANNER_FIXER.md | App usage guide | docs/ or root |
| README_DOCKER.md | Docker deployment guide | docker/README.md |
| INTEGRATION_GUIDE.md | Integration instructions | docs/ or root |
| CONTRIBUTING.md | Contribution guidelines | root/CONTRIBUTING.md |

## 8. CONFIGURATION

| File | Description | Destination |
|------|-------------|-------------|
| requirements.txt | Python dependencies | root/requirements.txt |

## TOTAL: 22 files

## QUICK START

```bash
# 1. Navigate to omni-medical-suite
cd /path/to/omni-medical-suite

# 2. Run setup script
chmod +x setup_github_actions.sh
./setup_github_actions.sh

# 3. Set secrets
gh secret set HF_TOKEN --body "hf_xxxxxxxx"

# 4. Commit and push
git add .
git commit -m "feat: add Scanner Fixer Pro v2.0 + CI/CD + Dependabot"
git push origin main

# 5. Create release
git tag v2.0.0
git push origin v2.0.0
```
