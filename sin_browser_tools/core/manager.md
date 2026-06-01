# `manager.py`

Central browser lifecycle manager. The `BrowserManager` class and `manager` singleton.

## `BrowserManager`

Manages Playwright browser lifecycle, page state, and dialog handling.

### Key Methods

| Method | Description |
|--------|-------------|
| `start_local(headless=True)` | Launch a local Chromium browser |
| `connect_cdp(endpoint_url)` | Connect to existing browser via CDP |
| `cleanup()` | Close browser and release resources |
| `set_active_page(page)` | Switch active tab (validates input) |
| `get_next_dialog(timeout, consume)` | Pop/peek the dialog queue |

### Properties

| Property | Description |
|----------|-------------|
| `page` | Current active Playwright Page |
| `context` | Current BrowserContext |
| `browser` | Playwright Browser instance |
| `registry` | ElementRegistry for @eN refs |

### Dialog Handling

Dialogs (alert/confirm/prompt) are captured asynchronously via a listener
installed once per page (deduplicated by WeakSet). The queue is accessible via
`get_next_dialog(timeout, consume)`.

## `manager` Singleton

A proxy object that forwards attribute access to the registered `BrowserManager`
instance. Tools import `from sin_browser_tools.core import manager` and use
`manager.page`, `manager.start_local()`, etc.

### Proxy Behavior

- Public attributes are forwarded to `_require()` which returns the active manager
- Private/dunder attributes raise `AttributeError` (not forwarded) to support
  introspection (`inspect.getmembers`, `hasattr`, etc.)
- `_set_instance(mgr)` registers a manager; `_instance` holds the current one

## Common Patterns

```python
from sin_browser_tools.core import manager

# Start a new browser
await manager.start_local(headless=True)
await manager.page.goto("https://example.com")

# Connect to existing browser (e.g., user profile)
await manager.connect_cdp("http://localhost:9222")
pages = manager.browser.contexts[0].pages
manager.set_active_page(pages[0])

# Cleanup
await manager.cleanup()
```
