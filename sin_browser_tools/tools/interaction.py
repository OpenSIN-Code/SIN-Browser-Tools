import asyncio

from sin_browser_tools.core import manager


def _is_cdp_descriptor(value) -> bool:
    return isinstance(value, dict) and "backendDOMNodeId" in value


async def _resolve_target(target: str):
    """Resolve a target string to a Playwright handle/selector or CDP descriptor.

    - ``@eN`` -> looks up the registry. May return a Playwright ElementHandle
      or a CDP descriptor dict (``{"backendDOMNodeId": ...}``).
    - any other string -> treated as a CSS/text selector.
    """
    if target.startswith("@e"):
        resolved = manager.registry.get(target)
        if resolved is None:
            raise ValueError(f"Ref-ID {target} not found")
        return resolved
    return target


async def browser_click(target: str) -> dict:
    """Click an element.

    Automatically routes CDP-backed refs (from ``browser_snapshot_full_oopif``)
    through the coordinate-based CDP click, which works across cross-origin
    iframes. Otherwise uses the high-level Playwright click.
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
    """Click an element via CDP ``Input.dispatchMouseEvent``.

    Resolves the element's on-screen coordinates with ``DOM.getContentQuads``
    and fires native mouse events, bypassing cross-origin iframe / OOPIF click
    restrictions that cause Playwright's ``element.click()`` to time out.

    Falls back to the standard Playwright click when the target is not a
    CDP-backed ref.
    """
    resolved = await _resolve_target(target)
    if not _is_cdp_descriptor(resolved):
        # Not a CDP ref -> fall back to the high-level click path.
        if hasattr(resolved, "click"):
            await resolved.click(timeout=5000)
            return {"status": "clicked", "target": target}
        if isinstance(resolved, str):
            await manager.page.click(resolved, timeout=5000)
            return {"status": "clicked", "target": target}
        raise ValueError(f"Target {target} is not clickable via CDP")

    backend_node_id = resolved["backendDOMNodeId"]
    cdp = await manager.context.new_cdp_session(manager.page)
    try:
        quads_result = await cdp.send(
            "DOM.getContentQuads", {"backendNodeId": backend_node_id}
        )
        quads = quads_result.get("quads", [])
        if not quads or not quads[0]:
            raise ValueError(f"No coordinates found for element {target}")

        q = quads[0]
        # A quad is [x1, y1, x2, y2, x3, y3, x4, y4]. The center is the average
        # of the top-left (x1,y1) and bottom-right (x3,y3) corners.
        cx = (q[0] + q[4]) / 2
        cy = (q[1] + q[5]) / 2

        await cdp.send(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": cx, "y": cy},
        )
        await cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": cx,
                "y": cy,
                "button": "left",
                "clickCount": 1,
            },
        )
        await asyncio.sleep(0.05)
        await cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": cx,
                "y": cy,
                "button": "left",
                "clickCount": 1,
            },
        )
        return {"status": "clicked_cdp", "target": target, "coords": [cx, cy]}
    finally:
        try:
            await cdp.detach()
        except Exception:
            pass


async def browser_type(target: str, text: str, clear: bool = True) -> dict:
    resolved = await _resolve_target(target)

    if _is_cdp_descriptor(resolved):
        # Focus the CDP node, optionally clear it, then type via CDP key events.
        await browser_click_cdp(target)
        if clear:
            await manager.page.keyboard.press("Control+A")
            await manager.page.keyboard.press("Delete")
        await manager.page.keyboard.type(text, delay=30)
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
