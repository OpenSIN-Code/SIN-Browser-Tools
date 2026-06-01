# `spa_waker.py`

SPA (Single Page Application) hydration detection and wake-up.

## Problem

Modern SPAs render a loading shell first, then hydrate with JavaScript. Actions
taken before hydration completes often fail silently or target stale elements.

## `SPAWaker`

Detects when an SPA is fully hydrated and ready for interaction.

### Detection Strategies

1. **Network idle**: No pending requests for N ms
2. **DOM stability**: No DOM mutations for N ms
3. **Custom markers**: Wait for app-specific ready signals

### Usage

```python
waker = SPAWaker(page)

# Wait for SPA to be ready
await waker.wait_ready(timeout=10.0)

# Or check current state
is_ready = await waker.is_ready()
```

### Configuration

```python
waker = SPAWaker(
    page,
    network_idle_ms=500,      # Wait for network to be idle
    dom_stable_ms=200,        # Wait for DOM to stop changing
    ready_selector="#app",    # Optional: wait for specific element
)
```

## Integration

Used by `SmartBrowserTools.smart_navigate()` to automatically wait for SPAs
to hydrate before returning control to the caller.

## Common Patterns

```python
# Navigate and wait for SPA
await page.goto("https://app.example.com")
await waker.wait_ready()
# Now safe to interact

# For known slow SPAs
await waker.wait_ready(timeout=30.0)
```
