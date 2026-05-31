# OpenSIN Integration

## MCP Server (Claude Desktop / Cursor)

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "sin-browser-tools": {
      "command": "uv",
      "args": ["--directory", "/path/to/SIN-Browser-Tools", "run", "sin-browser-mcp"]
    }
  }
}
```

## CLI Interface

```bash
sin-browser skills  # List all tools
sin-browser help    # Show help

sin-browser navigate "https://example.com"
sin-browser snapshot
sin-browser click "@e1"
sin-browser screenshot
```

## Python API

```python
from sin_browser_tools import manager, skill
from sin_browser_tools.tools import navigation, accessibility

await manager.start_local()
await navigation.browser_navigate("https://example.com")
snapshot = await accessibility.browser_snapshot()
```

## Configuration

Create `.opencode/config.json`:

```json
{
  "browser": {"headless": true},
  "cdp": {"auto_scan": true, "ports": [9222, 9223, 9224]}
}
```
