# Changelog

All notable changes to SIN-Browser-Tools.

## [Unreleased]

### Added — Diagnostics & Evidence Layer (CDP)
- **`core/evidence.py`**: CDP-based evidence engine. Opens a real `CDPSession`
  and subscribes losslessly to Network, Runtime, Log, Page, Performance and
  Target. Streams every event with `seq`, timestamps and a correlation
  `step_id` to `events.jsonl`. Stores request/response bodies as artifacts.
  Per-action before/after proof (screenshot, DOM dump, a11y snapshot, element
  details: backendNodeId, box-model, exact click coordinates, outerHTML,
  computed styles). Generates `report.md` + `report.html`. Adds
  `EvidenceRecorder.note()` so the error path is recorded as evidence.
- **`tools/diagnostics.py`**: 11 `browser_diag_*` MCP tools exposing the engine
  (`start`, `stop`, `status`, `snapshot_all`, `element`, `action`, `query`,
  `console`, `network`, `get_body`, `report`). Auto-discovered via the catalog.
- **`.opencode/skills/browser-evidence/SKILL.md`**: runtime forcing-function —
  no claim without evidence; mandatory start -> action -> query/console/network
  -> stop -> report lifecycle; strict bug-diagnosis protocol.
- **`.opencode/skills/browser-automation/SKILL.md`**: authoring skill for
  building browser automations with debug capture baked in (mandatory skeletons,
  capture checklist, anti-patterns, verification rule).
- **`docs/DIAGNOSTICS.md`** + **`docs/code/*.md`**: user docs and per-file
  companion docs (public API, data formats, pitfalls).

### Changed — Diagnostics & Evidence Layer
- **`tools/catalog.py`**: registered `diagnostics` in `TOOL_MODULES`.
- **`tools/__init__.py`**: exported `diagnostics`.

### Rationale
The built-in `TraceLogger` only listened to `page.on("response")` and captured
`url/status/method` — missing bodies, console logs, JS exceptions, lifecycle
events, performance metrics and all per-action DOM/element details. That forced
the agent to *guess* behavior instead of *establishing* it. The evidence layer
closes this gap with a full CDP event stream.

### Fixed
- **browser_wait_for_text return-contract regression** (Issue #28): the Issue #22
  enhancement switched the return dict from the `status` key ("found"/"timeout")
  to a `found` boolean, breaking every caller/test that checked
  `result["status"] == "found"`. The contract is now additive — both the legacy
  `status` key (`found`/`timeout`/`error`) and the new `found` boolean (plus the
  `element`/`matchCount`/`method` fields) are returned, restoring backwards
  compatibility without losing the Shadow DOM/element-info enhancements.

### Added
- **browser_wait_for_text enhancements** (Issue #22):
  - Shadow DOM support: Searches across OPEN shadow roots
  - Element info return: Returns tag, id, className of first matching element
  - Configurable polling: 500ms default interval (per spec), adjustable via `poll_interval`
  - Frame support: `frame_name` and `frame_url` parameters for iframe targeting
  - Clear timeout errors with method tracking
- **Window Control** (Issue #27 F1):
  - `browser_get_window_bounds` - Read window position/size/state
  - `browser_set_window_bounds` - Set exact pixel bounds
  - `browser_set_window_mode` - Preset sizes (small/medium/large/maximized/fullscreen)
  - `browser_maximize_window`, `browser_minimize_window`, `browser_fullscreen_window`, `browser_restore_window`
  - `browser_move_window` - Position window on screen
  - New `core/window.py` with CDP-based `WindowController`
- **macOS Spaces Control** (Issue #27 F2):
  - `browser_list_spaces` - List all virtual desktops
  - `browser_create_space` - Create new Space
  - `browser_move_to_space` - Move browser to specific Space
  - `browser_get_window_space` - Query current Space
  - `browser_send_to_background_space` - Auto-find/create background Space
  - New `core/spaces.py` with Hammerspoon/yabai/AppleScript backends
- Documentation: `WINDOW_AND_SPACES.md`, `PERMISSIONS_MACOS.md`

## [Unreleased]

### Added
- **browser_wait_for_text enhancements** (Issue #22):
  - Shadow DOM support: Searches across OPEN shadow roots
  - Element info return: Returns tag, id, className of first matching element
  - Configurable polling: 500ms default interval (per spec), adjustable via `poll_interval`
  - Frame support: `frame_name` and `frame_url` parameters for iframe targeting
  - Clear timeout errors with method info (`immediate`/`poll`/`timeout`)
- Updated `navigation.md` documentation with complete API reference for wait tools

### Added
- **Frame tools** (Issue #11, #12, #15):
  - `browser_list_frames` — list all frames on page
  - `browser_eval_in_frame` — run JS in specific frame by name/URL
  - `browser_snapshot_in_frame` — walk frame DOM with shadow-piercing
  - `browser_click_in_frame` — click a (shadow-DOM) element inside one frame,
    e.g. GMX/web.de `list-mail-item` mail rows (Issue #12)
  - `browser_scan_frames` — scan ALL frames for text/regex (unnamed iframe support)
- `browser_click_checkbox_by_text` (Issue #21) — click a checkbox by its visible
  label; pierces open shadow DOM, handles custom (non-`<input>`) checkboxes, and
  is SPA-safe (polls until the label appears).
- **Smoke test suite** — 59 end-to-end tests covering all tools
- `set_active_page` validation (Issue #14) — clear errors instead of cryptic crashes
- Hints in `browser_snapshot` pointing to frame tools when content is missing

### Fixed
- **Issue #7**: `browser_snapshot` / `browser_snapshot_full_oopif` crashed with
  `AttributeError: 'FrameInfo' has no attribute 'frame'`. Added and populated
  the `frame` field on `FrameInfo`.
- **Issue #11**: GMX mail list invisible (custom elements in shadow DOM). Solved
  by `browser_snapshot_in_frame` with `pierce_shadow=True`.
- **Issue #12**: GMX/web.de mail rows (`list-mail-item` custom elements in an
  iframe's open shadow DOM) could be read but not clicked. Solved by
  `browser_click_in_frame`, which routes a Playwright shadow-piercing locator
  click into the target frame.
- **Issue #21**: no way to tick a checkbox by its visible label when the control
  is a custom element / lives in shadow DOM / only appears after a prior SPA
  step. Solved by `browser_click_checkbox_by_text`.
- **Issue #1**: documented `uv pip` / `rtk pip` "No virtual environment found"
  and PEP 668 "externally-managed-environment" installs in the README.
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

## [Unreleased]

### Added
- **OpenCode CLI Skills** (Issue #26):
  - `sin-browser-automation`: Tool reference, correct sequencing, LOOK→DECIDE→ACT→VERIFY loop
  - `sin-browser-skill-authoring`: Generate reusable skills from proven runs (+ templates)
  - `sin-browser-learning`: Playbook system (record/suggest/list/compare), learn-by-doing, auto-ranking by success_rate
- **macOS Screen Recording + Vision Failure Diagnosis**:
  - `browser_screen_record_start/stop`: macOS screen recording (ffmpeg/screencapture auto-detect, window-region crop)
  - `browser_screen_record_analyze`: Extract ordered Base64 PNG keyframes for the agent to visually diagnose failures
  - Auto-record-on-failure hook: Start recording on first tool failure (macOS-only, `SIN_AUTO_RECORD_ON_FAILURE` env)
- **Playbook System** (`sin_browser_tools/playbook.py`):
  - `browser_playbook_suggest`: Retrieve best-known trajectories for a task (ranked by success_rate, avg_steps)
  - `browser_playbook_record`: Save/update playbook variant with auto-ranking
  - `browser_playbook_list/compare`: Browse and compare stored playbooks
- **Skill Generator** (`sin_browser_tools/skills/generator.py`):
  - `python -m sin_browser_tools.skills.generator --name <skill>`: Scaffold a new skill
  - `--validate <name>`: Check SKILL.md frontmatter, name consistency, tool existence
- **Configuration Wiring (B1-B4 Bugfixes)**:
  - **B1**: `opensin_config.py` now reads all SIN_* environment variables (SIN_HEADLESS, SIN_STEALTH, SIN_VIEWPORT_*, SIN_CDP_URL, SIN_SESSION_DIR, SIN_AUTO_RECORD_ON_FAILURE, etc.) with proper parsing and defaults; python-dotenv optional.
  - **B2+B3**: BrowserManager constructor now accepts Optional headless/stealth/executable_path (explicit args > config > defaults); signal handler modernized to use asyncio.get_running_loop() (no deprecated get_event_loop()).
  - **B4**: _kill_zombie_processes now supports both POSIX (pkill -TERM -P) and Windows (taskkill /T) for safe, targeted cleanup.

### Fixed
- **B1-B4 Bugfixes**:
  - Config environment variables (`SIN_HEADLESS`, etc.) were documented but never read — now wired into BrowserManager
  - Signal handler used deprecated `asyncio.get_event_loop()` (broken in Python 3.12+) — now uses `asyncio.get_running_loop()`
  - Zombie cleanup killed ALL Chromium processes (global pkill) — now kills only the specific browser PID tree
- **Auto-record-on-failure** was never wired — now connected to MCP dispatcher (incl. soft {error}/{ok:false} results)
- `browser_screen_record_analyze` was a placeholder — now returns ordered Base64 PNG keyframes for the vision-capable agent

### Documentation
- Tool count: 52 -> 64 (added learning, screen_record, and re-organized categorization)
- Added `frames.md`, `network_intercept.md`, `smart_tools.md`
- COOKBOOK: Recipes 9-10 for unnamed iframes and shadow DOM
- API.md: Full reference for all 52 tools

## [1.0.0] - 2026-05-15

Initial release with 46 tools.
