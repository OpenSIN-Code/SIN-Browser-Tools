# Error Recovery Guide

## Common failures and fixes

| Error | Symptom | Fix |
|-------|---------|-----|
| **Stale ref** | `@e7 not found` | Call `browser_snapshot()` first (refs reset per snapshot). |
| **OOPIF invisible** | Can't find text in an iframe | Use `browser_snapshot_full_oopif()` instead of `browser_snapshot()`. |
| **Shadow DOM** | Element exists but `browser_click` fails | Try `browser_click_cdp("@e7")` (CDP pierce shadow trees). |
| **Cookie banner blocks** | Click lands on banner, not target | Call `browser_click_by_text("Accept all")` first. |
| **Element moved** | Click position was correct, but button moved | Wait with `browser_wait_for_stable("@e7")` before click. |
| **Page still loading** | Actions execute on half-loaded page | Use `browser_wait_for_load("networkidle")` or `browser_wait_for_text("expected text")`. |
| **Dialog appeared** | Unexpected modal blocks everything | Use `browser_dialog("accept")` or `browser_dialog("dismiss")`. |
| **Multi-tab opened** | New window, but still on old tab | Use `browser_list_tabs()`, then `browser_switch_tab(tab_id)`. |

## Debug-record flow

1. Tool returns `ok: false`.
2. Start screen recording: `screen_record_start("failure")`.
3. Reproduce the failure (re-run the same action).
4. Stop recording: `screen_record_stop()` -> path.
5. Analyze: `screen_record_analyze(path, "what UI state caused the failure?")`.
6. Fix trajectory based on findings.
7. Retry + record playbook with the corrected sequence.
