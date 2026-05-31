# SIN-Browser-Tools-Library

Native browser automation library inspired by Hermes Agent.

Features:
- 46 Native Tools (navigation, tabs, interaction, accessibility, vision, extraction, dialogs)
- Ref-ID System (@e1, @e2, ...) with CDP / OOPIF / Shadow-DOM support
- Schema-safe MCP tool names (`browser_*`, matching `^[a-zA-Z0-9_-]{1,64}$`)
- OpenSIN Compatible (registry auto-derived from the tool catalog)
- MCP Server (Claude Desktop, Cursor, Cline)
- CLI Interface

## Installation

```bash
git clone https://github.com/OpenSIN-Code/SIN-Browser-Tools.git
cd SIN-Browser-Tools

# 1. Python dependencies (canonical):
pip install -e .
#    ...or, if you prefer a plain requirements file:
#    pip install -r requirements.txt

# 2. REQUIRED: download the Chromium browser binary.
python -m playwright install chromium
```

> [!IMPORTANT]
> **Step 2 is not optional.** `playwright install chromium` downloads the actual
> browser and is **separate** from `pip install`. It is NOT a pip package, so it
> will never be pulled in by `pip install -e .` or `requirements.txt`. If you skip
> it, every tool fails at launch with an error like
> *"Executable doesn't exist ... run `playwright install`"*. This is the single
> most common setup mistake.

## Quick Start

```python
import asyncio
from sin_browser_tools.core import manager
from sin_browser_tools.tools import navigation, accessibility

async def main():
    await manager.start_local()
    await navigation.browser_navigate("https://example.com")
    snapshot = await accessibility.browser_snapshot()
    print(snapshot["tree"])
    await manager.cleanup()

asyncio.run(main())
```

## For AI agents (start here)

If you are an automation agent (or configuring one), read these FIRST — they are
written for agents that need explicit, literal instructions:

- **[AGENTS.md](./AGENTS.md)** — the operating manual: the snapshot→act→verify
  loop, golden rules, a tool decision table, and an Error→Fix table.
- **[COOKBOOK.md](./COOKBOOK.md)** — copy-paste, step-by-step recipes for common
  tasks (login, reading webmail in an OOPIF, forms, dialogs, new tabs, scraping).

Rule of thumb for agents: **always `browser_snapshot` before acting**, only use
`@eN` refs from the latest snapshot, and if a `browser_click` does nothing, retry
with `browser_click_cdp`. For webmail/iframe pages use `browser_snapshot_full_oopif`.

## Documentation

See [ARCHITECTURE.md](./ARCHITECTURE.md), [API.md](./API.md), [OPENSIN_INTEGRATION.md](./OPENSIN_INTEGRATION.md).

Per-module companion docs live next to each source file (e.g.
`sin_browser_tools/tools/interaction.md`).

## License

MIT
