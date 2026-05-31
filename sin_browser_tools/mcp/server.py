"""
MCP Server v2.0 -- Enterprise-Ready mit SmartBrowserTools.
Ersetzt den alten 46-Tool-Flat-Server durch High-Level Enterprise-Tools.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import structlog

from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.smart_tools import SmartBrowserTools

logger = structlog.get_logger(__name__)

server = Server("sin-browser-tools")
_manager = BrowserManager(headless=True, stealth=True)
_tools: SmartBrowserTools | None = None


async def _get_tools() -> SmartBrowserTools:
    global _tools
    if _tools is None:
        await _manager.start_local()
        _tools = SmartBrowserTools(
            _manager.page,
            _manager.context,
            _manager.tracer,
        )
    return _tools


TOOLS = [
    Tool(
        name="smart_navigate",
        description=(
            "Navigate to a URL with automatic session restore, SID-redirect detection, "
            "popup closing, and DOM stability waiting. Replaces browser_navigate."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "restore_session": {
                    "type": "boolean",
                    "default": True,
                    "description": "Attempt to restore saved session for this domain",
                },
                "close_popups": {
                    "type": "boolean",
                    "default": True,
                    "description": "Auto-close cookie banners and other popups",
                },
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="deep_snapshot",
        description=(
            "Accessibility snapshot across ALL frames (OOPIF + same-process + Shadow DOM). "
            "Replaces browser_snapshot and browser_snapshot_full_oopif. "
            "Optionally redacts PII before returning."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pierce_shadow": {
                    "type": "boolean",
                    "default": True,
                    "description": "Traverse Shadow DOM roots",
                },
                "redact_pii": {
                    "type": "boolean",
                    "default": True,
                    "description": "Remove emails, phones, SIDs before returning",
                },
            },
        },
    ),
    Tool(
        name="smart_interact",
        description=(
            "Interact with an element across all frames (click, hover, focus, scroll_into_view). "
            "Wakes up SPAs before interacting. Falls back across iframes automatically."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or Playwright locator",
                },
                "action": {
                    "type": "string",
                    "enum": ["click", "hover", "focus", "scroll_into_view"],
                    "default": "click",
                },
                "intent": {
                    "type": "string",
                    "description": "Human-readable intent for tracing",
                },
            },
            "required": ["selector"],
        },
    ),
    Tool(
        name="extract_structured_data",
        description=(
            "Extract data via network interception instead of DOM parsing. "
            "More robust for SPAs, GMX mail lists, and similar dynamic content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "api_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "URL substrings to intercept, e.g. ['/api/v3/', 'listMessages']",
                },
                "trigger_selector": {
                    "type": "string",
                    "description": "Optional CSS selector to click before waiting for responses",
                },
                "timeout_ms": {"type": "integer", "default": 10000},
            },
            "required": ["api_patterns"],
        },
    ),
    Tool(
        name="wait_for_stable_dom",
        description=(
            "Wait until the DOM stops changing. "
            "Better than fixed sleep() for SPAs and dynamic content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "timeout_ms": {"type": "integer", "default": 15000},
            },
        },
    ),
    Tool(
        name="close_popups",
        description="Close common popups (cookie banners, newsletters, modals).",
        inputSchema={"type": "object", "properties": {}},
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    tools = await _get_tools()

    try:
        if name == "smart_navigate":
            result = await tools.smart_navigate(**arguments)
        elif name == "deep_snapshot":
            result = await tools.deep_snapshot(**arguments)
        elif name == "smart_interact":
            result = await tools.smart_interact(**arguments)
        elif name == "extract_structured_data":
            result = await tools.extract_structured_data(**arguments)
        elif name == "wait_for_stable_dom":
            result = await tools.wait_for_stable_dom(**arguments)
        elif name == "close_popups":
            result = await tools.close_popups()
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        logger.error("Tool call failed", tool=name, error=str(e))
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "tool": name}, indent=2),
            )
        ]


async def main():
    """Startet den MCP Server ueber stdio."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        await _manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
