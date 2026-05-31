# `tools/navigation.py`

Page navigation, scrolling, keyboard, viewport, waiting, and tab/window
management.

## Navigation & page state

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_navigate` | `(url)` | Go to a URL (`domcontentloaded`, 30s timeout). Returns HTTP status. |
| `browser_back` | `()` | History back. |
| `browser_forward` | `()` | History forward. |
| `browser_reload` | `()` | Reload current page. |
| `browser_scroll` | `(direction="down", amount=500)` | Scroll by pixels. |
| `browser_press` | `(key)` | Press a key/combo: `Enter`, `Control+A`, `Escape`. |
| `browser_get_url` | `()` | Current URL + title. |
| `browser_set_viewport` | `(width=1280, height=720)` | Resize viewport (responsive testing). |

## Waiting

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_wait_for` | `(selector, state="visible", timeout=10000)` | Wait for selector state (`attached`/`detached`/`visible`/`hidden`). |
| `browser_wait_for_text` | `(text, timeout=10000)` | Wait until text appears anywhere on the page. |
| `browser_wait_for_load` | `(state="networkidle", timeout=15000)` | Wait for `load`/`domcontentloaded`/`networkidle`. |

All waiters return `{"status": "timeout", ...}` instead of throwing, so an agent
can branch on the result.

## Tabs / windows

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_list_tabs` | `()` | All tabs with index, url, title, `active` flag. |
| `browser_new_tab` | `(url?)` | Open + focus a new tab; optional initial navigation. |
| `browser_switch_tab` | `(index)` | Focus the tab at `index` and bring it to front. |
| `browser_close_tab` | `(index?)` | Close a tab (defaults to active) and re-focus another. |

### Active-page semantics
The tab tools call `manager.set_active_page()`, which re-attaches the dialog
handler to the focused page. `browser_close_tab` only moves focus when the
**active** tab is closed — closing a background tab leaves your current tab
focused. If the last tab closes, `manager.page` becomes `None`.

## Notes
- Index ranges are validated; out-of-range raises a clear `ValueError`.
- `browser_navigate` waits for `domcontentloaded`, not `networkidle`; follow up
  with `browser_wait_for_load("networkidle")` for SPA-heavy pages.
