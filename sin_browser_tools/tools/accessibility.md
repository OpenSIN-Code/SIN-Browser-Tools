# `tools/accessibility.py`

Builds the accessibility (AX) snapshot that agents use to "see" a page and to
obtain clickable ref-ids. **This module contains the OOPIF fix.**

## Tools

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_snapshot` | `() -> dict` | Standard snapshot (main doc + cross-origin OOPIFs), no Shadow-DOM piercing. |
| `browser_snapshot_full_oopif` | `(pierce: bool = True) -> dict` | Bulletproof snapshot: pierces Shadow-DOM **and** scans every OOPIF. Use for GMX / web.de / complex apps. |

### Return shape
```jsonc
{
  "tree": "- button \"Compose\" [@e1]\n- iframe \"[OOPIF #1: https://3c.gmx.net]\"\n  ...",
  "ref_count": 42,        // number of registered interactive nodes
  "oopif_count": 1,       // cross-origin frames that were scanned separately
  "method": "cdp_multitarget_pierce",
  "hint": "This page has 1 cross-origin iframe(s) (OOPIF). ... Call browser_snapshot_full_oopif to capture them.",
  "hints": ["...", "..."]  // same advice as a list; only present when relevant
}
```

### `hint` / `hints` (agent guidance)

When the snapshot looks empty or iframe-heavy, the result carries a plain,
imperative `hint` string (and a `hints` list) that names the **exact next tool
to call**. This lets a weak agent recover without reasoning about OOPIFs.

`_build_hints(...)` emits advice for these situations:

| Situation | Hint tells the agent to… |
| --- | --- |
| Fast `browser_snapshot` on a page with cross-origin iframes | call `browser_snapshot_full_oopif` (content may be inside the OOPIF) |
| `ref_count == 0` on a plain page | call `browser_wait`, then `browser_snapshot` again |
| `ref_count == 0` even with OOPIF scanning | `browser_wait` (frame still loading), then retry |
| One or more frames failed to scan | retry with `browser_snapshot_full_oopif` / `browser_wait` |

A clean, fully-loaded page returns **no** `hint` field. Agents should always
read `hint` if present and follow it before concluding the page is empty.

## The OOPIF problem this solves

`Accessibility.getFullAXTree(pierce=True)` on the **page target**:
- ✅ pierces Shadow-DOM roots,
- ✅ includes *same-process* (same-origin) iframes,
- ❌ **stops at cross-origin iframe boundaries.**

A cross-origin iframe under site isolation is an **OOPIF** — it runs in its own
renderer process with its own DevTools target. The page target literally cannot
see into it. This is exactly the GMX/web.de mail-list case (the message list is
served from a different origin than the shell).

## How the fix works

`_build_axtree(pierce)`:
1. **Main frame** — `getFullAXTree(pierce=...)` (covers Shadow-DOM + same-origin
   subframes in one shot).
2. **Each OOPIF** — for every frame whose origin differs from the main frame,
   open a dedicated `context.new_cdp_session(frame)` and call
   `getFullAXTree` against that frame's *own* target (`_collect_frame_axnodes`).
   Same-origin subframes are skipped to avoid duplicate refs.

Each emitted node (`_emit_node`) is registered **with its owning frame** so
`browser_click` can target it across process boundaries. Interactive roles
(`_INTERACTIVE_ROLES`) are kept even when unlabeled, so icon-only buttons (very
common on GMX/web.de) stay clickable.

### Helpers
- `_origin(url)` — `scheme://host[:port]`, used to detect cross-origin frames.
- `_collect_frame_axnodes(frame, pierce)` — frame-bound CDP session → raw AX
  nodes; always `detach()`es.
- `_emit_node(node, frame, lines)` — filters ignored/empty nodes, registers
  refs, appends a readable line.

## Gotchas
- Refs are cleared on every snapshot — always snapshot again after navigation.
- A frame that fails to scan is reported inline (`(frame scan failed: …)`) and
  does **not** abort the whole snapshot.
- `oopif_count` only counts cross-origin frames that returned nodes.
