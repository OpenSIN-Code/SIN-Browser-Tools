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
pip install -e .
python -m playwright install chromium
```

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

## Documentation

See [ARCHITECTURE.md](./ARCHITECTURE.md), [API.md](./API.md), [OPENSIN_INTEGRATION.md](./OPENSIN_INTEGRATION.md)

## License

MIT
