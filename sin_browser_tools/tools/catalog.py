"""Central tool catalog / registry.

This module is the single source of truth for which ``browser_*`` tools exist.
Both the MCP server (for ``list_tools`` / dispatch) and the in-process
``browser_list_tools`` discovery tool consume this catalog, so the advertised
tool surface can never drift away from the actual implementation.
"""

import inspect

from sin_browser_tools.tools import (
    accessibility,
    dialog,
    diagnostics,
    extraction,
    frames,
    interaction,
    navigation,
    vision,
    learning,
    screen_record,
    window,
    sessions,
)

# Order matters only for stable, readable listings.
TOOL_MODULES = [
    navigation,
    interaction,
    accessibility,
    extraction,
    vision,
    dialog,
    frames,
    learning,
    screen_record,
    window,
    sessions,
    diagnostics,
]

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


def _param_specs(fn) -> tuple[dict, list]:
    """Return (properties, required) describing a tool's parameters."""
    sig = inspect.signature(fn)
    properties: dict = {}
    required: list = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = (
            param.annotation if param.annotation is not inspect.Parameter.empty else str
        )
        prop = {"type": _json_type(annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default
        properties[pname] = prop
    return properties, required


def input_schema(fn) -> dict:
    """JSON schema for a tool's arguments (used by MCP ``inputSchema``)."""
    properties, required = _param_specs(fn)
    return {"type": "object", "properties": properties, "required": required}


def discover() -> dict:
    """Map MCP tool names (``browser_<action>``) -> coroutine functions.

    Tool names MUST match the MCP / Anthropic schema ``^[a-zA-Z0-9_-]{1,64}$``,
    so we keep the underscore form (``browser_navigate``) verbatim. Using a
    slash (``browser/navigate``) is rejected by Claude Desktop, Cursor and Cline
    and silently disables every tool.

    Includes this module too, so ``browser_list_tools`` is itself discoverable.
    """
    tools: dict = {}
    modules = TOOL_MODULES + [__import__(__name__, fromlist=["_self"])]
    seen = set()
    for module in modules:
        if module in seen:
            continue
        seen.add(module)
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if not name.startswith("browser_"):
                continue
            # Keep the function name as the MCP tool name (valid, schema-safe).
            tools[name] = fn
    return tools


def specs() -> list[dict]:
    """Full, agent-readable catalog: name, description, params, required."""
    out = []
    for mcp_name, fn in sorted(discover().items()):
        doc = (inspect.getdoc(fn) or "").strip()
        summary = doc.split("\n\n")[0].replace("\n", " ").strip() if doc else mcp_name
        properties, required = _param_specs(fn)
        out.append(
            {
                "name": mcp_name,
                "function": fn.__name__,
                "description": summary,
                "parameters": properties,
                "required": required,
            }
        )
    return out


async def browser_list_tools(filter: str = None) -> dict:
    """List every available browser tool with its parameters.

    Call this first to discover exactly which actions exist and how to invoke
    them. Optionally pass ``filter`` to substring-match tool names (e.g.
    ``"click"`` or ``"tab"``).
    """
    catalog = specs()
    if filter:
        needle = filter.lower()
        catalog = [t for t in catalog if needle in t["name"].lower() or needle in t["description"].lower()]
    return {"count": len(catalog), "tools": catalog}
