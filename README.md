# SIN-Browser-Tools-Library

Native browser automation library inspired by Hermes Agent.

Features:
- 18 Native Tools
- Ref-ID System (@e1, @e2, ...)
- OpenSIN Compatible
- MCP Server
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
