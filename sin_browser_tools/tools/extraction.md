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

### `browser_console(expression)`

Evaluate a JavaScript expression on the current page and return the stringified result.

**Arguments:**
- `expression` (str): JavaScript code to evaluate (e.g., `"document.title"`)

**Returns:**

Success:
```json
{"result": "Hello World", "type": "str"}
```

Error:
```json
{"error": "document.missing is not defined"}
```

**Example:**
```python
result = await browser_console("document.body.children.length")
if "result" in result:
    print(f"Found {result['result']} child elements")
else:
    print(f"Error: {result['error']}")
```

### `browser_get_cookies(url=None)`

Get cookies from the current browser context, optionally filtered by URL.

**Arguments:**
- `url` (str, optional): Filter cookies by this URL (domain/path match)

**Returns:**

```json
{"count": 3, "cookies": [
  {"name": "session_id", "value": "abc123", "domain": ".example.com", "path": "/"},
  {"name": "pref", "value": "dark_mode", "domain": ".example.com", "path": "/"}
]}
```

Empty cookies:
```json
{"count": 0, "cookies": []}
```

### `browser_set_cookie(name, value, url=None, domain=None, path="/")`

Set a cookie in the current browser context.

**Arguments:**
- `name` (str): Cookie name
- `value` (str): Cookie value
- `url` (str, optional): Scope by this URL (default: current page URL)
- `domain` (str, optional): Scope by this domain (e.g., `.example.com`); if set, ignores `url`
- `path` (str, optional): Cookie path (default `"/"`)

**Returns:**

```json
{"status": "set", "name": "my_cookie"}
```

Error:
```json
{"error": "Invalid domain or url"}
```

### `browser_clear_cookies()`

Clear all cookies from the current browser context.

**Returns:**

```json
{"status": "cleared"}
```

### `browser_get_html(selector=None, max_length=200000)`

Get the raw HTML of the page or a specific element.

**Arguments:**
- `selector` (str, optional): CSS selector to get HTML of a specific element; if None, gets entire page
- `max_length` (int, optional): Maximum HTML length before truncation (default 200000)

**Returns:**

Full content:
```json
{"html": "<html>...</html>"}
```

Truncated:
```json
{"html": "<html>...[truncated]", "truncated": true}
```

### `browser_get_links()`

Extract all links (`<a>` tags) from the page with text, href, title, and visibility.

**Returns:**

```json
{"links": [
  {"text": "Home", "href": "https://example.com/", "title": "Home page", "visible": true},
  {"text": "About", "href": "https://example.com/about", "title": "", "visible": false}
]}
```

### `browser_get_attribute(selector, name)`

Read a single attribute of an element.

**Arguments:**
- `selector` (str): CSS selector
- `name` (str): Attribute name (e.g., `"data-id"`, `"href"`)

**Returns:**

Found:
```json
{"result": "value123", "type": "str"}
```

Missing element:
```json
{"error": "No element matches selector: .not-there"}
```

### `browser_storage(area="local", action="get", key=None, value=None)`

Read/write browser `localStorage` or `sessionStorage`.

**Arguments:**
- `area` (str): `"local"` or `"session"` (default `"local"`)
- `action` (str): `"get"`, `"set"`, `"remove"`, or `"clear"`
- `key` (str, optional): Storage key (required for `set`/`remove`)
- `value` (str, optional): Storage value (required for `set`)

**Returns:**

Get all:
```json
{"method": "get", "result": {"user_id": "123", "theme": "dark"}}
```

Get one key:
```json
{"method": "get", "result": "dark"}
```

Set:
```json
{"method": "set", "result": "value stored"}
```

Remove:
```json
{"method": "remove", "result": "key removed"}
```

Clear:
```json
{"method": "clear", "result": "storage cleared"}
```

Error:
```json
{"error": "Invalid area: 'cookies'", "method": "get"}
```

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
