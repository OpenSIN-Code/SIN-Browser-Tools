# `tools/extraction.py`

Data extraction and low-level escape hatches: JS evaluation, raw CDP, cookies,
HTML, links, attributes, and web storage.

## Tools

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_console` | `(expression)` | `page.evaluate` an expression; returns stringified result + type. |
| `browser_cdp` | `(method, params={})` | Send a raw CDP command on a page-bound session. |
| `browser_get_cookies` | `(url?)` | Context cookies, optionally filtered by URL. |
| `browser_set_cookie` | `(name, value, url?, domain?, path="/")` | Add a cookie. |
| `browser_clear_cookies` | `()` | Clear all context cookies. |
| `browser_get_html` | `(selector?, max_length=200000)` | Raw HTML of page or element (truncated). |
| `browser_get_links` | `()` | Every `<a href>` with text, absolute href, title, visibility. |
| `browser_get_attribute` | `(selector, name)` | Read one attribute of an element. |
| `browser_storage` | `(area="local", action="get", key?, value?)` | Read/write `localStorage`/`sessionStorage`. |

## `browser_set_cookie` scoping rule
Playwright scopes a cookie **either** by `url` **or** by the `domain`+`path`
pair — never a mix. This tool enforces that: pass `domain` (with optional
`path`) for a domain-scoped cookie, otherwise it uses `url` (defaulting to the
current page URL).

## `browser_storage`
- `area`: `"local"` or `"session"`.
- `action`: `"get"` (one key or dump all), `"set"`, `"remove"`, `"clear"`.
- `set`/`remove` require `key`; invalid `area`/`action` raise `ValueError`.

## Gotchas
- `browser_console` returns the result **stringified** (`str(result)`), so
  objects come back as their string form, not structured JSON.
- `browser_get_html` truncates to `max_length` and sets `"truncated": true` when
  it had to cut — raise the limit deliberately for large pages.
- `browser_cdp` uses a page-target session, so it does **not** reach OOPIFs; for
  cross-origin frame work use the snapshot/click tools that bind sessions to the
  owning frame.
- Errors are returned as `{"error": ...}` rather than raised, so agents can
  branch without try/except.
