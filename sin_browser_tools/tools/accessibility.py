from urllib.parse import urlparse

from sin_browser_tools.core import manager

# Roles that are interactive/clickable and must stay in the snapshot even when
# they have no accessible name (e.g. icon-only buttons common on GMX/web.de).
_INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio", "switch", "tab",
    "menuitem", "menuitemcheckbox", "menuitemradio", "combobox", "listbox",
    "option", "searchbox", "slider", "spinbutton", "treeitem",
}


def _origin(url: str) -> str:
    """Return ``scheme://host[:port]`` for an URL, or ``""`` for about:blank etc."""
    try:
        p = urlparse(url or "")
        if not p.scheme or not p.netloc:
            return ""
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return ""


async def _collect_frame_axnodes(frame, pierce: bool) -> list:
    """Open a CDP session bound to ``frame`` and return its raw AX nodes.

    Binding the session to the *frame* (not the page) is what lets us read the
    accessibility tree of an OOPIF: a cross-origin iframe lives in its own
    renderer process / DevTools target, so ``Accessibility.getFullAXTree`` on
    the page target stops at the OOPIF boundary. ``new_cdp_session(frame)``
    attaches directly to the OOPIF's own target instead.
    """
    cdp = await manager.context.new_cdp_session(frame)
    try:
        await cdp.send("Accessibility.enable")
        tree = await cdp.send("Accessibility.getFullAXTree", {"pierce": pierce})
        return tree.get("nodes", [])
    finally:
        try:
            await cdp.detach()
        except Exception:
            pass


# Low-signal leaf roles that duplicate their parent's text. Emitting them as
# their own lines (and especially registering refs for them) just inflates the
# token cost and pollutes ref_count with non-actionable entries.
_NOISE_ROLES = {"InlineTextBox", "LineBreak"}


def _emit_node(node, frame, lines: list) -> None:
    """Process one CDP AX node: register interactive nodes (with their owning
    frame) and append a human-readable line to ``lines``."""
    if node.get("ignored"):
        return

    role = (node.get("role") or {}).get("value", "unknown")
    name = ((node.get("name") or {}).get("value") or "").strip()
    desc = ((node.get("description") or {}).get("value") or "").strip()
    val = (node.get("value") or {}).get("value", "")
    if isinstance(val, str):
        val = val.strip()

    # Drop pure text fragments (InlineTextBox/LineBreak): their content is
    # already covered by the parent StaticText/heading line.
    if role in _NOISE_ROLES:
        return

    is_interactive = role in _INTERACTIVE_ROLES
    # Skip empty structural containers, but ALWAYS keep interactive controls so
    # icon-only buttons remain clickable.
    if not name and not val and not desc and not is_interactive:
        return

    ref_str = ""
    backend_node_id = node.get("backendDOMNodeId")
    # Only INTERACTIVE nodes get an @eN ref. Previously every named node
    # (StaticText, headings, ...) was registered, so ref_count lied about how
    # many things were actually clickable and agents wasted clicks on plain text.
    if backend_node_id is not None and is_interactive:
        # Store the OWNING FRAME alongside the backendDOMNodeId. backendDOMNodeIds
        # are target-local, so a later click must resolve / dispatch on the same
        # frame's CDP session -- not the page's.
        ref_id = manager.registry.register(
            {
                "backendDOMNodeId": backend_node_id,
                "role": role,
                "name": name,
                "frame": frame,
            }
        )
        ref_str = f" [{ref_id}]"

    text = " ".join(part for part in (name, desc, str(val)) if part).strip()
    label = text if text else "(unlabeled)"
    lines.append(f'- {role} "{label}"{ref_str}')


async def _build_axtree(pierce: bool) -> dict:
    """Shared CDP accessibility-tree builder with OOPIF support.

    Strategy:
      1. Scan the main frame with ``getFullAXTree(pierce=...)``. With ``pierce``
         this already covers Shadow-DOM roots and *same-process* iframes.
      2. Additionally scan every cross-origin frame with its own CDP session.
         Those are OOPIFs (separate renderer target) that ``pierce`` cannot
         reach from the page target -- this is the GMX/web.de mail-list case.

    Every named/interactive node is registered with its owning frame so
    ``browser_click`` can target it across process boundaries.
    """
    manager.registry.clear()
    lines = []

    page = manager.page
    main_frame = page.main_frame
    main_origin = _origin(main_frame.url)

    # Build the scan list: main frame first, then each OOPIF (cross-origin) frame.
    frames_to_scan = [main_frame]
    for fr in page.frames:
        if fr is main_frame:
            continue
        fr_origin = _origin(fr.url)
        # A cross-origin frame is (under site isolation) an OOPIF. Same-origin
        # subframes are already included in the main frame's pierced tree, so we
        # skip them to avoid duplicate refs.
        if fr_origin and fr_origin != main_origin:
            frames_to_scan.append(fr)

    # Total cross-origin frames present on the page (whether or not the scan of
    # each succeeds). Used to advise the agent even when a frame fails to scan.
    oopif_present = len(frames_to_scan) - 1

    oopif_count = 0
    scan_failures = 0
    for frame in frames_to_scan:
        is_oopif = frame is not main_frame
        try:
            nodes = await _collect_frame_axnodes(frame, pierce)
        except Exception as e:  # noqa: BLE001 - surface, don't abort whole scan
            scan_failures += 1
            lines.append(f'- (frame scan failed: {_origin(frame.url)} -- {e})')
            continue

        if is_oopif and nodes:
            oopif_count += 1
            lines.append(f'- iframe "[OOPIF #{oopif_count}: {_origin(frame.url)}]"')

        for node in nodes:
            _emit_node(node, frame, lines)

    ref_count = len(manager.registry)
    hints = _build_hints(
        pierce=pierce,
        ref_count=ref_count,
        oopif_present=oopif_present,
        oopif_scanned=oopif_count,
        scan_failures=scan_failures,
    )

    result = {
        "tree": "\n".join(lines),
        "ref_count": ref_count,
        "oopif_count": oopif_count,
        "method": "cdp_multitarget_pierce" if pierce else "cdp_multitarget",
    }
    if hints:
        # A single, copy-paste-able instruction for weak agents, plus the raw list.
        result["hint"] = " ".join(hints)
        result["hints"] = hints
    return result


def _build_hints(
    *,
    pierce: bool,
    ref_count: int,
    oopif_present: int,
    oopif_scanned: int,
    scan_failures: int,
) -> list:
    """Turn the scan outcome into plain, imperative advice for an agent.

    These strings are written to be acted on literally -- they name the exact
    next tool to call so a weak agent does not have to reason about OOPIFs.
    """
    hints: list = []

    # 1) The page has cross-origin iframes but this was the FAST snapshot.
    #    The mail list / embedded app most likely lives in there.
    if oopif_present > 0 and not pierce:
        hints.append(
            f"This page has {oopif_present} cross-origin iframe(s) (OOPIF). "
            "Important content (e.g. a webmail message list) is often inside "
            "them and may be missing here. Call browser_snapshot_full_oopif to "
            "capture them."
        )

    # 2) Nothing actionable was found at all.
    if ref_count == 0:
        if oopif_present > 0 and pierce:
            hints.append(
                "No interactive elements were found even with OOPIF scanning. "
                "The frame may still be loading -- wait briefly (browser_wait) "
                "and snapshot again."
            )
        elif not pierce and oopif_present == 0:
            hints.append(
                "No interactive elements were found. The page may not be loaded "
                "yet -- call browser_wait, then browser_snapshot again."
            )

    # 3) A frame's CDP session could not be opened.
    if scan_failures > 0:
        hints.append(
            f"{scan_failures} frame(s) could not be scanned. Retry with "
            "browser_snapshot_full_oopif, or browser_wait and snapshot again."
        )

    return hints


async def browser_snapshot() -> dict:
    """Accessibility snapshot of the current page.

    Scans the main document plus any cross-origin OOPIF frames and returns a
    readable tree with a ``ref_count`` of registered interactive nodes. Every
    named node gets a ref-id (@e1, @e2, ...) usable with ``browser_click`` /
    ``browser_type``.

    If the page looks empty or has cross-origin iframes, the result includes a
    ``hint`` string telling you exactly which tool to call next (e.g.
    ``browser_snapshot_full_oopif``). ALWAYS read ``hint`` if present and follow
    it before deciding the page has no usable content.
    """
    return await _build_axtree(pierce=False)


async def browser_snapshot_full_oopif(pierce: bool = True) -> dict:
    """Bulletproof snapshot for complex pages (OOPIFs, Shadow-DOM, GMX/web.de).

    Combines ``getFullAXTree(pierce=True)`` on the main frame (Shadow-DOM +
    same-process iframes) with a dedicated per-frame CDP session for every
    cross-origin OOPIF, so the entire accessibility tree is captured across
    process boundaries. Nodes are registered with their owning frame so they
    can be clicked via ``browser_click`` / ``browser_click_cdp``.
    """
    return await _build_axtree(pierce=pierce)
