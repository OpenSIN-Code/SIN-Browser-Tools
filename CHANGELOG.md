# Changelog

All notable changes to SIN-Browser-Tools.

## [Unreleased]

### Added
- **Frame tools** (Issue #11, #15):
  - `browser_list_frames` — list all frames on page
  - `browser_eval_in_frame` — run JS in specific frame by name/URL
  - `browser_snapshot_in_frame` — walk frame DOM with shadow-piercing
  - `browser_scan_frames` — scan ALL frames for text/regex (unnamed iframe support)
- **Smoke test suite** — 51 end-to-end tests covering all tools
- `set_active_page` validation (Issue #14) — clear errors instead of cryptic crashes
- Hints in `browser_snapshot` pointing to frame tools when content is missing

### Fixed
- **Issue #7**: `browser_snapshot` / `browser_snapshot_full_oopif` crashed with
  `AttributeError: 'FrameInfo' has no attribute 'frame'`. Added and populated
  the `frame` field on `FrameInfo`.
- **Issue #11**: GMX mail list invisible (custom elements in shadow DOM). Solved
  by `browser_snapshot_in_frame` with `pierce_shadow=True`.
- **Issue #14**: `set_active_page(None)` crashed with `'NoneType' has no attribute
  'context'`. Now validates input and gives a helpful error.
- **Issue #15**: Email body in unnamed `about:blank` iframe unreachable. Solved
  by `browser_scan_frames`.
- `browser_click_by_text(exact=True)` passed `has_text=True` (a bool) instead of
  the search text, making the filter a no-op. Now uses anchored regex.
- MCP server never auto-started browser — `manager.page` property threw before
  the browser could launch. Fixed by probing `_instance._page` exception-free.
- Manager proxy `__getattr__` forwarded private attributes to `_require()`,
  breaking introspection (`inspect.getmembers` in `catalog.discover()`). Now only
  forwards public names.
- IBAN redactions were not counted in `RedactionStats`. Added `ibans` field.
- Dialog handler was never ported from legacy `core.py` to v2 `BrowserManager`.
  `browser_dialog` / `browser_wait_for_dialog` always failed. Ported the full
  dialog queue + one-listener-per-page logic.

### Changed
- **DEPRECATED**: `sin-browser-mcp-legacy` (flat 52-tool server). Use
  `sin-browser-mcp` (v2 high-level tools) for new integrations.
- Deleted unreachable `sin_browser_tools/core.py` (shadowed by `core/` package).
- Test command: `python test_all_tools.py` -> `python -m pytest`

### Documentation
- Tool count: 46 -> 52
- Added `frames.md`, `network_intercept.md`, `smart_tools.md`
- COOKBOOK: Recipes 9-10 for unnamed iframes and shadow DOM
- API.md: Full reference for all 52 tools

## [1.0.0] - 2026-05-15

Initial release with 46 tools.
