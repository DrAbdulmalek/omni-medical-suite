# Repo Sync Toolkit

Secure, automated Git synchronization system for managing multiple GitHub repositories and HuggingFace Spaces. Built for the [Omni Medical Suite](https://github.com/DrAbdulmalek/omni-medical-suite) ecosystem.

> For a simpler one-command sync without TUI or token management, see [sync-github](https://github.com/DrAbdulmalek/sync-github).

## Features

- **17-command TUI dashboard** — push, pull, bidirectional sync, clone, dry-run, watch
- **Secure token management** — `token-manager.py` stores secrets in `~/.config/` with `chmod 600`
- **Auto-discovery** — fetches repo list from GitHub API + HuggingFace API
- **Real-time monitoring** — inotifywait-based file watcher + polling mode
- **PyCharm integration** — open all repos, setup git hooks
- **systemd service** — background auto-sync daemon
- **28 GitHub repos + 11 HF Spaces** — unified management

## Quick Start

```bash
# Clone
git clone https://github.com/DrAbdulmalek/repo-sync-toolkit.git ~/repo-sync-toolkit
cd ~/repo-sync-toolkit

# Make executable
chmod +x github-sync.sh token-manager.py sync-scripts/*.sh config/lib-common.sh

# Setup tokens securely
./token-manager.py add github
./token-manager.py add hf

# Verify
./token-manager.py check
./token-manager.py list

# Run the dashboard
./github-sync.sh
```

## Token Manager

Securely manage API tokens without storing them in the repository:

```bash
# Add tokens (interactive — hidden input)
./token-manager.py add github
./token-manager.py add hf
./token-manager.py add telegram_api_id

# List tokens (masked by default)
./token-manager.py list
./token-manager.py list --show    # show full values (careful!)

# Check security
./token-manager.py check

# Export for shell scripts
./token-manager.py export                  # shell format
./token-manager.py export --format json    # JSON format

# Import from existing file
./token-manager.py import old-tokens.txt

# Remove a token
./token-manager.py remove github
```

**Supported tokens:** `github`, `github_vscode`, `hf`, `telegram_api_id`, `telegram_api_hash`, `deepseek`, `groq`, `openrouter`, `openai`, `zai`, `cursor`

### Security Model

| Aspect | Implementation |
|--------|---------------|
| Storage location | `~/.config/repo-sync-toolkit/secrets.env` |
| File permissions | `600` (owner read/write only) |
| Directory permissions | `700` (owner access only) |
| Display | Masked by default (`ghp_XXXX...XXXX`) |
| Validation | Prefix + length check before saving |
| Repo isolation | `settings.env` is gitignored — only template committed |

## Dashboard Commands

| # | Command | Description |
|---|---------|-------------|
| 1 | Status Dashboard | Show all repos status |
| 2 | Push to GitHub | Local → GitHub |
| 3 | Pull from GitHub | GitHub → Local |
| 4 | Bidirectional Sync | Local ↔ GitHub |
| 5 | Sync Single Repo | Sync one specific repo |
| 6 | Custom Message | Push with custom commit message |
| 7 | Clone All Missing | Clone repos not on disk |
| 8 | Dry-Run Push | Preview without pushing |
| 9 | Monitor (Polling) | Check every 5 min |
| 10 | Watch (Real-time) | inotifywait file watcher |
| 11 | systemd Service | Enable auto-sync daemon |
| 12 | Open PyCharm | Launch all repos in PyCharm |
| 13 | Git Hooks | Setup auto-push hooks |
| 14 | Refresh Repos | Re-fetch repo list from APIs |
| 15-17 | Edit/Logs | Edit config, view logs |

## Project Structure

```
repo-sync-toolkit/
├── github-sync.sh           # Main TUI dashboard
├── token-manager.py         # Secure token CLI manager
├── install.sh               # Installation script
├── .gitignore
├── README.md
├── config/
│   ├── lib-common.sh        # Shared library (auth, sync, dashboard)
│   ├── repos.txt            # Repo list (auto-fetched from APIs)
│   ├── settings.env.example # Settings template (safe to commit)
│   └── settings.env         # Real settings (GITIGNORED)
├── sync-scripts/
│   ├── sync-push.sh
│   ├── sync-pull.sh
│   ├── sync-bidirectional.sh
│   ├── sync-single.sh
│   ├── sync-custom.sh
│   ├── sync-all.sh
│   ├── sync-watch.sh
│   ├── monitor-changes.sh
│   ├── open-pycharm.sh
│   └── setup-pycharm-hooks.sh
├── pycharm-config/
│   └── pycharm.vmoptions
└── logs/
    └── .gitkeep
```

## Migrating from settings.env to token-manager

If you have tokens in `config/settings.env`, migrate them securely:

```bash
# 1. Import all tokens from old settings.env
./token-manager.py import config/settings.env

# 2. Check security
./token-manager.py check

# 3. Remove secrets from settings.env (keep only non-secret settings)
#    Use settings.env.example as reference

# 4. Verify
./token-manager.py list
```

## Author

**Dr. Abdulmalek** — [GitHub](https://github.com/DrAbdulmalek) | [Omni Medical Suite](https://github.com/DrAbdulmalek/omni-medical-suite)

## License

MIT