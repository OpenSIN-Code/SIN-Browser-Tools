# `tools/catalog.py`

The **single source of truth** for which `browser_*` tools exist. Both the MCP
server and the OpenSIN skill registry consume this catalog, so the advertised
tool surface can never drift away from the actual implementation.

## Exports

| Symbol | Description |
| --- | --- |
| `TOOL_MODULES` | Ordered list of tool modules scanned for `browser_*` coroutines. |
| `discover()` | `{ "browser_<action>": coroutine }` for every tool (incl. this module). |
| `input_schema(fn)` | JSON Schema for a tool's arguments (used as MCP `inputSchema`). |
| `specs()` | Full agent-readable catalog: name, function, description, params, required. |
| `browser_list_tools(filter?)` | A tool itself: lists every tool, optionally substring-filtered. |

## How discovery works
`discover()` walks each module in `TOOL_MODULES` (plus this module, so
`browser_list_tools` is itself discoverable) and collects every coroutine whose
name starts with `browser_`. The function name **is** the MCP tool name.

## Tool-name schema rule (critical)
MCP / Anthropic tool names must match `^[a-zA-Z0-9_-]{1,64}$`. Therefore tools
keep the **underscore** form (`browser_navigate`). A slash form
(`browser/navigate`) is rejected by Claude Desktop, Cursor and Cline and
**silently disables every tool** — do not introduce slashes.

## Parameter inference
`_param_specs(fn)` reads the function signature via `inspect`:
- Python type annotations map to JSON types through `_PY_TO_JSON`
  (`str→string`, `int→integer`, `float→number`, `bool→boolean`, `dict→object`,
  `list→array`; unknown → `string`).
- Parameters without a default are marked **required**; defaults are surfaced as
  `default` in the schema.
- `self`/`cls` and `*args`/`**kwargs` are ignored.

## Adding a new tool
1. Add an `async def browser_<action>(...)` in the relevant tool module.
2. Give it type-annotated params and a docstring (first paragraph = the
   description shown to agents).
3. That's it — discovery, MCP listing and the OpenSIN skill pick it up
   automatically. No registration list to edit.
