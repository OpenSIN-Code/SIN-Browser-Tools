# `network_intercept.py`

Network interception tool for capturing API responses. A more robust alternative
to DOM parsing for modern SPAs.

## Why intercept network traffic?

Modern web apps (GMX, Salesforce, Office365) load their data via XHR/Fetch.
Intercepting the JSON response is often 100x more robust than DOM parsing:
- Unaffected by Shadow DOM or OOPIF rendering
- Independent of SPA rendering timing
- Returns structured data, not HTML

## Classes

### `InterceptedResponse`
Dataclass representing a captured HTTP response.

```python
@dataclass
class InterceptedResponse:
    url: str
    status: int
    method: str
    headers: dict
    body: Any = None  # Parsed JSON or raw text
    timestamp: float
```

### `NetworkInterceptor`
Context manager that captures responses matching a URL pattern.

```python
interceptor = NetworkInterceptor(page, url_pattern="api/mail")
async with interceptor:
    await page.click("#refresh")
    # Wait for API call to complete
responses = interceptor.responses  # List[InterceptedResponse]
```

## Functions

### `intercept_api_data(page, url_pattern, trigger_action, timeout=10.0)`
High-level helper: trigger an action and capture the resulting API response.

```python
# Click refresh and capture the mail list API response
data = await intercept_api_data(
    page,
    url_pattern="api/v1/mail/list",
    trigger_action=lambda: page.click("#refresh-btn"),
    timeout=5.0
)
# data = {"emails": [{"id": 1, "subject": "..."}, ...]}
```

## Use Cases

1. **Webmail**: Capture email list/body from API instead of scraping DOM
2. **SPAs**: Get structured data from REST/GraphQL endpoints
3. **Debugging**: See what data the page is actually loading
4. **Testing**: Verify API calls are made correctly

## Limitations

- Only works for same-origin or CORS-enabled requests
- Response body parsing assumes JSON; falls back to text
- Large responses may be truncated

## Integration with Smart Tools

The `SmartBrowserTools` class uses `intercept_api_data` internally for robust
data extraction. See `smart_tools.md`.
