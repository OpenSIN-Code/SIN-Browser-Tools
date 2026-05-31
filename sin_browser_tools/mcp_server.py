import asyncio
import logging
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from .core import manager

logger = logging.getLogger("sin-browser-mcp")
server = Server("sin-browser-tools")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="browser/snapshot", description="Get accessibility tree", inputSchema={"type": "object", "properties": {}, "required": []}),
        types.Tool(name="browser/navigate", description="Navigate to URL", inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
        types.Tool(name="browser/click", description="Click element", inputSchema={"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}),
        types.Tool(name="browser/screenshot", description="Take screenshot", inputSchema={"type": "object", "properties": {}, "required": []}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if not arguments:
        arguments = {}
    try:
        if not manager.page:
            await manager.start_local(headless=True)
        return [types.TextContent(type="text", text=f"Tool {name} called")]
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(server_name="sin-browser-tools", server_version="0.1.0"))

def main():
    asyncio.run(_run())

if __name__ == "__main__":
    main()
