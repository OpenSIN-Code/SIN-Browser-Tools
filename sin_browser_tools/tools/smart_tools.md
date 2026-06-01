# `smart_tools.py`

High-level Enterprise tool suite. Powers the v2 MCP server (`sin-browser-mcp`).

## Overview

`SmartBrowserTools` wraps the low-level 52-tool catalog into a smaller set of
high-level operations with built-in:
- OOPIF and Shadow DOM support
- Session persistence (via `SessionVault`)
- PII redaction (via `PIIRedactor`)
- SPA wake-up (via `SPAWaker`)
- Structured tracing (via `TraceLogger`)

## Class: `SmartBrowserTools`

### Constructor

```python
tools = SmartBrowserTools(
    page: Page,
    context: BrowserContext,
    session_vault: SessionVault = None,
    pii_redactor: PIIRedactor = None,
    trace_logger: TraceLogger = None,
)
```

### Methods

#### `smart_navigate(url, wait_for="domcontentloaded")`
Navigate with automatic SPA wake-up and session restoration.

#### `deep_snapshot(pierce_oopif=True, pierce_shadow=True)`
Full-page snapshot across OOPIFs and shadow DOM. Returns the accessibility tree
plus frame metadata.

#### `smart_interact(target, action="click", value=None, force=False)`
Click, type, or fill with automatic:
- Ref-ID resolution (`@e1` -> element)
- OOPIF detection -> CDP click fallback
- Overlay handling (`force=True`)
- PII redaction in logs

#### `extract_structured(selector, fields)`
Extract structured data from repeating elements (e.g., email list rows).

```python
emails = await tools.extract_structured(
    selector="list-mail-item",
    fields={"subject": ".subject", "sender": ".from", "date": ".date"}
)
# [{"subject": "Invoice", "sender": "billing@...", "date": "2026-01-15"}, ...]
```

#### `intercept_api(url_pattern, trigger_action)`
Capture API responses during an action. Delegates to `network_intercept.py`.

## MCP Server Integration

The v2 MCP server (`sin_browser_tools/mcp/server.py`, entry point `sin-browser-mcp`)
exposes `SmartBrowserTools` methods as MCP tools:
- `smart_navigate`
- `deep_snapshot`
- `smart_interact`
- `extract_structured`

For the full 52-tool flat catalog, use the legacy server (`sin-browser-mcp-legacy`).

## When to Use

| Use Case | Recommended |
|----------|-------------|
| Simple automation scripts | Low-level tools (navigation, interaction, ...) |
| Enterprise webmail (GMX, O365) | `SmartBrowserTools` |
| Agent frameworks needing fewer tools | v2 MCP server |
| Full control / debugging | Legacy 52-tool catalog |

## Dependencies

- `core/frame_traversal.py` — OOPIF/Shadow DOM traversal
- `core/spa_waker.py` — SPA hydration detection
- `core/session_vault.py` — Cookie/storage persistence
- `core/pii_redaction.py` — Sensitive data masking
- `core/observability.py` — Structured tracing
- `tools/network_intercept.py` — API response capture
