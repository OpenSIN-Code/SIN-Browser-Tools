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
| `browser_wait_for_text` | `(text, timeout=15000, pierce_shadow=True, poll_interval=500)` | Wait until text appears anywhere on the page (SPA-safe, Shadow DOM support). |
| `browser_wait_for_load` | `(state="networkidle", timeout=15000)` | Wait for `load`/`domcontentloaded`/`networkidle`. |
| `browser_wait_for_spa_transition` | `(target_text, timeout_ms=30000, pierce_shadow=True)` | MutationObserver-based instant detection when text appears in DOM. |

All waiters return `{"status": "timeout", ...}` or `{"found": false, ...}` instead of throwing, so an agent
can branch on the result.

### `browser_wait_for_text` (Issue #22)

This tool is designed for SPA multi-step content where URL/navigation events don't trigger:

**Features:**
- Polls at 500ms intervals (configurable via `poll_interval`)
- Searches across Shadow DOM boundaries (OPEN shadow roots)
- Returns element info (tag, id, className) for the first matching element
- Timeout with clear error message
- Works within iframes via `frame_name`/`frame_url` parameters

**Parameters:**
- `text` (required): The text substring to wait for
- `timeout`: Max wait time in ms (default: 15000)
- `pierce_shadow`: Search inside open Shadow DOM roots (default: True)
- `poll_interval`: Polling frequency in ms (default: 500)
- `frame_name`: Optional iframe name to search within
- `frame_url`: Optional iframe URL substring to match

**Return value:**

The contract is additive: the legacy `status` key (`"found"` / `"timeout"` /
`"error"`) is always present for backwards compatibility, alongside the Issue #22
`found` boolean and the element-info fields.

```json
{
  "status": "found",
  "found": true,
  "text": "Step 2: Select preferences",
  "element": {
    "tag": "h2",
    "id": "step-title",
    "className": "title",
    "text": "Step 2: Select preferences"
  },
  "matchCount": 1,
  "method": "poll"
}
```

On timeout:
```json
{
  "status": "timeout",
  "found": false,
  "text": "Step 2: Select preferences",
  "error": "Text 'Step 2: Select preferences' did not appear within 15000ms",
  "method": "timeout"
}
```

**Example use case (Fireworks onboarding):**
```python
# Step 1: Fill form and click Continue
await browser_fill("#email", "user@example.com")
await browser_click("Continue")

# Step 2: Wait for SPA content to swap (no URL change!)
result = await browser_wait_for_text("Step 2: Select your preferences")
if result["found"]:
    # Now interact with step 2 content
    await browser_click_checkbox_react("I agree to terms")
```

### `browser_wait_for_spa_transition` vs `browser_wait_for_text`

| Feature | `browser_wait_for_text` | `browser_wait_for_spa_transition` |
| --- | --- | --- |
| Detection method | Polling (500ms default) | MutationObserver (instant) |
| Element info returned | Yes (tag, id, className) | No |
| Best for | Need element info, slower transitions | Instant detection, fast SPAs |
| Shadow DOM | Yes (open roots) | Yes (open roots) |

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
