# UV Migration Summary

**Date:** May 30, 2026

## Overview

The TalentKru.ai server project has been updated to exclusively use **uv** for Python package dependency management, replacing Poetry. All development workflows now use `uv` with Invoke for build automation.

## Key Changes

### 1. Dependency Management (tech.md)
- **Removed:** Poetry references and `poetry.lock`
- **Added:** uv as the primary package manager
- **Lock file:** Changed from `poetry.lock` to `uv.lock`
- **Key principle:** Never use `pip` directly — always use `uv`

### 2. Updated Commands (tech.md)

#### Installation
```zsh
# Old (Poetry)
poetry install
poetry install --no-dev
poetry update

# New (uv)
uv sync
uv sync --no-dev
uv lock --upgrade
```

#### Running Tasks
```zsh
# Old (Poetry)
poetry run invoke dev
poetry run invoke test

# New (uv)
uv run invoke dev
uv run invoke test
```

### 3. New Invoke Tasks (tasks.py)

Added dedicated uv-based tasks for dependency management:

| Task | Command | Description |
|------|---------|-------------|
| `sync` | `uv sync` | Sync all dependencies (including dev) |
| `sync-no-dev` | `uv sync --no-dev` | Sync only production dependencies |
| `add` | `uv add <package>` | Add a new dependency |
| `add-dev` | `uv add --dev <package>` | Add a new dev dependency |
| `lock-upgrade` | `uv lock --upgrade` | Upgrade all dependencies to latest |
| `lock-refresh` | `uv lock` | Refresh lock file |
| `cache-clean` | `uv cache clean` | Clean uv cache |
| `show-deps` | `uv pip list` | Show all installed dependencies |

### 4. Backwards Compatibility

Legacy task aliases maintained for smooth transition:
- `install` → calls `sync`
- `install-dev` → calls `sync`
- `update` → calls `lock-upgrade`
- `show-deps` → calls `uv pip list`

### 5. Shell Environment

- **Shell:** zsh (macOS)
- **All code blocks:** Updated from `bash` to `zsh`
- **Commands:** Compatible with zsh shell environment

## Usage Examples

### First-Time Setup
```zsh
# 1. Sync dependencies
uv run invoke sync

# 2. Start database
uv run invoke db-start

# 3. Initialize database users
uv run invoke db-init-users

# 4. Apply migrations
uv run invoke migrate

# 5. Start dev server
uv run invoke dev
```

### Adding Dependencies
```zsh
# Add a production dependency
uv run invoke add --package requests

# Add a dev dependency
uv run invoke add-dev --package pytest-xdist

# Upgrade all dependencies
uv run invoke lock-upgrade
```

### Daily Development
```zsh
# Terminal 1: Start dev server
uv run invoke dev

# Terminal 2: Run tests in watch mode
uv run invoke test-watch

# Terminal 3: Check code quality
uv run invoke lint
```

## Benefits of uv

1. **Speed**: Rust-based implementation is significantly faster than Poetry
2. **Simplicity**: Cleaner command interface
3. **Lock file**: `uv.lock` is more deterministic
4. **Compatibility**: Works seamlessly with existing `pyproject.toml`
5. **No virtual environment overhead**: uv handles environments efficiently

## Migration Checklist

- [x] Update tech.md steering document
- [x] Add new uv tasks to tasks.py
- [x] Update all command examples to use `uv run invoke`
- [x] Add backwards compatibility aliases
- [x] Update documentation examples
- [x] Verify Python syntax (tasks.py)
- [ ] Delete `poetry.lock` (when ready)
- [ ] Commit changes to git

## Important Notes

### Never Use pip Directly
```zsh
# ❌ WRONG
pip install package_name

# ✅ CORRECT
uv run invoke add --package package_name
```

### Always Use `uv run` for Python Executions
```zsh
# ❌ WRONG
python script.py
pytest tests/
mypy app

# ✅ CORRECT
uv run script.py
uv run pytest tests/
uv run mypy app
uv run python  # Interactive REPL
```

### Lock File Management
```zsh
# Update lock file with latest versions
uv run invoke lock-upgrade

# Refresh lock file without upgrading
uv run invoke lock-refresh

# Clean cache if issues occur
uv run invoke cache-clean
```

### Environment Variables
All existing `.env` configuration remains unchanged. The migration only affects how dependencies are managed, not application configuration.

## Troubleshooting

### uv Not Installed
```zsh
# Install uv
brew install uv

# Or via pip
pip install uv
```

### Cache Issues
```zsh
# Clear uv cache
uv run invoke cache-clean

# Resync dependencies
uv run invoke sync --refresh
```

### Lock File Conflicts
```zsh
# Refresh lock file
uv run invoke lock-refresh

# Resync
uv run invoke sync
```

## References

- [uv Documentation](https://docs.astral.sh/uv/)
- [uv GitHub Repository](https://github.com/astral-sh/uv)
- [Invoke Documentation](http://docs.pyinvoke.org/)

## Questions?

Refer to the updated `tech.md` steering document for comprehensive build system documentation.
