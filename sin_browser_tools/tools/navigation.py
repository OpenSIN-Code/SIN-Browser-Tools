from sin_browser_tools.core import manager


async def browser_navigate(url: str) -> dict:
    response = await manager.page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return {"status": response.status if response else "unknown", "url": manager.page.url}


async def browser_back() -> dict:
    await manager.page.go_back(wait_until="domcontentloaded")
    return {"status": "navigated_back", "url": manager.page.url}


async def browser_forward() -> dict:
    await manager.page.go_forward(wait_until="domcontentloaded")
    return {"status": "navigated_forward", "url": manager.page.url}


async def browser_reload() -> dict:
    await manager.page.reload(wait_until="domcontentloaded")
    return {"status": "reloaded", "url": manager.page.url}


async def browser_scroll(direction: str = "down", amount: int = 500) -> dict:
    delta = amount if direction == "down" else -amount
    await manager.page.evaluate(f"window.scrollBy(0, {delta})")
    return {"status": "scrolled", "direction": direction, "amount": amount}


async def browser_press(key: str) -> dict:
    """Press a key or key combination, e.g. 'Enter', 'Control+A', 'Escape'."""
    await manager.page.keyboard.press(key)
    return {"status": "pressed", "key": key}


async def browser_get_url() -> dict:
    return {"url": manager.page.url, "title": await manager.page.title()}


async def browser_wait_for(selector: str, state: str = "visible", timeout: float = 10000) -> dict:
    """Wait for a selector to reach a state ('attached', 'detached', 'visible', 'hidden')."""
    try:
        await manager.page.wait_for_selector(selector, state=state, timeout=timeout)
        return {"status": "ready", "selector": selector, "state": state}
    except Exception as e:
        return {"status": "timeout", "selector": selector, "error": str(e)}


async def browser_wait_for_text(text: str, timeout: float = 10000) -> dict:
    """Wait until the given text appears anywhere on the page."""
    try:
        await manager.page.wait_for_function(
            "t => document.body && document.body.innerText.includes(t)",
            arg=text,
            timeout=timeout,
        )
        return {"status": "found", "text": text}
    except Exception as e:
        return {"status": "timeout", "text": text, "error": str(e)}


async def browser_wait_for_load(state: str = "networkidle", timeout: float = 15000) -> dict:
    """Wait for a page load state ('load', 'domcontentloaded', 'networkidle')."""
    try:
        await manager.page.wait_for_load_state(state, timeout=timeout)
        return {"status": "loaded", "state": state, "url": manager.page.url}
    except Exception as e:
        return {"status": "timeout", "state": state, "error": str(e)}


# --- Tab / window management -------------------------------------------------

async def browser_list_tabs() -> dict:
    """List all open tabs in the current context with their index, url and title."""
    pages = manager.context.pages
    tabs = []
    for i, p in enumerate(pages):
        try:
            title = await p.title()
        except Exception:
            title = ""
        tabs.append({
            "index": i,
            "url": p.url,
            "title": title,
            "active": p is manager.page,
        })
    return {"count": len(tabs), "tabs": tabs}


async def browser_new_tab(url: str = None) -> dict:
    """Open a new tab and make it the active page. Optionally navigate to a URL."""
    page = await manager.context.new_page()
    manager.set_active_page(page)
    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return {"status": "opened", "index": manager.context.pages.index(page), "url": page.url}


async def browser_switch_tab(index: int) -> dict:
    """Switch the active page to the tab at the given index."""
    pages = manager.context.pages
    if index < 0 or index >= len(pages):
        raise ValueError(f"Tab index {index} out of range (0..{len(pages) - 1})")
    page = pages[index]
    manager.set_active_page(page)
    await page.bring_to_front()
    return {"status": "switched", "index": index, "url": page.url}


async def browser_close_tab(index: int = None) -> dict:
    """Close a tab by index (defaults to the active tab) and re-focus another."""
    pages = manager.context.pages
    page = manager.page if index is None else pages[index]
    await page.close()
    remaining = manager.context.pages
    if remaining:
        manager.set_active_page(remaining[-1])
    return {"status": "closed", "remaining": len(remaining)}
