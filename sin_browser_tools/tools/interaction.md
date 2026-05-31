# `tools/interaction.py`

All element interaction: clicking, typing, hovering, dragging, selecting,
checking, file upload. **Contains the OOPIF-safe click routing.**

## Tools

| Tool | Signature | Notes |
| --- | --- | --- |
| `browser_click` | `(target)` | Auto-routes CDP refs to the OOPIF-safe path. |
| `browser_click_cdp` | `(target)` | Two-strategy click with fallback (see below). |
| `browser_double_click` | `(target)` | Locator dblclick → CDP coord fallback. |
| `browser_right_click` | `(target)` | Context-menu click. |
| `browser_hover` | `(target)` | Frame-aware hover; reveals menus/tooltips. |
| `browser_drag` | `(source, target)` | Press-move-release (CDP or handles). |
| `browser_select_option` | `(target, value?, label?)` | Native `<select>` only (not CDP refs). |
| `browser_check` | `(target, checked=True)` | Checkbox/radio; CDP refs toggle via click. |
| `browser_type` | `(target, text, clear=True)` | Focus → optional clear → type. |
| `browser_fill` | `(target, value)` | Shorthand for `type(..., clear=True)`. |
| `browser_upload_file` | `(target, file_path)` | Selector/handle refs only. |

`target` is either a ref-id (`@eN`) from a snapshot or a CSS/text selector.

## Two-strategy click (the important part)

`browser_click_cdp` handles refs that resolve to a **CDP descriptor** (OOPIF /
Shadow-DOM nodes) using a fallback chain:

1. **Strategy 1 — Playwright role-locator on the owning frame** (preferred):
   `frame.get_by_role(role, name=…)` then `.click()`. Playwright natively
   routes input into the correct cross-origin renderer, so there is **no manual
   coordinate math** — this is what makes OOPIF clicks reliable.
   Result status: `clicked_locator`.
2. **Strategy 2 — frame-scoped CDP coordinates** (fallback): compute the node's
   on-screen center via `_cdp_center` (resolved on the node's **owning frame**
   session), then dispatch a native top-level `Input.dispatchMouseEvent`.
   Result status: `clicked_cdp`.

Plain Playwright handles/selectors take the high-level `.click()` path
(status `clicked`).

### Why two strategies
Strategy 1 is correct in virtually all cases and avoids brittle geometry. But it
needs a usable `role` + `name`; when those are missing or ambiguous, Strategy 2
guarantees a click as long as the node has on-screen geometry.

## Key helpers

| Helper | Role |
| --- | --- |
| `_is_cdp_descriptor(v)` | True if `v` is a `{backendDOMNodeId, …}` dict. |
| `_descriptor_frame(d)` | Returns the descriptor's owning `Frame` (falls back to main frame for legacy refs). |
| `_resolve_target(target)` | `@eN` → registry lookup; else treats string as selector. Raises a clear "refs expire" error if missing. |
| `_playwright_click_descriptor(d, …)` | Strategy 1 implementation; returns `False` if no confident locator. |
| `_cdp_center(d)` | Scrolls into view, then `getContentQuads` → `getBoxModel` fallback, on the owning-frame session. |
| `_cdp_mouse(x, y, …)` | Native press/release on the **page** session (top-level events hit-test down into OOPIFs). |

## Gotchas
- `_cdp_center` resolves geometry on the **owning frame** session (quads are
  returned in top-level viewport coords); `_cdp_mouse` dispatches on the **page**
  session because top-level input hit-tests into OOPIFs. This split is
  intentional — don't "simplify" it to a single session.
- `select_option`, `upload_file` reject CDP refs (no native CDP equivalent) —
  use a `browser_snapshot()` handle ref or a selector.
- `browser_type` on a CDP ref focuses via a frame-aware click first, so typing
  lands in the right (possibly cross-origin) field.
