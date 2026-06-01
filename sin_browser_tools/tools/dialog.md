# `tools/dialog.py`

Handles native JavaScript dialogs (`alert`, `confirm`, `prompt`,
`beforeunload`).

## Tools

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_dialog` | `(action, prompt_text?)` | Respond to a pending dialog. `action` is `"accept"` or `"dismiss"`. |
| `browser_wait_for_dialog` | `(timeout=10.0)` | Block until a dialog appears (or time out). |

### `browser_dialog(action, prompt_text=None)`

Respond to a **pending** dialog (alert, confirm, prompt, beforeunload) that has
already been captured by the async listener.

**Arguments:**
- `action` (str): `"accept"` or `"dismiss"` — whether to confirm or reject the dialog
- `prompt_text` (str, optional): For `prompt` dialogs, the text to enter (or None for default)

**Returns:**

Dialog responded:
```json
{"status": "accepted", "dialog_type": "alert", "message": "Are you sure?"}
```
or
```json
{"status": "dismissed", "dialog_type": "confirm", "message": "Delete item?"}
```

No pending dialog:
```json
{"status": "no_dialog_pending"}
```

**Example:**
```python
# Trigger an action that shows a dialog
await browser_click("button#delete")
# Then respond to it
result = await browser_dialog("accept")
if result["status"] == "accepted":
    print(f"Dialog message: {result['message']}")
else:
    print("No dialog was pending")
```

### `browser_wait_for_dialog(timeout=10.0)`

Block until a dialog appears, or time out if none appears.

**Arguments:**
- `timeout` (float, optional): Seconds to wait (default 10.0)

**Returns:**

Dialog detected:
```json
{"status": "dialog_detected", "type": "alert", "message": "Welcome!"}
```

Timeout (no dialog after N seconds):
```json
{"status": "timeout"}
```

**Example:**
```python
# Start an action that may show a dialog
await browser_click("button#maybe-dialog")
# Wait for it
result = await browser_wait_for_dialog(timeout=5.0)
if result["status"] == "dialog_detected":
    print(f"Got {result['type']}: {result['message']}")
    # Now respond to it
    await browser_dialog("accept")
else:
    print("No dialog appeared within 5 seconds")
```

## How it works
Dialogs are **captured asynchronously** by the listener attached in
`core/manager.py` (`BrowserManager._setup_dialog_handler`), which pushes each
event onto an internal queue. These tools pop from that queue via
`manager.get_next_dialog(timeout=..., consume=...)`.

- `browser_dialog` waits up to 3s for a queued dialog. If none, returns
  `{"status": "no_dialog_pending"}`. On `accept` for a `prompt`, it sends
  `prompt_text` (or the dialog's default value).
- `browser_wait_for_dialog` waits up to `timeout` and returns
  `{"status": "dialog_detected", ...}` or `{"status": "timeout"}`.

## Ordering & gotchas
- The dialog listener is installed **once per page** (deduplicated via a
  `WeakSet` of page objects), so a single alert is enqueued exactly once even
  after tab switches.
- Trigger the action that *causes* the dialog first, then call `browser_dialog`
  / `browser_wait_for_dialog` to consume it — the queue preserves arrival order.
- An un-consumed dialog can block subsequent page interactions; always resolve
  pending dialogs.
