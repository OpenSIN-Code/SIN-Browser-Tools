# Development Guide

## Local Setup

```bash
git clone https://github.com/OpenSIN-Code/SIN-Browser-Tools.git
cd SIN-Browser-Tools
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Testing

```bash
python test_all_tools.py
```

## Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Run browser non-headless:

```python
await manager.start_local(headless=False)
```

## Project Structure

```
sin_browser_tools/
├── core.py              # SINBrowserManager, ElementRegistry
├── mcp_server.py        # MCP Protocol Server
├── cli.py               # CLI interface
├── opensin_skill.py     # Tool registry
├── opensin_config.py    # Configuration
└── tools/               # 6 tool modules
```

## Common Tasks

### Add New Tool

Create function in tools/<category>.py, register in opensin_skill.py

### Connect Remote Chrome

```python
cdp_url = await manager.scan_cdp_ports()
await manager.connect_cdp(cdp_url)
```

### Extract Data with JavaScript

```python
from sin_browser_tools.tools import extraction
result = await extraction.browser_console("document.title")
```
