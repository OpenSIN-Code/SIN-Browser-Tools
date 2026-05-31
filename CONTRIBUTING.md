# Contributing

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Running Tests

```bash
python test_all_tools.py
```

## Code Style

- Black (100 char lines)
- Ruff linting
- Type hints required

```bash
black sin_browser_tools/
ruff check sin_browser_tools/
```

## Adding a Tool

1. Create async function in `sin_browser_tools/tools/<category>.py`
2. Register in `opensin_skill.py` as `ToolAction`
3. Add to MCP server in `mcp_server.py`
4. Document in API.md

## PR Process

1. Fork and create feature branch
2. Make changes and test
3. Format code with Black
4. Submit PR with description
