# `tools/interaction.py`

All element interaction: clicking, typing, hovering, dragging, selecting,
checking, file upload. **Contains the OOPIF-safe click routing.**

## Tools

| Tool | Signature | Notes |
| --- | --- | --- |
| `browser_click` | `(target)` | Auto-routes CDP refs to the OOPIF-safe path. |
| `browser_click_cdp` | `(target)` | Two-strategy click with fallback (see below). |
| `browser_double_click` | `(target)` | Locator dblclick → CDP coord fallback. |
| `browser_right_click` | `(target)` | Context-menu click. |
| `browser_hover` | `(target)` | Frame-aware hover; reveals menus/tooltips. |
| `browser_drag` | `(source, target)` | Press-move-release (CDP or handles). |
| `browser_select_option` | `(target, value?, label?)` | Native `<select>` only (not CDP refs). |
| `browser_check` | `(target, checked=True)` | Checkbox/radio; CDP refs toggle via click. |
| `browser_type` | `(target, text, clear=True)` | Focus → optional clear → type. |
| `browser_fill` | `(target, value)` | Shorthand for `type(..., clear=True)`. |
| `browser_upload_file` | `(target, file_path)` | Selector/handle refs only. |

`target` is either a ref-id (`@eN`) from a snapshot or a CSS/text selector.

### `browser_click(target, button="left", force=False, timeout=30000)`

Click an element on the page. Auto-routes CDP descriptors via the OOPIF-safe
two-strategy approach; plain selectors use Playwright's `.click()`.

**Arguments:**
- `target` (str): ref-id (`@eN`), CSS selector, or text selector (`:text("Label")`)
- `button` (str, optional): `"left"`, `"right"`, or `"middle"` (default `"left"`)
- `force` (bool, optional): Skip scroll-into-view checks (default `False`)
- `timeout` (int, optional): Milliseconds to wait for element (default 30000)

**Returns:**

Clicked via Playwright locator (best path):
```json
{"status": "ok", "element": {"tag": "button", "id": "submit", "text": "Submit"}}
```

Clicked via CDP two-strategy fallback:
```json
{"status": "clicked_locator", "element": {...}}
```
or
```json
{"status": "clicked_cdp", "element": {...}}
```

Error (missing selector):
```json
{"status": "error", "error": "No element matches selector: .not-there"}
```

Timeout:
```json
{"status": "error", "error": "Timeout waiting for selector (30000ms)"}
```

**Example:**
```python
# Click by CSS selector
result = await browser_click("button.submit")
if result["status"] == "ok":
    print("Clicked successfully")
elif "error" in result:
    print(f"Click failed: {result['error']}")

# Click by text (any button containing "Delete")
await browser_click(":text('Delete')")

# Right-click for context menu
await browser_click("button", button="right")
```

### `browser_double_click(target, timeout=30000)`

Double-click an element.

**Returns:** Same as `browser_click` (status `ok`, `clicked_locator`, `clicked_cdp`, or `error`)

### `browser_right_click(target, timeout=30000)`

Right-click an element (show context menu).

**Returns:** Same as `browser_click`

### `browser_hover(target, timeout=30000)`

Hover over an element (triggers `:hover` CSS and can reveal tooltips/menus).

**Returns:**

```json
{"status": "ok", "element": {"tag": "button", "text": "Hover me"}}
```

### `browser_fill(target, value)`

**Alias for `browser_type(target, value, clear=True)`** — clear the field and type.

**Returns:**

```json
{"status": "ok", "element": {"tag": "input", "id": "email"}}
```

### `browser_type(target, text, clear=True, timeout=30000)`

Type text into a form field.

**Arguments:**
- `target` (str): ref-id or selector
- `text` (str): Text to type
- `clear` (bool, optional): Clear the field first (default `True`)
- `timeout` (int, optional): Milliseconds to wait (default 30000)

**Returns:**

```json
{"status": "ok", "element": {"tag": "input", "type": "text", "id": "search"}}
```

### `browser_check(target, checked=True, timeout=30000)`

Check or uncheck a checkbox/radio button.

**Arguments:**
- `target` (str): ref-id or selector
- `checked` (bool, optional): Whether to check (True) or uncheck (False) (default `True`)

**Returns:**

```json
{"status": "ok", "element": {"tag": "input", "type": "checkbox", "checked": true}}
```

### `browser_select_option(target, value=None, label=None, timeout=30000)`

Select an option from a native `<select>` element.

**Arguments:**
- `target` (str): ref-id or selector (CSS selectors only, not CDP refs)
- `value` (str, optional): Option `value` attribute to select
- `label` (str, optional): Option text (label) to select; if both `value` and `label` are given, `value` wins

**Returns:**

```json
{"status": "ok", "element": {"tag": "select", "id": "country", "value": "US"}}
```

Error (not a select):
```json
{"status": "error", "error": "Element is not a <select>"}
```

### `browser_drag(source, target, timeout=30000)`

Drag from `source` element to `target` element.

**Arguments:**
- `source` (str): ref-id or selector (starting position)
- `target` (str): ref-id or selector (ending position)

**Returns:**

```json
{"status": "ok", "element": {"tag": "div", "id": "draggable"}}
```

### `browser_upload_file(target, file_path, timeout=30000)`

Upload a file to an `<input type="file">` element.

**Arguments:**
- `target` (str): CSS selector or ref-id (selectors preferred over CDP refs)
- `file_path` (str): Absolute file path

**Returns:**

```json
{"status": "ok", "element": {"tag": "input", "type": "file", "value": "/path/to/file.txt"}}
```

Error:
```json
{"status": "error", "error": "File not found: /path/to/file.txt"}
```

## Two-strategy click (the important part)

`browser_click_cdp` handles refs that resolve to a **CDP descriptor** (OOPIF /
Shadow-DOM nodes) using a fallback chain:

1. **Strategy 1 — Playwright role-locator on the owning frame** (preferred):
   `frame.get_by_role(role, name=…)` then `.click()`. Playwright natively
   routes input into the correct cross-origin renderer, so there is **no manual
   coordinate math** — this is what makes OOPIF clicks reliable.
   Result status: `clicked_locator`.
2. **Strategy 2 — frame-scoped CDP coordinates** (fallback): compute the node's
   on-screen center via `_cdp_center` (resolved on the node's **owning frame**
   session), then dispatch a native top-level `Input.dispatchMouseEvent`.
   Result status: `clicked_cdp`.

Plain Playwright handles/selectors take the high-level `.click()` path
(status `clicked`).

### Why two strategies
Strategy 1 is correct in virtually all cases and avoids brittle geometry. But it
needs a usable `role` + `name`; when those are missing or ambiguous, Strategy 2
guarantees a click as long as the node has on-screen geometry.

## Key helpers

| Helper | Role |
| --- | --- |
| `_is_cdp_descriptor(v)` | True if `v` is a `{backendDOMNodeId, …}` dict. |
| `_descriptor_frame(d)` | Returns the descriptor's owning `Frame` (falls back to main frame for legacy refs). |
| `_resolve_target(target)` | `@eN` → registry lookup; else treats string as selector. Raises a clear "refs expire" error if missing. |
| `_playwright_click_descriptor(d, …)` | Strategy 1 implementation; returns `False` if no confident locator. |
| `_cdp_center(d)` | Scrolls into view, then `getContentQuads` → `getBoxModel` fallback, on the owning-frame session. |
| `_cdp_mouse(x, y, …)` | Native press/release on the **page** session (top-level events hit-test down into OOPIFs). |

## Gotchas
- `_cdp_center` resolves geometry on the **owning frame** session (quads are
  returned in top-level viewport coords); `_cdp_mouse` dispatches on the **page**
  session because top-level input hit-tests into OOPIFs. This split is
  intentional — don't "simplify" it to a single session.
- `select_option`, `upload_file` reject CDP refs (no native CDP equivalent) —
  use a `browser_snapshot()` handle ref or a selector.
- `browser_type` on a CDP ref focuses via a frame-aware click first, so typing
  lands in the right (possibly cross-origin) field.
