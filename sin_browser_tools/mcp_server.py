import asyncio
import inspect
import json
import logging

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .core import manager
from .tools import accessibility, dialog, extraction, interaction, navigation, vision

logger = logging.getLogger("sin-browser-mcp")
server = Server("sin-browser-tools")

# Modules whose ``browser_*`` coroutines are exposed as MCP tools.
_TOOL_MODULES = [navigation, interaction, accessibility, vision, extraction, dialog]

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _json_type(annotation) -> str:
    return _PY_TO_JSON.get(annotation, "string")


def _build_input_schema(fn) -> dict:
    """Generate a JSON schema for a tool from its function signature."""
    sig = inspect.signature(fn)
    properties = {}
    required = []
    for pname, param in sig.parameters.items():
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        properties[pname] = {"type": _json_type(annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {"type": "object", "properties": properties, "required": required}


def _discover_tools() -> dict:
    """Map MCP tool names (``browser/<action>``) -> coroutine functions.

    Every public ``browser_*`` coroutine across the tool modules is exposed,
    so the tool surface stays in sync with the implementation automatically.
    """
    tools = {}
    for module in _TOOL_MODULES:
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if not name.startswith("browser_"):
                continue
            mcp_name = "browser/" + name[len("browser_"):]
            tools[mcp_name] = fn
    return tools


_TOOLS = _discover_tools()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    listed = []
    for mcp_name, fn in sorted(_TOOLS.items()):
        description = (inspect.getdoc(fn) or f"{mcp_name} browser tool").split("\n\n")[0].strip()
        listed.append(
            types.Tool(
                name=mcp_name,
                description=description,
                inputSchema=_build_input_schema(fn),
            )
        )
    return listed


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = arguments or {}
    try:
        if not manager.page:
            await manager.start_local(headless=True)

        fn = _TOOLS.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        result = await fn(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
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
    asyncio.run(_run())


if __name__ == "__main__":
    main()
