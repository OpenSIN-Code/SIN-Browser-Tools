# feat: Window-Control + macOS-Spaces (CDP + Hammerspoon/yabai)

## Goal
Enable AI agents to control the browser **window size/position** (small/medium/large/maximized/fullscreen) and **move the browser to another macOS Space** ("desktop") so it appears to run "in the background" while actually being a foreground window on a different Space.

## Context
- Plan: `docs/PLAN_WINDOW_SPACES_AND_FIXES.md`
- Bugfixes B1-B4: **Done** (Commit `63248dd`)
- Features F1+F2: **Open**

## Scope

### F1: Window Control (cross-platform, headful-only)
New module `core/window.py` with CDP `Browser.setWindowBounds` for:
- `browser_set_window_mode(small|medium|large|maximized|fullscreen)`
- `browser_set_window_bounds(left, top, width, height)`
- `browser_maximize_window`, `browser_minimize_window`, `browser_fullscreen_window`, `browser_restore_window`
- `browser_get_window_bounds`

### F2: macOS Spaces (Hammerspoon > yabai > AppleScript fallback)
New module `core/spaces.py` with backend auto-detection:
- `browser_list_spaces` — list all Spaces/desktops
- `browser_move_to_space(index)` — move browser window to another Space
- `browser_send_to_background_space` — find/create a non-visible Space and move there
- `browser_get_window_space` — which Space is the browser on?

**Backend priority (security-first):** Hammerspoon (only Accessibility permission, no SIP disable) > yabai (more powerful, may need SIP partial disable) > AppleScript (limited fallback with clear "unsupported" response).

## Acceptance Criteria
- [ ] `core/window.py` with WindowController class (CDP-based)
- [ ] `core/spaces.py` with SpaceController + backend auto-detection
- [ ] `tools/window.py` with 8+ window tools + 5 space tools
- [ ] Wiring: catalog.py, tools/__init__.py, mcp/server.py (v2)
- [ ] `.env.template` updated with SIN_WINDOW_*, SIN_SPACE_BACKEND
- [ ] Tests: `tests/test_window.py`, `tests/test_spaces.py` (macOS-only tests skipif)
- [ ] Docs: `docs/WINDOW_AND_SPACES.md`, `docs/PERMISSIONS_MACOS.md`

## Implementation
Full code blocks in `docs/PLAN_WINDOW_SPACES_AND_FIXES.md` sections 3-6.

## Risks
- macOS has no official public API for Space assignment — requires Hammerspoon or yabai with appropriate permissions (documented in PERMISSIONS_MACOS.md)
- Window tools are headful-only; headless-shell has no OS window — tools return clear hint instead of crashing
