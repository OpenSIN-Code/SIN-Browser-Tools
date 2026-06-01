# `observability.py`

Structured tracing and logging for browser automation.

## `TraceLogger`

Captures detailed traces of browser operations for debugging and monitoring.

### Features

- Structured JSON logging (compatible with ELK, Datadog, etc.)
- Operation timing and duration
- Error capture with context
- PII-safe (integrates with `PIIRedactor`)

### Usage

```python
logger = TraceLogger(service_name="browser-agent")

with logger.span("navigate", url="https://example.com") as span:
    await page.goto("https://example.com")
    span.set_attribute("title", await page.title())
# Automatically logs duration, success/failure, attributes
```

### Output Format

```json
{
  "timestamp": "2026-01-15T10:30:00.123Z",
  "service": "browser-agent",
  "operation": "navigate",
  "duration_ms": 1234,
  "status": "ok",
  "attributes": {
    "url": "https://example.com",
    "title": "Example Domain"
  }
}
```

### Integration with OpenTelemetry

```python
from opentelemetry import trace

logger = TraceLogger(
    service_name="browser-agent",
    otel_tracer=trace.get_tracer(__name__)
)
# Spans are now exported to your OTEL collector
```

## Integration

Used by `SmartBrowserTools` to trace all high-level operations. Traces include:
- Navigation events
- Element interactions
- Snapshot operations
- API interceptions
- Errors and retries
