# `mcp_server.py`

The MCP (Model Context Protocol) server entry point. Exposes every `browser_*`
tool over stdio to MCP clients (Claude Desktop, Cursor, Cline).

## What it does
- Builds the tool set once via `catalog.discover()` (`_TOOLS`) — a single source
  of truth shared with the OpenSIN skill registry.
- `handle_list_tools()` advertises each tool with its first-paragraph docstring
  as the description and `catalog.input_schema(fn)` as the `inputSchema`.
- `handle_call_tool(name, arguments)` lazily starts a headless browser on first
  use, dispatches to the tool coroutine, and returns the JSON result as
  `TextContent`.
- `main()` runs the server over `stdio_server()`.

## Agent-friendly error handling
Errors are never silent — each failure mode returns structured, actionable JSON:

| Situation | Response |
| --- | --- |
| Unknown tool name | `{ "error": "Unknown tool: …", "hint": "Call browser/list_tools…", "available": [...] }` |
| Bad/missing arguments (`TypeError`) | `{ "error": "Invalid arguments…", "expected_schema": {...} }` |
| Any other exception | `{ "error": "...", "tool": name }` (and `logger.exception`) |

## Run it
```bash
python -m sin_browser_tools.mcp_server   # via main()
```
Then point your MCP client's server config at that command. The browser
auto-starts headless on the first tool call; no manual `start_local` needed.

## Notes
- Tool names are the underscore form (`browser_click`) — see `catalog.md` for
  why slashes are forbidden.
- The server holds one shared `manager` (one browser) across calls; state
  (tabs, cookies, page) persists between tool invocations within a session.
