<!-- markdownlint-disable MD033 -->
<div align="center">
  <h1>SIN-Browser-Tools</h1>
  <p><strong>Native browser automation for AI agents — 54 tools, shadow DOM piercing, OOPIF support</strong></p>
</div>
<!-- markdownlint-enable MD033 -->

---

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-51%20passing-brightgreen)
![Tools](https://img.shields.io/badge/Tools-52-purple)

Browser automation library built for AI agents. Handles the hard parts: cross-origin iframes (OOPIFs), shadow DOM, native dialogs, and element targeting with stable ref-IDs.

> **Built for agents**: If you're an AI agent or configuring one, start with [AGENTS.md](./AGENTS.md) — it's written for you.

## Contents

- [Start Here](#start-here)
- [Why SIN-Browser-Tools](#why-sin-browser-tools)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Core Concepts](#core-concepts)
- [Tool Categories](#tool-categories)
- [MCP Server](#mcp-server)
- [Examples](#examples)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Start Here

| I want to... | Path | Get started |
|--------------|------|-------------|
| Automate a browser with Python | Direct API | [Quickstart](#quickstart) |
| Use with Claude/Cursor/Cline | MCP Server | [MCP Server](#mcp-server) |
| Build an AI agent | Agent integration | [AGENTS.md](./AGENTS.md) |
| See working examples | Examples directory | [examples/](./examples/) |
| Debug my automation | Debug helper | [examples/debug_helper.py](./examples/debug_helper.py) |

## Why SIN-Browser-Tools

| Capability | What it means |
|------------|---------------|
| **52 native tools** | Navigation, interaction, accessibility, vision, extraction, dialogs, frames |
| **OOPIF support** | See and click inside cross-origin iframes (GMX, embedded checkouts) |
| **Shadow DOM piercing** | Access content inside custom elements and shadow roots |
| **Ref-ID system** | Stable `@e1`, `@e2` targeting that survives DOM changes |
| **Frame scanning** | Find content in unnamed `about:blank` iframes |
| **MCP compatible** | Works with Claude Desktop, Cursor, Cline, any MCP client |

## Installation

```bash
git clone https://github.com/OpenSIN-Code/SIN-Browser-Tools.git
cd SIN-Browser-Tools
python -m venv .venv && source .venv/bin/activate   # recommended
pip install -e ".[dev]"
```

> [!IMPORTANT]
> **You must also install the browser binary:**
> ```bash
> python -m playwright install chromium
> ```
> This downloads the actual browser. Skipping it causes *"Executable doesn't exist"* errors.

> [!TIP]
> **Installing with `uv pip` / `rtk pip` or on a "managed" system** (Issue #1)
>
> `uv pip` / `rtk pip` refuse to install unless a virtual environment is active:
> ```
> error: No virtual environment found; run `uv venv` to create an environment,
> or pass `--system` to install into a non-virtual environment
> ```
> Pick one of:
> ```bash
> # (recommended) create + activate a venv first, then install
> uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
>
> # or install into the active interpreter explicitly (uv / rtk)
> uv pip install --system -e ".[dev]"
>
> # or, on PEP 668 "externally-managed-environment" systems, with plain pip
> python3 -m pip install -e ".[dev]" --break-system-packages
> ```
> A venv is strongly preferred — `--system` / `--break-system-packages` mutate the
> system interpreter and can conflict with OS-managed packages.

### Verify installation

```bash
python -m pytest tests/ -q
```

## Quickstart

```python
import asyncio
from sin_browser_tools.core import manager
from sin_browser_tools.tools import navigation, accessibility, interaction

async def main():
    # Start browser
    await manager.start_local()
    
    # Navigate
    await navigation.browser_navigate("https://example.com")
    
    # Get page snapshot (accessibility tree with ref-IDs)
    snapshot = await accessibility.browser_snapshot()
    print(snapshot["tree"])
    # Output: @e1 link "More information..." @e2 heading "Example Domain"
    
    # Click using ref-ID from snapshot
    await interaction.browser_click("@e1")
    
    # Cleanup
    await manager.cleanup()

asyncio.run(main())
```

## Core Concepts

### The Snapshot-Act-Verify Loop

```
1. browser_snapshot()     → See what's on the page (@e1, @e2, ...)
2. browser_click("@e3")   → Act on a specific element
3. browser_snapshot()     → Verify the result
```

### Ref-IDs (`@eN`)

Every interactive element gets a stable ref-ID like `@e1`, `@e2`. Use these instead of fragile CSS selectors:

```python
# From snapshot: "@e5 button 'Submit'"
await interaction.browser_click("@e5")  # Reliable
await interaction.browser_click("button.submit")  # Fragile
```

### Handling OOPIFs (Cross-Origin Iframes)

Some sites (GMX, web.de, payment forms) put content in cross-origin iframes. Normal snapshots miss these:

```python
# Regular snapshot - may miss iframe content
snapshot = await accessibility.browser_snapshot()

# Full OOPIF snapshot - sees everything
snapshot = await accessibility.browser_snapshot_full_oopif()
```

### Handling Shadow DOM

Content inside custom elements (shadow DOM) is invisible to normal queries:

```python
from sin_browser_tools.tools import frames

# Scan all frames for text (works across shadow DOM)
result = await frames.browser_scan_frames(pattern="Invoice")

# Snapshot specific frame with shadow piercing
result = await frames.browser_snapshot_in_frame(
    frame_name="mail", 
    selector="list-mail-item",
    pierce_shadow=True
)
```

## Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| **Navigation** | `navigate`, `back`, `forward`, `reload`, `scroll`, `press`, `wait_for*` | Move around pages |
| **Tabs** | `list_tabs`, `new_tab`, `switch_tab`, `close_tab` | Multi-tab workflows |
| **Interaction** | `click`, `click_cdp`, `type`, `fill`, `check`, `click_checkbox_by_text`, `select_option`, `hover`, `drag` | User actions |
| **Accessibility** | `snapshot`, `snapshot_full_oopif` | See page structure |
| **Frames** | `list_frames`, `eval_in_frame`, `snapshot_in_frame`, `click_in_frame`, `scan_frames` | Handle iframes/shadow DOM |
| **Vision** | `screenshot`, `screenshot_element`, `pdf`, `get_images`, `get_text` | Visual capture |
| **Extraction** | `console`, `cdp`, `get_html`, `get_links`, `get_attribute`, `storage`, `cookies` | Data extraction |
| **Dialog** | `dialog`, `wait_for_dialog` | Handle alerts/confirms/prompts |

See [API.md](./API.md) for complete tool reference.

## MCP Server

### Claude Desktop / Cursor / Cline

Add to your MCP config (`claude_desktop_config.json` or similar):

```json
{
  "mcpServers": {
    "sin-browser": {
      "command": "sin-browser-mcp",
      "args": []
    }
  }
}
```

### Start manually

```bash
# v2 server (recommended - high-level tools)
sin-browser-mcp

# Legacy server (all 54 tools flat)
sin-browser-mcp-legacy
```

## Examples

See [`examples/`](./examples/) for complete working examples:

| Example | Description |
|---------|-------------|
| [01_basic_navigation.py](./examples/01_basic_navigation.py) | Navigate, snapshot, extract |
| [02_form_interaction.py](./examples/02_form_interaction.py) | Fill forms, click buttons |
| [03_shadow_dom_frames.py](./examples/03_shadow_dom_frames.py) | Access shadow DOM and iframes |
| [04_screenshots_pdf.py](./examples/04_screenshots_pdf.py) | Capture screenshots and PDFs |
| [05_multi_tab.py](./examples/05_multi_tab.py) | Work with multiple tabs |
| [debug_helper.py](./examples/debug_helper.py) | Interactive REPL for debugging |

### Debug Helper

Interactive REPL for building and debugging automations:

```bash
python examples/debug_helper.py

debug> goto https://example.com
debug> snap
debug> frames
debug> scan "login"
debug> eval document.title
debug> shot
debug> quit
```

## Documentation

| Document | Purpose |
|----------|---------|
| [AGENTS.md](./AGENTS.md) | **Start here if you're an AI agent** — operating manual, rules, error fixes |
| [COOKBOOK.md](./COOKBOOK.md) | Copy-paste recipes for common tasks |
| [API.md](./API.md) | Complete tool reference |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design and internals |
| [CLAUDE.md](./CLAUDE.md) | Guide for AI coding assistants |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [CHANGELOG.md](./CHANGELOG.md) | Version history |

Per-module docs live next to source files (e.g., `sin_browser_tools/tools/frames.md`).

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for:

- Development setup
- Code style (ruff, pre-commit)
- Testing requirements
- PR process

```bash
# Quick setup
pip install -e ".[dev]"
pre-commit install
python -m pytest
```

## License

MIT — see [LICENSE](./LICENSE)
