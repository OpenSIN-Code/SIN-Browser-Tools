# CLAUDE.md — AI Coding Assistant Guide

This file provides guidance for AI coding assistants (Claude, GPT, Copilot, etc.)
working on this codebase. Read this before making changes.

## Project Overview

SIN-Browser-Tools is a Python library for browser automation, designed for AI agents.
It provides 52+ tools exposed via MCP (Model Context Protocol) for headless browser control.

## Architecture

```
sin_browser_tools/
├── core/                    # Internal infrastructure
│   ├── manager.py           # BrowserManager singleton + proxy
│   ├── frame_traversal.py   # OOPIF/shadow DOM traversal
│   ├── observability.py     # Tracing and debugging
│   ├── pii_redaction.py     # PII detection/masking
│   ├── session_vault.py     # Session persistence
│   └── spa_waker.py         # SPA hydration detection
├── tools/                   # User-facing tools (auto-discovered)
│   ├── accessibility.py     # browser_snapshot, browser_snapshot_full_oopif
│   ├── dialog.py            # browser_dialog, browser_wait_for_dialog
│   ├── extraction.py        # browser_get_html, browser_console, cookies, storage
│   ├── frames.py            # browser_list_frames, browser_scan_frames, etc.
│   ├── interaction.py       # browser_click, browser_type, browser_fill, etc.
│   ├── navigation.py        # browser_navigate, browser_scroll, tabs, waits
│   ├── vision.py            # browser_screenshot, browser_pdf, etc.
│   ├── catalog.py           # Tool discovery and schema generation
│   └── smart_tools.py       # High-level enterprise tools
├── mcp/server.py            # v2 MCP server (preferred)
├── mcp_server.py            # Legacy MCP server (deprecated)
└── cli.py                   # CLI interface
```

## Key Patterns

### 1. Tool Discovery
Tools are auto-discovered from modules in `catalog.TOOL_MODULES`. Any `async def browser_*`
function is automatically registered. Do NOT manually register tools.

### 2. Manager Singleton
Always use `from sin_browser_tools.core import manager` (not `from ... import BrowserManager`).
The `manager` object is a proxy that auto-starts the browser on first use.

```python
from sin_browser_tools.core import manager

page = manager.page  # Auto-starts browser if needed
await manager.cleanup()  # Always cleanup when done
```

### 3. Return Conventions
All tools return a dict. On success, include `"status": "success"` or relevant data.
On failure, include `"error": "message"` and optionally `"hint": "guidance"`.

```python
# Success
return {"status": "success", "data": result, "ref_count": 5}

# Error
return {"error": "Element not found", "hint": "Try browser_snapshot first"}
```

### 4. Ref-ID System
Elements are identified by `@eN` refs (e.g., `@e1`, `@e2`) from `browser_snapshot`.
These refs are stored in `manager.registry` and are page-local (invalidated on navigation).

## Common Tasks

### Adding a New Tool

1. Add function to appropriate module in `tools/`
2. Follow naming: `async def browser_<action>(...) -> dict`
3. Add docstring with Args, Returns, Example
4. Add test in `tests/test_tool_smoke.py`
5. Update `API.md`

### Fixing a Bug

1. Write a failing test first
2. Fix the bug
3. Ensure all tests pass: `python -m pytest`
4. Run linter: `ruff check .`

### Understanding Frame Tools (Issue #11, #15)

The frame tools solve a specific problem: content inside shadow DOM or unnamed iframes
(like GMX webmail) is invisible to `browser_snapshot`. Use:

- `browser_list_frames()` — see all frames
- `browser_snapshot_in_frame(frame_name, selector, pierce_shadow=True)` — pierce shadow DOM
- `browser_scan_frames(pattern)` — search ALL frames for text

## Testing

```bash
python -m pytest              # All tests
python -m pytest -k "frame"   # Tests matching pattern
python -m pytest -v           # Verbose output
```

The `live_manager` fixture in `conftest.py` provides a real browser instance with a
fixture page containing forms, buttons, iframes, and shadow DOM elements.

## Do NOT

- Do NOT use `from sin_browser_tools.core.manager import BrowserManager` directly
- Do NOT manually register tools (they're auto-discovered)
- Do NOT use `asyncio.run()` inside tools (they're already async)
- Do NOT return raw exceptions (catch and return `{"error": ...}`)
- Do NOT access `page.frames` without null checks (frames can detach)

## Do

- DO use type hints on all function signatures
- DO add docstrings with Args/Returns/Example
- DO return hints in error cases to help agents recover
- DO add smoke tests for new tools
- DO update documentation when adding/changing tools
