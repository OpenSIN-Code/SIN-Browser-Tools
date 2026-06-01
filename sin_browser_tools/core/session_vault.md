# `session_vault.py`

Persistent session storage for cookies, localStorage, and sessionStorage.

## `SessionVault`

Saves and restores browser session state across runs.

### Usage

```python
vault = SessionVault(storage_path="~/.sin-browser/sessions")

# Save current session
await vault.save(context, session_id="gmx-login")

# Restore session in new context
await vault.restore(context, session_id="gmx-login")
```

### Stored Data

| Type | Description |
|------|-------------|
| Cookies | All cookies from the browser context |
| localStorage | Per-origin localStorage data |
| sessionStorage | Per-origin sessionStorage data |

### File Format

Sessions are stored as JSON files:
```
~/.sin-browser/sessions/
  gmx-login.json
  office365.json
```

Each file contains:
```json
{
  "cookies": [...],
  "origins": {
    "https://gmx.net": {
      "localStorage": {...},
      "sessionStorage": {...}
    }
  },
  "saved_at": "2026-01-15T10:30:00Z"
}
```

## Integration

Used by `SmartBrowserTools.smart_navigate()` to automatically restore sessions
when navigating to known domains.
