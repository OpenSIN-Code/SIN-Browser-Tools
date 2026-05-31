# `tools/dialog.py`

Handles native JavaScript dialogs (`alert`, `confirm`, `prompt`,
`beforeunload`).

## Tools

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_dialog` | `(action, prompt_text?)` | Respond to a pending dialog. `action` is `"accept"` or `"dismiss"`. |
| `browser_wait_for_dialog` | `(timeout=10.0)` | Block until a dialog appears (or time out). |

## How it works
Dialogs are **captured asynchronously** by the listener attached in
`core.py` (`SINBrowserManager._setup_dialog_handler`), which pushes each event
onto an internal queue. These tools pop from that queue via
`manager.get_next_dialog(timeout=...)`.

- `browser_dialog` waits up to 3s for a queued dialog. If none, returns
  `{"status": "no_dialog_pending"}`. On `accept` for a `prompt`, it sends
  `prompt_text` (or the dialog's default value).
- `browser_wait_for_dialog` waits up to `timeout` and returns
  `{"status": "dialog_detected", ...}` or `{"status": "timeout"}`.

## Ordering & gotchas
- The dialog listener is installed **once per page** (deduplicated by page id),
  so a single alert is enqueued exactly once even after tab switches.
- Trigger the action that *causes* the dialog first, then call `browser_dialog`
  / `browser_wait_for_dialog` to consume it — the queue preserves arrival order.
- An un-consumed dialog can block subsequent page interactions; always resolve
  pending dialogs.
