# Contributing to SIN-Browser-Tools

Thank you for your interest in contributing! This guide will help you get started.

## Table of Contents
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding a New Tool](#adding-a-new-tool)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

---

## Development Setup

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/OpenSIN-Code/SIN-Browser-Tools.git
cd SIN-Browser-Tools

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install Chromium browser (required, one-time)
python -m playwright install chromium
```

### Verify Installation

```bash
# Run tests to verify everything works
python -m pytest

# Quick smoke test
python -c "from sin_browser_tools.tools import catalog; print(f'{len(catalog.discover())} tools available')"
```

---

## Code Style

We enforce consistent code style using automated tools.

### Tools
- **Ruff** for linting and import sorting
- **Type hints** required for all public functions

### Commands

```bash
# Check linting
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code (via ruff)
ruff format .
```

### Style Guidelines

1. **Line length**: 100 characters max
2. **Imports**: sorted by ruff (stdlib, third-party, local)
3. **Docstrings**: Google style for public functions
4. **Type hints**: Required for function signatures
5. **Naming**:
   - Tools: `browser_<action>` (e.g., `browser_click`, `browser_snapshot`)
   - Internal functions: `_underscore_prefix`
   - Classes: `PascalCase`

### Pre-commit Hooks

Install pre-commit hooks to auto-check before each commit:

```bash
pip install pre-commit
pre-commit install
```

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_tool_smoke.py

# Run tests matching a pattern
python -m pytest -k "frame"

# Run with coverage
python -m pytest --cov=sin_browser_tools
```

### Writing Tests

1. Use the `live_manager` fixture for browser tests
2. Tests should be independent and not rely on order
3. Clean up any state changes (tabs, cookies, etc.)
4. Use descriptive test names: `test_<tool>_<scenario>`

---

## Adding a New Tool

### 1. Choose the Right Module

| Module | Purpose |
|--------|---------|
| `navigation.py` | URL navigation, history, viewport, waits |
| `interaction.py` | Clicks, typing, form controls |
| `accessibility.py` | Snapshots, AX tree |
| `extraction.py` | HTML, cookies, storage, console |
| `vision.py` | Screenshots, PDF, images |
| `dialog.py` | Native JS dialogs |
| `frames.py` | Frame traversal, shadow DOM |

### 2. Implement the Tool

```python
async def browser_my_new_tool(
    required_param: str,
    optional_param: int = 10,
) -> dict:
    """One-line description.

    Args:
        required_param: What this parameter controls.
        optional_param: What this controls. Defaults to 10.

    Returns:
        dict with status, data, and optional hint.
    """
    page = manager.page
    # Implementation here
    return {"status": "success", "data": result}
```

### 3. Auto-Registration

Tools are auto-discovered by `catalog.discover()`. Requirements:
- Function name starts with `browser_`
- Function is `async`
- Function is in a module listed in `catalog.TOOL_MODULES`

### 4. Add Tests and Documentation

- Add smoke tests in `tests/test_tool_smoke.py`
- Add to `API.md` in the appropriate section
- Update tool count in `README.md`

---

## Return Contract Stability

Agents and tests branch on the **keys** a tool returns, so a tool's return dict is
a public API. Changing it is a breaking change.

**Rules:**

1. **Never rename or remove an existing key** in a released tool's return dict.
   Renaming `status` → `found`, or dropping `error`, breaks every caller that
   reads the old key. (This is exactly what caused [Issue #28][i28]: the #22
   enhancement swapped `{"status": "found"}` for `{"found": true}` and broke the
   whole suite.)

2. **Evolve contracts additively.** To expose new information, *add* a new key
   and keep the old one. Returning **both** `status` *and* `found` is backwards
   compatible and still ships the new data.

3. **Keep the `status` key on every code path** (`success`/`ok`, `timeout`,
   `error`, `unsupported`, …). Error and early-return paths must carry it too,
   not just the happy path.

4. **Pin the contract with a test.** Assert the exact keys for *both* the success
   and failure paths so a future refactor can't silently drop one. See
   `tests/test_tool_smoke.py::test_wait_for_text_returns_both_status_and_found`
   for the reference pattern.

5. **If a breaking change is truly unavoidable**, open an issue first, bump the
   version, and document the migration in `CHANGELOG.md` under a `### Changed`
   (breaking) heading.

[i28]: https://github.com/OpenSIN-Code/SIN-Browser-Tools/issues/28

---

## Pull Request Process

### Before Submitting

1. **Create an issue first** for significant changes
2. **Branch from `main`**: `git checkout -b fix/issue-123-description`
3. **Run tests**: `python -m pytest`
4. **Run linter**: `ruff check .`

### Commit Message Format

```
type(scope): short description

Fixes #123
```

Types: `fix`, `feat`, `docs`, `test`, `chore`, `refactor`

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
