"""DEPRECATED legacy MCP entry point (``sin-browser-mcp-legacy``).

This is the original *flat* 48-tool catalog server. It is kept only for
backwards compatibility and still works, but new integrations should use the
v2 server at :mod:`sin_browser_tools.mcp.server` (entry point
``sin-browser-mcp``), which exposes the high-level Enterprise tools
(``smart_navigate``, ``deep_snapshot``, ``smart_interact`` ...).

Both servers share the same underlying ``core.manager`` and tool
implementations, so the legacy surface is a thin compatibility shim.
"""

import asyncio
import inspect
import json
import logging
import warnings

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .core import manager
from .tools import catalog

logger = logging.getLogger("sin-browser-mcp")
server = Server("sin-browser-tools")

# Single source of truth: the catalog discovers every browser_* coroutine
# across all tool modules, so the MCP surface never drifts from the code.
_TOOLS = catalog.discover()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    listed = []
    for mcp_name, fn in sorted(_TOOLS.items()):
        description = (inspect.getdoc(fn) or f"{mcp_name} browser tool").split("\n\n")[0].strip()
        listed.append(
            types.Tool(
                name=mcp_name,
                description=description,
                inputSchema=catalog.input_schema(fn),
            )
        )
    return listed


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = arguments or {}
    try:
        # BUGFIX: Frueher stand hier 'if not manager.page'. Das Proxy-Property
        # 'page' ruft intern _require() auf und WIRFT RuntimeError, solange noch
        # kein BrowserManager registriert ist -- also genau beim allerersten
        # Tool-Call. Folge: der Browser wurde nie automatisch gestartet, jeder
        # erste Call schlug mit RuntimeError fehl. Wir pruefen jetzt
        # exception-frei, ob bereits eine aktive Page existiert.
        current_page = getattr(manager._instance, "_page", None)
        if current_page is None:
            await manager.start_local(headless=True)

        fn = _TOOLS.get(name)
        if fn is None:
            # Never fail silently: tell the agent exactly what is available.
            available = sorted(_TOOLS.keys())
            return [types.TextContent(type="text", text=json.dumps({
                "error": f"Unknown tool: {name}",
                "hint": "Call browser/list_tools to see all available tools.",
                "available": available,
            }))]

        result = await fn(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
    except TypeError as e:
        # Almost always a bad/missing argument -> return the expected schema.
        fn = _TOOLS.get(name)
        schema = catalog.input_schema(fn) if fn else None
        return [types.TextContent(type="text", text=json.dumps({
            "error": f"Invalid arguments for {name}: {e}",
            "expected_schema": schema,
        }))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e), "tool": name}))]


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(server_name="sin-browser-tools", server_version="0.1.0"),
        )


def main():
    # Backwards compatible, but steer integrators toward the v2 server.
    message = (
        "sin-browser-mcp-legacy (sin_browser_tools.mcp_server) is deprecated. "
        "Use 'sin-browser-mcp' (sin_browser_tools.mcp.server) instead."
    )
    warnings.warn(message, DeprecationWarning, stacklevel=2)
    logger.warning(message)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
