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
from .core.result import normalize_result
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
        # BUGFIX #38: Use the public API to check if browser is started instead of
        # accessing private manager._instance attribute. The manager module provides
        # a get_instance() function or we check via the public 'started' property.
        # Previously accessing _instance directly violated encapsulation and could
        # break if the manager's internal structure changed.
        try:
            current_page = manager.page if manager.started else None
        except (RuntimeError, AttributeError):
            current_page = None
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
        # Auto-record-on-failure: behandelt auch "weiche" Fehler, bei denen ein
        # Tool kein Exception wirft, sondern {"error": ...} / {"ok": False}
        # zurueckgibt. Niemals Screen-Recording-Tools selbst tracken (Endlos-Loop).
        await _note_tool_result(name, result)
        result = normalize_result(result)
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
        await _note_tool_failure_safe(name, str(e))
        return [types.TextContent(type="text", text=json.dumps({"ok": False, "error": str(e), "tool": name}))]


async def _note_tool_result(name: str, result) -> None:
    """Leite Erfolg/Misserfolg eines Tool-Ergebnisses an den Manager weiter."""
    if name.startswith("browser_screen_record"):
        return  # nie das Recording-Tool selbst tracken
    inst = getattr(manager, "_instance", None)
    if inst is None:
        return
    is_failure = isinstance(result, dict) and (
        result.get("error") is not None or result.get("ok") is False
        or result.get("status") == "error"
    )
    try:
        if is_failure:
            await inst.note_tool_failure(name, str(result.get("error") or result))
        else:
            inst.note_tool_success()
    except Exception:  # pragma: no cover - defensive
        pass


async def _note_tool_failure_safe(name: str, error: str) -> None:
    """Wie oben, aber fuer den Exception-Pfad."""
    if name.startswith("browser_screen_record"):
        return
    inst = getattr(manager, "_instance", None)
    if inst is None:
        return
    try:
        await inst.note_tool_failure(name, error)
    except Exception:  # pragma: no cover - defensive
        pass


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
