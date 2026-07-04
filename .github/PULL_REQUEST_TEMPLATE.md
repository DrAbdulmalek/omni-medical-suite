<!--
================================================================================
  Omni Medical Suite - Pull Request Template
================================================================================
Thank you for contributing! Please fill out ALL sections to help reviewers.
-->

## 📋 Description
<!-- Provide a clear, concise description of your changes -->

**What:**
<!-- What does this PR do? -->

**Why:**
<!-- Why is this change needed? Link to issue if applicable -->

Fixes #(issue number) <!-- or N/A -->

---

## 🏷️ Type of Change
<!-- Mark ALL that apply with [x] -->

- [ ] 🐛 **Bug fix** - non-breaking change that fixes an issue
- [ ] ✨ **New feature** - non-breaking change that adds functionality
- [ ] 💥 **Breaking change** - fix/feature causing existing functionality to break
- [ ] 📚 **Documentation** - updates to docs, README, or comments
- [ ] 🔧 **Configuration** - changes to config files, Docker, CI/CD
- [ ] 🧪 **Tests** - adding/updating tests
- [ ] 🏗️ **Build/CI/CD** - changes to build system or pipelines
- [ ] 🎨 **UI/UX** - visual or interaction changes
- [ ] ⚡ **Performance** - optimization or speed improvements
- [ ] 🔒 **Security** - security fixes or improvements

---

## 🧩 Component(s) Affected
<!-- Mark ALL components this PR touches -->

- [ ] 🖥️ **Desktop App** (`desktop/scanner_fixer_pro_v2.py`)
- [ ] 🌐 **Web Interface** (`desktop/gradio_scanner_app.py`)
- [ ] 🔗 **HF Connector** (`desktop/hf_connector.py`)
- [ ] 📊 **Dataset Manager** (`desktop/hf_auto_dataset.py`)
- [ ] 🐳 **Docker** (`docker/`)
- [ ] ⚙️ **GitHub Actions** (`.github/workflows/`)
- [ ] 🤖 **Dependabot** (`.github/dependabot.yml`)
- [ ] 📖 **Documentation** (`README.md`, `CONTRIBUTING.md`, `docs/`)
- [ ] 🧪 **Tests** (`tests/`)
- [ ] 🔧 **Scripts** (`scripts/`)
- [ ] 📦 **Dependencies** (`requirements.txt`, `pyproject.toml`)

---

## 🧪 Testing
<!-- Describe ALL testing performed. Be specific! -->

### Tested Environments
<!-- Mark all you tested -->

- [ ] Local Python (desktop app)
- [ ] Local Python (web app)
- [ ] Docker (web mode)
- [ ] Docker (desktop mode)
- [ ] Hugging Face Space
- [ ] GitHub Actions (CI/CD)

### Test Details
```
OS:        <!-- e.g., Ubuntu 22.04, macOS 14.5, Windows 11 -->
Python:    <!-- e.g., 3.11.9 -->
Docker:    <!-- e.g., 24.0.7 or N/A -->
Browser:   <!-- e.g., Chrome 126, Firefox 127 or N/A -->
```

### Test Steps
<!-- Describe what you tested and how -->
1. 
2. 
3. 

### Screenshots / Logs
<!-- Paste screenshots, error logs, or output -->
```
<!-- Paste here -->
```

---

## ⚠️ Version Compatibility Checklist
<!-- CRITICAL: Verify these constraints are maintained -->

| Package | Constraint | Your Change | Verified? |
|---------|-----------|-------------|-----------|
| `huggingface-hub` | `<1.0.0` | <!-- your version --> | [ ] |
| `pydantic` | `<2.11.0` | <!-- your version --> | [ ] |
| `gradio` | `>=4.44.0,<5.0.0` | <!-- your version --> | [ ] |
| `gradio-client` | `<1.0.0` | <!-- your version --> | [ ] |
| `opencv-python` | `>=4.8.0,<5.0.0` | <!-- your version --> | [ ] |

> ⚠️ **Why these constraints matter:**
> - `huggingface-hub>=1.0` removes `HfFolder` class → ImportError
> - `pydantic>=2.11` adds `additionalProperties: true` to boolean JSON schema → gradio crash
> - `gradio>=5.0` may have breaking API changes

---

## ✅ Pre-Merge Checklist
<!-- ALL items must be checked before merging -->

- [ ] Code follows project style (flake8/black)
- [ ] Self-review completed
- [ ] Code is commented (complex logic explained)
- [ ] Documentation updated (README, docstrings, comments)
- [ ] No new warnings or errors
- [ ] Tests added/updated and passing
- [ ] Version constraints maintained (see table above)
- [ ] Docker image builds successfully: `docker build -f docker/Dockerfile.scanner-fixer .`
- [ ] No secrets/tokens committed (check with `git diff --cached`)
- [ ] CHANGELOG.md updated (if applicable)

---

## 🔗 Related

### Related PRs
<!-- Link to related PRs -->
- 

### Related Issues
<!-- Link to related issues -->
- 

### Breaking Changes
<!-- List any breaking changes and migration steps -->
- 

---

## 📝 Additional Notes
<!-- Anything else reviewers should know? -->

