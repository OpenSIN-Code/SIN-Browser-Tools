# `core.py`

Foundation of the library: the global browser session manager and the element
ref-id registry that every tool builds on.

## Exports

| Symbol | Kind | Purpose |
| --- | --- | --- |
| `ElementRegistry` | class | Maps stable ref-ids (`@e1`, `@e2`, …) to a target. |
| `SINBrowserManager` | class | Owns the Playwright lifecycle, active page, dialogs. |
| `manager` | singleton | The shared `SINBrowserManager` instance imported by all tools. |

## `ElementRegistry`

A ref-id points to **one of two** things:

1. A Playwright `ElementHandle` (high-level API).
2. A **CDP descriptor dict** for elements Playwright cannot resolve via
   selectors (OOPIF / Shadow-DOM nodes):

```python
{
    "backendDOMNodeId": int,   # node id — valid ONLY on its owning target
    "role": str,               # used to rebuild an accessible locator
    "name": str,
    "frame": Frame,            # the Playwright Frame the node lives in
}
```

> **Why `frame` matters:** `backendDOMNodeId`s are *target-local*. A node that
> lives in a cross-origin OOPIF must be resolved and clicked through that
> frame's own CDP session — never the page's. The registry stores the owning
> frame so `interaction.py` can route input across process boundaries.

`register(value)` returns the generated ref-id; `get(ref_id)` looks it up;
`clear()` resets the map (called at the start of every snapshot — **refs expire
on re-snapshot / navigation**).

## `SINBrowserManager`

| Method | Description |
| --- | --- |
| `start_local(headless=True)` | Launch a local Chromium context (1280×720). |
| `connect_cdp(cdp_url)` | Attach to an already-running Chrome over CDP. |
| `set_active_page(page)` | Switch the active page and (re)attach the dialog handler. Used by the tab tools. |
| `get_next_dialog(timeout=5.0)` | Pop the next captured `dialog` event, or `None`. |
| `cleanup()` | Close the browser and reset all state for reuse. |
| `scan_cdp_ports(host, ports)` | Static helper: probe common CDP ports for a live Chrome. |

### Dialog handling
`_setup_dialog_handler()` attaches **at most one** listener per page (tracked by
`id(page)` in `_dialog_pages`). Without this guard, every `set_active_page()`
call would stack another listener and a single alert would be enqueued N times.

### Lifecycle notes
- `cleanup()` fully resets `browser/context/page/playwright`, the dialog-page
  set and the registry, so the same `manager` instance can be restarted cleanly.
- `manager` is a module-level singleton — import it, don't instantiate your own.
