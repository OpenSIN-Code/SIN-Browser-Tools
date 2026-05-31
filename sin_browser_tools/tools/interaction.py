import asyncio
import re

from sin_browser_tools.core import manager


def _is_cdp_descriptor(value) -> bool:
    return isinstance(value, dict) and "backendDOMNodeId" in value


def _descriptor_frame(descriptor: dict):
    """Return the Playwright Frame a CDP descriptor belongs to.

    Snapshots register the owning frame so that target-local backendDOMNodeIds
    and OOPIF input routing resolve against the correct renderer target. Older
    refs without a frame fall back to the page's main frame.
    """
    frame = descriptor.get("frame")
    if frame is not None:
        return frame
    return manager.page.main_frame


async def _resolve_target(target: str):
    """Resolve a target string to a Playwright handle/selector or CDP descriptor.

    - ``@eN`` -> looks up the registry. May return a Playwright ElementHandle
      or a CDP descriptor dict (``{"backendDOMNodeId": ..., "frame": ...}``).
    - any other string -> treated as a CSS/text selector.
    """
    if target.startswith("@e"):
        resolved = manager.registry.get(target)
        if resolved is None:
            raise ValueError(
                f"Ref-ID {target} not found. Refs expire on navigation/reload -- "
                f"call browser_snapshot (or browser_snapshot_full_oopif) again to "
                f"get fresh refs before interacting."
            )
        return resolved
    return target


async def _playwright_click_descriptor(descriptor: dict, click_count: int = 1,
                                       button: str = "left") -> bool:
    """Try to click a descriptor via Playwright's role-based locator on its
    owning frame. Returns True on success, False if no confident match.

    This is the preferred path for OOPIFs because Playwright routes input into
    the correct cross-origin renderer internally -- no manual coordinate /
    offset math, which is what makes raw page-level CDP clicks miss OOPIFs.
    """
    role = descriptor.get("role")
    name = descriptor.get("name")
    if not role or not name:
        return False  # can't build a reliable accessible locator

    frame = _descriptor_frame(descriptor)
    try:
        locator = frame.get_by_role(role, name=name, exact=True).first
        if await locator.count() == 0:
            locator = frame.get_by_role(role, name=name).first
            if await locator.count() == 0:
                return False
        if click_count == 2:
            await locator.dblclick(timeout=5000)
        else:
            await locator.click(button=button, click_count=click_count, timeout=5000)
        return True
    except Exception:
        return False


async def _cdp_center(descriptor: dict):
    """Return the on-screen center (x, y) of a node via CDP, resolved on the
    node's OWNING FRAME session.

    Scrolls the node into view first (off-screen elements have no content
    quads), then tries ``DOM.getContentQuads`` and falls back to
    ``DOM.getBoxModel``. Coordinates returned for an OOPIF target are already in
    top-level viewport space, so they can be fed to top-level input.
    """
    backend_node_id = descriptor["backendDOMNodeId"]
    frame = _descriptor_frame(descriptor)
    cdp = await manager.context.new_cdp_session(frame)
    try:
        try:
            await cdp.send(
                "DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_node_id}
            )
        except Exception:
            pass  # best-effort; some nodes (e.g. <option>) don't support it

        quads_result = await cdp.send(
            "DOM.getContentQuads", {"backendNodeId": backend_node_id}
        )
        quads = quads_result.get("quads", [])
        if quads and quads[0]:
            q = quads[0]
            # quad = [x1,y1, x2,y2, x3,y3, x4,y4]; center = midpoint of opposite corners
            return (q[0] + q[4]) / 2, (q[1] + q[5]) / 2

        box = await cdp.send("DOM.getBoxModel", {"backendNodeId": backend_node_id})
        content = (box.get("model") or {}).get("content")
        if content and len(content) >= 8:
            xs = content[0::2]
            ys = content[1::2]
            return sum(xs) / len(xs), sum(ys) / len(ys)

        raise ValueError(
            "Element has no on-screen geometry (it may be hidden, "
            "display:none, or zero-sized). Re-snapshot or use a selector."
        )
    finally:
        try:
            await cdp.detach()
        except Exception:
            pass


async def _cdp_mouse(x: float, y: float, button: str = "left", click_count: int = 1):
    """Dispatch a native press/release mouse click at (x, y) via top-level CDP.

    Input is dispatched on the PAGE session: top-level mouse events hit-test
    down into OOPIFs automatically, and OOPIF-derived quads are already in
    top-level coordinates, so this lands inside the cross-origin frame.
    """
    cdp = await manager.context.new_cdp_session(manager.page)
    try:
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": button, "clickCount": click_count,
        })
        await asyncio.sleep(0.05)
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": button, "clickCount": click_count,
        })
    finally:
        try:
            await cdp.detach()
        except Exception:
            pass


async def browser_click(target: str) -> dict:
    """Click an element.

    Automatically routes CDP-backed refs (from ``browser_snapshot`` /
    ``browser_snapshot_full_oopif``) through the OOPIF-safe click path.
    Otherwise uses the high-level Playwright click.
    """
    resolved = await _resolve_target(target)

    if _is_cdp_descriptor(resolved):
        return await browser_click_cdp(target)

    if hasattr(resolved, "click"):
        await resolved.click(timeout=5000)
    else:
        await manager.page.click(resolved, timeout=5000)
    return {"status": "clicked", "target": target}


async def browser_click_cdp(target: str) -> dict:
    """Click a CDP-backed ref using a two-strategy approach with fallback.

    Strategy 1 (preferred): Playwright role-locator on the ref's owning frame.
      Playwright natively routes input into cross-origin OOPIF renderers, so
      this is the most reliable path for GMX/web.de-style mail lists.
    Strategy 2 (fallback): resolve on-screen coordinates via the frame's own CDP
      session and dispatch a native top-level ``Input.dispatchMouseEvent``.

    Falls back to the standard Playwright click when the target is not a
    CDP-backed ref.
    """
    resolved = await _resolve_target(target)
    if not _is_cdp_descriptor(resolved):
        if hasattr(resolved, "click"):
            await resolved.click(timeout=5000)
            return {"status": "clicked", "target": target}
        if isinstance(resolved, str):
            await manager.page.click(resolved, timeout=5000)
            return {"status": "clicked", "target": target}
        raise ValueError(f"Target {target} is not clickable via CDP")

    # Strategy 1: accessible role-locator on the owning frame.
    if await _playwright_click_descriptor(resolved):
        return {"status": "clicked_locator", "target": target}

    # Strategy 2: native coordinate click on the owning frame's geometry.
    cx, cy = await _cdp_center(resolved)
    await _cdp_mouse(cx, cy)
    return {"status": "clicked_cdp", "target": target, "coords": [cx, cy]}


async def browser_double_click(target: str) -> dict:
    """Double-click an element (works for both Playwright and CDP refs)."""
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        if await _playwright_click_descriptor(resolved, click_count=2):
            return {"status": "double_clicked_locator", "target": target}
        cx, cy = await _cdp_center(resolved)
        await _cdp_mouse(cx, cy, click_count=2)
        return {"status": "double_clicked_cdp", "target": target, "coords": [cx, cy]}
    if hasattr(resolved, "dblclick"):
        await resolved.dblclick(timeout=5000)
    else:
        await manager.page.dblclick(resolved, timeout=5000)
    return {"status": "double_clicked", "target": target}


async def browser_right_click(target: str) -> dict:
    """Right-click (context menu) an element."""
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        if await _playwright_click_descriptor(resolved, button="right"):
            return {"status": "right_clicked_locator", "target": target}
        cx, cy = await _cdp_center(resolved)
        await _cdp_mouse(cx, cy, button="right")
        return {"status": "right_clicked_cdp", "target": target, "coords": [cx, cy]}
    if hasattr(resolved, "click"):
        await resolved.click(button="right", timeout=5000)
    else:
        await manager.page.click(resolved, button="right", timeout=5000)
    return {"status": "right_clicked", "target": target}


async def browser_hover(target: str) -> dict:
    """Hover the mouse over an element (reveals menus / tooltips)."""
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        # Prefer Playwright's frame-aware hover (routes into OOPIFs correctly).
        role = resolved.get("role")
        name = resolved.get("name")
        frame = _descriptor_frame(resolved)
        if role and name:
            try:
                locator = frame.get_by_role(role, name=name, exact=True).first
                if await locator.count() == 0:
                    locator = frame.get_by_role(role, name=name).first
                if await locator.count() > 0:
                    await locator.hover(timeout=5000)
                    return {"status": "hovered_locator", "target": target}
            except Exception:
                pass
        cx, cy = await _cdp_center(resolved)
        cdp = await manager.context.new_cdp_session(manager.page)
        try:
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
        finally:
            try:
                await cdp.detach()
            except Exception:
                pass
        return {"status": "hovered_cdp", "target": target, "coords": [cx, cy]}
    if hasattr(resolved, "hover"):
        await resolved.hover(timeout=5000)
    else:
        await manager.page.hover(resolved, timeout=5000)
    return {"status": "hovered", "target": target}


async def browser_drag(source: str, target: str) -> dict:
    """Drag the source element and drop it onto the target element."""
    src = await _resolve_target(source)
    dst = await _resolve_target(target)

    # CDP-backed refs: do a manual press-move-release using coordinates.
    if _is_cdp_descriptor(src) or _is_cdp_descriptor(dst):
        sx, sy = await _cdp_center(src) if _is_cdp_descriptor(src) else (None, None)
        tx, ty = await _cdp_center(dst) if _is_cdp_descriptor(dst) else (None, None)
        if None in (sx, sy, tx, ty):
            raise ValueError("Drag with mixed CDP/handle targets is not supported")
        cdp = await manager.context.new_cdp_session(manager.page)
        try:
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": sx, "y": sy})
            await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1})
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tx, "y": ty})
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tx, "y": ty, "button": "left", "clickCount": 1})
        finally:
            try:
                await cdp.detach()
            except Exception:
                pass
        return {"status": "dragged_cdp", "source": source, "target": target}

    # High-level handles/selectors.
    if hasattr(src, "hover"):
        await src.hover()
        await manager.page.mouse.down()
        await dst.hover()
        await manager.page.mouse.up()
    else:
        await manager.page.drag_and_drop(src, dst)
    return {"status": "dragged", "source": source, "target": target}


async def browser_select_option(target: str, value: str = None, label: str = None) -> dict:
    """Select an option in a native <select> dropdown by value or visible label."""
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        raise ValueError(
            "select_option is not supported for CDP-backed refs; use a "
            "browser_snapshot() ref or a selector instead."
        )
    kwargs = {}
    if label is not None:
        kwargs["label"] = label
    elif value is not None:
        kwargs["value"] = value
    else:
        raise ValueError("Provide either 'value' or 'label'")

    if hasattr(resolved, "select_option"):
        selected = await resolved.select_option(**kwargs)
    else:
        selected = await manager.page.select_option(resolved, **kwargs)
    return {"status": "selected", "target": target, "selected": selected}


async def browser_check(target: str, checked: bool = True) -> dict:
    """Check or uncheck a checkbox / radio input."""
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        # No native check helper for CDP nodes; clicking toggles the control.
        return await browser_click_cdp(target)
    if checked:
        if hasattr(resolved, "check"):
            await resolved.check(timeout=5000)
        else:
            await manager.page.check(resolved, timeout=5000)
    else:
        if hasattr(resolved, "uncheck"):
            await resolved.uncheck(timeout=5000)
        else:
            await manager.page.uncheck(resolved, timeout=5000)
    return {"status": "checked" if checked else "unchecked", "target": target}


async def browser_type(target: str, text: str, clear: bool = True) -> dict:
    resolved = await _resolve_target(target)

    if _is_cdp_descriptor(resolved):
        # Focus the CDP node (frame-aware click), optionally clear, then type.
        # Keyboard input is delivered to the focused element, including OOPIFs.
        await browser_click_cdp(target)
        keyboard = manager.page.keyboard
        if clear:
            await keyboard.press("Control+A")
            await keyboard.press("Delete")
        await keyboard.type(text, delay=30)
        return {"status": "typed", "target": target, "text": text}

    if clear and hasattr(resolved, "fill"):
        await resolved.fill("")
    if hasattr(resolved, "type"):
        await resolved.type(text, delay=30)
    else:
        await manager.page.type(resolved, text, delay=30)
    return {"status": "typed", "target": target, "text": text}


async def browser_fill(target: str, value: str) -> dict:
    return await browser_type(target, value, clear=True)


async def browser_find_by_text(
    keyword: str, role: str = None, exact: bool = False
) -> dict:
    """Find registered interactive refs by their visible/accessible text.

    Solves Issue #4: instead of regex-parsing the ``browser_snapshot`` *text*
    (whose format varies -- role prefixes, quoting, OOPIF markers,
    "(unlabeled)" placeholders), this searches the structured registry that
    ``browser_click`` already resolves against. Run a snapshot first so refs
    exist.

    Args:
        keyword: text to look for (case-insensitive substring, or exact match
            when ``exact=True``).
        role: optional role filter, e.g. "button" or "link".
        exact: require an exact (case-insensitive) name match.

    Returns:
        ``{"matches": [{"ref": "@eN", "name": ..., "role": ...}, ...],
           "count": N}`` ordered best-match-first. Feed ``matches[0]["ref"]``
        straight into ``browser_click``.
    """
    matches = manager.registry.find_by_text(keyword, role=role, exact=exact)
    return {"keyword": keyword, "count": len(matches), "matches": matches}


async def browser_click_by_text(
    keyword: str, role: str = None, exact: bool = False
) -> dict:
    """Click the best-matching element by its visible/accessible text.

    Convenience wrapper around ``browser_find_by_text`` + ``browser_click`` so
    an agent never has to parse snapshot text to obtain a ref. Picks the
    highest-ranked match (exact > shortest name) and clicks it via the normal
    OOPIF-safe click path.

    If no registered ref matches, tries a live Playwright locator query
    (Issue #5 fix: handles DOM changes between snapshot and click, e.g. after
    SPA navigation or wake_gmx_mail()).

    Raises:
        ValueError: if no match found in registry AND no live locator matches
            the keyword (the message advises taking a fresh snapshot).
    """
    matches = manager.registry.find_by_text(keyword, role=role, exact=exact)
    
    if matches:
        # Found in the snapshot/registry -- use the ref
        best = matches[0]
        result = await browser_click(best["ref"])
        result["matched"] = {"ref": best["ref"], "name": best["name"], "role": best["role"]}
        result["match_count"] = len(matches)
        result["source"] = "registry"
        return result
    
    # Registry miss -- try a live locator as fallback (Issue #5).
    # This handles DOM changes between snapshot and click (e.g. SPA nav,
    # wake_gmx_mail, etc.). Map role to selector; fall back to a broad search.
    page = manager.page
    selectors = []
    if role:
        if role == "button":
            selectors = ["button", "[role=button]"]
        elif role == "link":
            selectors = ["a", "[role=link]"]
        else:
            selectors = [f"[role={role}]"]
    else:
        # No role specified -- search broadly (buttons, links, clickables)
        selectors = ["button", "a", "[role=button]", "[role=link]", "[onclick]"]
    
    # Bei exact=True einen anker-genauen, case-insensitiven Text-Filter bauen.
    # BUGFIX: Frueher wurde 'has_text=keyword if not exact else exact'
    # uebergeben -- bei exact=True landete also der Bool True (statt des
    # Suchtexts) im has_text-Filter, der dadurch wirkungslos war.
    text_filter = (
        re.compile(rf"^\s*{re.escape(keyword)}\s*$", re.IGNORECASE)
        if exact
        else keyword
    )

    locator = None
    for sel in selectors:
        try:
            loc = page.locator(sel, has_text=text_filter)
            count = await loc.count()
            if count > 0:
                locator = loc.first
                break
        except Exception:
            continue
    
    if not locator:
        raise ValueError(
            f"No interactive element matching {keyword!r}"
            + (f" with role={role!r}" if role else "")
            + " was found in the snapshot registry. Tried a live DOM search as"
            " fallback (to handle SPA changes, wake_gmx_mail, etc.) but also"
            " found nothing. Take a fresh browser_snapshot or"
            " browser_snapshot_full_oopif to update the ref store."
        )
    
    try:
        await locator.click()
        return {
            "status": "clicked",
            "matched": {"text": keyword, "role": role or "any"},
            "match_count": 1,
            "source": "live_locator",
        }
    except Exception as e:
        raise ValueError(
            f"Live locator matched {keyword!r} but click failed: {str(e)}"
        )


async def browser_upload_file(target: str, file_path: str) -> dict:
    resolved = await _resolve_target(target)
    if _is_cdp_descriptor(resolved):
        raise ValueError(
            "File upload is not supported for CDP-backed refs; use a "
            "browser_snapshot() ref or a selector instead."
        )
    if hasattr(resolved, "set_input_files"):
        await resolved.set_input_files(file_path)
    else:
        await manager.page.set_input_files(resolved, file_path)
    return {"status": "uploaded", "file": file_path, "target": target}
