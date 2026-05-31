# `test_all_tools.py`

A smoke-test script that exercises the core happy path end-to-end against a
real local browser.

## What it covers
1. `manager.start_local(headless=True)` — launch Chromium.
2. `browser_navigate("https://example.com")`.
3. `browser_snapshot()` — accessibility tree + ref count.
4. `browser_vision()` — screenshot.
5. `browser_get_images()`.
6. `browser_console("document.title")`.
7. `manager.cleanup()` in a `finally` block.

## Run it
```bash
python test_all_tools.py
```
Requires Playwright + a Chromium install:
```bash
pip install playwright && python -m playwright install chromium
```

## Notes & suggested additions
- This is a manual smoke test (prints `✓`/`✗`), not a pytest suite — exit status
  is not asserted per step.
- It does **not** yet cover the OOPIF path. To regression-test the fix, add a
  case that loads a page embedding a **cross-origin** iframe, calls
  `browser_snapshot_full_oopif()`, and asserts `oopif_count >= 1` plus a
  successful `browser_click` on a ref inside the OOPIF.
- Because it drives a real network site (`example.com`), it needs outbound
  network access.
