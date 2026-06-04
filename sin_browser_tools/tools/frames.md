# `frames.py`

Frame traversal tools for shadow DOM and unnamed iframes. Solves Issue #11 (GMX
webmail) and Issue #15 (unnamed `about:blank` iframes).

## Why these tools exist

Modern webmail and enterprise apps (GMX, web.de, Office365) render content in:
- **Named iframes** with shadow DOM (email lists as `<list-mail-item>` custom elements)
- **Unnamed `about:blank` iframes** (email body after clicking a message)

The standard `browser_snapshot` uses the accessibility tree, which is blind to
custom elements (they have no ARIA roles). And `browser_snapshot_in_frame` needs
a frame name or URL — but unnamed iframes have neither.

These tools solve both problems.

## Tools

### `browser_list_frames()`
List all frames on the page (main frame, OOPIFs, same-process iframes).

```python
result = await browser_list_frames()
# {"count": 3, "frames": [{"index": 0, "name": "", "url": "https://..."}, ...]}
```

### `browser_eval_in_frame(expr, frame_name=None, frame_url=None)`
Run JavaScript in a specific frame, targeted by name or URL substring.

```python
# By name attribute
await browser_eval_in_frame("document.title", frame_name="mail")
# By URL substring
await browser_eval_in_frame("document.body.innerText", frame_url="webmailer.gmx")
```

### `browser_snapshot_in_frame(frame_name, frame_url, selector, pierce_shadow=True)`
Walk a frame's DOM with a CSS selector, descending into OPEN shadow roots.

```python
# Find all email items in the "mail" frame, piercing shadow DOM
result = await browser_snapshot_in_frame(frame_name="mail", selector="list-mail-item")
# {"count": 3, "items": [{"tag": "list-mail-item", "text": "Invoice 2026-01"}, ...]}
```

The `pierce_shadow=True` default is what makes this work: it descends into every
element's `shadowRoot` (if open) looking for matches, regardless of whether the
container itself matches the selector.

### `browser_scan_frames(pattern=None, regex=None, include_empty=False)`
Scan ALL frames for text content. Essential for unnamed `about:blank` iframes.

```python
# Find OTP verification links in any frame
await browser_scan_frames(pattern="verify")
# Find 6-digit codes using regex
await browser_scan_frames(regex=r"\d{6}")
# See all frames' text (debugging)
await browser_scan_frames(include_empty=True)
```

### `browser_click_in_frame(selector, index=0, frame_name=None, frame_url=None, text_filter=None)`
Click an element inside a frame via a Playwright locator, which **pierces open
shadow DOM** and dispatches a trusted click. Solves Issue #12: a plain
`evaluate(el => el.click())` is unreliable on shadow-DOM custom elements, whereas
a locator reaches them.

```python
# Click the 2nd email row (0-based) in the "mail" frame
await browser_click_in_frame(selector="list-mail-item", index=1, frame_name="mail")

# Or pick the row by its text (sender/subject) instead of an index
await browser_click_in_frame(selector="list-mail-item", text_filter="Invoice", frame_name="mail")
# {"status": "clicked", "matched": 1, "index": 0, ...}
```

The `index` lines up with the `index` field returned by
`browser_snapshot_in_frame` (both use document order), so you can snapshot to
read the rows, then click the one you want by its index. Returns a helpful
`error` (unknown frame, no match, or index out of range) instead of raising.

### `browser_type_in_frame(selector, text, index=0, frame_name=None, frame_url=None, text_filter=None, clear=True, submit=False)`
Type into a field inside a frame, also piercing open shadow DOM. The locator-based
companion to `browser_click_in_frame` for forms in same-process iframes / shadow DOM.

```python
# Replace a search box's value and submit it, inside the "mail" frame
await browser_type_in_frame(selector="input[type=search]", text="invoice",
                            frame_name="mail", submit=True)
```

## GMX Webmail Workflow (Issue #11 + #15)

```text
# 1. Login and navigate to inbox
browser_navigate("https://gmx.net")
browser_snapshot -> find login form -> browser_fill/click

# 2. Read email list (shadow DOM in named iframe)
browser_snapshot_in_frame(frame_name="mail", selector="list-mail-item")
# Returns: [{"index": 0, "text": "Invoice from X"}, {"index": 1, "text": "Welcome aboard"}, ...]

# 3. Click an email by snapshot index (fixes Issue #12)
browser_click_in_frame(selector="list-mail-item", index=1, frame_name="mail")
# Or by text: browser_click_in_frame(selector="list-mail-item", text_filter="Welcome", frame_name="mail")

# 4. Read email body (unnamed iframe)
browser_scan_frames(pattern="Your verification code")
# Returns: {"frames": [{"index": 2, "text": "... code is 123456 ..."}]}

# 5. Extract specific data
browser_scan_frames(regex=r"\d{6}")
# Returns: {"frames": [{"matches": ["123456"]}]}
```

## Implementation Notes

- Shadow DOM traversal iterates ALL elements at each root (not just selector
  matches), because the container element may not match while its shadow
  children do.
- Text extraction falls back to `shadowRoot.textContent` when the element's
  light DOM is empty (custom elements render inside their shadow).
- Cross-origin and detached frames are handled gracefully (empty text, no crash).
