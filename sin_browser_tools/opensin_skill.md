# `opensin_skill.py`

Builds the **OpenSIN skill registry** — the machine-readable catalog of actions
the agent can perform — directly from the central tool `catalog`.

## Why it's derived, not hand-written
This registry used to be a hand-maintained list that drifted out of sync with
the real implementation (wrong/invalid names, missing tools). It is now
generated from `sin_browser_tools.tools.catalog`, so it can **never** disagree
with the tools the MCP server actually exposes.

## Exports

| Symbol | Description |
| --- | --- |
| `ToolAction` | Dataclass: `name`, `description`, `category`, `params`, `enabled`, `tags`. |
| `SINBrowserSkill` | Builds `ToolAction`s from `catalog.specs()`. |
| `skill` | Module-level `SINBrowserSkill()` singleton. |
| `init_opensin_integration()` | Returns the `skill` singleton (integration hook). |

## Registry output
`skill.to_opensin_registry()` →
```jsonc
{
  "skill": "sin-browser-tools",
  "version": "0.1.0",
  "count": 46,
  "actions": { "browser_navigate": { "name": ..., "category": "navigation", "params": {...} }, ... }
}
```

## Categorization
`_category_for(tool_name)` maps each tool to a category (`navigation`,
`interaction`, `accessibility`, `vision`, `dialog`, `extraction`, `meta`, …)
via the `_CATEGORY_BY_PREFIX` table, matched against the action name (the part
after `browser_`).

> **Maintenance note:** when you add a tool with a new action prefix, add an
> entry to `_CATEGORY_BY_PREFIX` so it lands in the right category (otherwise it
> falls back to `misc`). The new OOPIF tools `snapshot_full_oopif` and
> `screenshot_element` already match the existing `snapshot` / `screenshot`
> prefixes.
