# Python Execution Guide

**Last Updated:** May 30, 2026

## Core Principle

**All Python executions must be prepended with `uv run`** to ensure consistent environment management, correct Python version, and proper dependency isolation.

## Quick Reference

### Scripts
```zsh
# Execute a Python script
uv run script_name.py

# With arguments
uv run script_name.py --arg value --flag

# With environment variables
ENV_VAR=value uv run script_name.py
```

### Testing
```zsh
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_auth_service.py

# Run specific test function
uv run pytest tests/test_auth_service.py::test_login

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run in watch mode
uv run invoke test-watch

# Run with verbose output
uv run pytest -v

# Run with specific markers
uv run pytest -m integration
```

### Code Quality Tools
```zsh
# Type checking
uv run mypy app

# Linting
uv run ruff check app tests

# Formatting
uv run ruff format app tests

# Check formatting
uv run ruff format --check app tests
```

### Database Tools
```zsh
# Run migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# Check migration status
uv run alembic current

# Create new migration
uv run alembic revision --autogenerate -m "Description"
```

### Interactive REPL
```zsh
# Launch Python interactive shell
uv run python

# With IPython (if installed)
uv run ipython
```

### Task Runner
```zsh
# Run invoke tasks
uv run invoke dev
uv run invoke test
uv run invoke lint
uv run invoke format
uv run invoke db-start
```

## Common Patterns

### Development Workflow
```zsh
# Terminal 1: Start dev server
uv run invoke dev

# Terminal 2: Run tests in watch mode
uv run invoke test-watch

# Terminal 3: Check code quality
uv run invoke lint
```

### Before Committing
```zsh
# Format code
uv run invoke format

# Run all checks
uv run invoke check

# Run full test suite with coverage
uv run invoke test-cov
```

### Debugging
```zsh
# Run Python with debugger
uv run python -m pdb script_name.py

# Run pytest with debugger
uv run pytest --pdb tests/test_file.py

# Interactive Python shell for exploration
uv run python
```

### Running Scripts with Invoke
```zsh
# Create a custom invoke task for your script
# In tasks.py:
@task
def my_script(c):
    """Run my custom script."""
    c.run("uv run my_script.py", pty=True)

# Then run it
uv run invoke my-script
```

## Why `uv run`?

1. **Environment Isolation**: Ensures correct Python version (3.12.x)
2. **Dependency Management**: Uses locked versions from `uv.lock`
3. **Consistency**: All developers use identical environments
4. **Reproducibility**: Guarantees exact package versions
5. **Safety**: Prevents accidental use of system Python
6. **Simplicity**: No manual virtual environment activation needed

## Common Mistakes

### ❌ WRONG
```zsh
python script.py
python3 script.py
pytest tests/
mypy app
ruff check app
alembic upgrade head
ipython
```

### ✅ CORRECT
```zsh
uv run script.py
uv run script.py
uv run pytest tests/
uv run mypy app
uv run ruff check app
uv run alembic upgrade head
uv run ipython
```

## Troubleshooting

### Command Not Found
```zsh
# If you get "command not found", ensure uv is installed
brew install uv

# Or verify uv is in PATH
which uv
```

### Python Version Mismatch
```zsh
# Verify correct Python version
uv run python --version  # Should show 3.12.x

# Reset pyenv if needed
pyenv local 3.12.0
exec $SHELL
```

### Dependencies Not Found
```zsh
# Sync dependencies
uv run invoke sync

# Or refresh lock file
uv run invoke lock-refresh
```

### Cache Issues
```zsh
# Clear uv cache
uv run invoke cache-clean

# Resync dependencies
uv run invoke sync --refresh
```

## Integration with IDE

### VS Code
Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.ruffEnabled": true,
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm
1. Go to Settings → Project → Python Interpreter
2. Click gear icon → Add
3. Select "Existing Environment"
4. Navigate to `.venv/bin/python`

## References

- [uv Documentation](https://docs.astral.sh/uv/)
- [pytest Documentation](https://docs.pytest.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
