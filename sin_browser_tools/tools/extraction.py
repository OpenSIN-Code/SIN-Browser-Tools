from sin_browser_tools.core import manager

async def browser_console(expression: str) -> dict:
    try:
        result = await manager.page.evaluate(expression)
        return {"result": str(result), "type": type(result).__name__}
    except Exception as e:
        return {"error": str(e)}

async def browser_cdp(method: str, params: dict = None) -> dict:
    try:
        cdp_session = await manager.context.new_cdp_session(manager.page)
        result = await cdp_session.send(method, params or {})
        return {"method": method, "result": result}
    except Exception as e:
        return {"error": str(e), "method": method}


async def browser_get_cookies(url: str = None) -> dict:
    """Return cookies for the current context (optionally filtered by URL)."""
    cookies = await manager.context.cookies(url) if url else await manager.context.cookies()
    return {"count": len(cookies), "cookies": cookies}


async def browser_set_cookie(name: str, value: str, url: str = None, domain: str = None, path: str = "/") -> dict:
    """Set a cookie. Provide either ``url`` OR (``domain`` + ``path``).

    Playwright requires a cookie to be scoped by ``url`` exclusively, or by the
    ``domain``/``path`` pair -- never a mix of ``url`` and ``path``.
    """
    cookie = {"name": name, "value": value}
    if domain:
        cookie["domain"] = domain
        cookie["path"] = path
    else:
        cookie["url"] = url or manager.page.url
    await manager.context.add_cookies([cookie])
    return {"status": "set", "name": name}


async def browser_clear_cookies() -> dict:
    """Clear all cookies in the current browser context."""
    await manager.context.clear_cookies()
    return {"status": "cleared"}


async def browser_get_html(selector: str = None, max_length: int = 200000) -> dict:
    """Return the raw HTML of the page (or of ``selector`` if provided).

    Useful when the accessibility snapshot is not enough and the agent needs to
    inspect markup, hidden attributes, or non-semantic structure. The result is
    truncated to ``max_length`` characters to stay within model context limits.
    """
    if selector:
        el = await manager.page.query_selector(selector)
        if el is None:
            return {"error": f"No element matches selector: {selector}"}
        html = await el.evaluate("e => e.outerHTML")
    else:
        html = await manager.page.content()
    truncated = len(html) > max_length
    return {
        "html": html[:max_length],
        "length": len(html),
        "truncated": truncated,
        "selector": selector,
    }


async def browser_get_links() -> dict:
    """Return every hyperlink on the page with its text, href and visibility.

    Handy for crawling and for picking a navigation target without a full
    snapshot. Hrefs are already resolved to absolute URLs by the browser.
    """
    links = await manager.page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
            text: (a.innerText || a.textContent || '').trim().slice(0, 200),
            href: a.href,
            title: a.title || '',
            visible: !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length)
        })).filter(l => l.href)
        """
    )
    return {"count": len(links), "links": links}


async def browser_get_attribute(selector: str, name: str) -> dict:
    """Read a single attribute (e.g. 'href', 'value', 'aria-label') of an element."""
    el = await manager.page.query_selector(selector)
    if el is None:
        return {"error": f"No element matches selector: {selector}"}
    value = await el.get_attribute(name)
    return {"selector": selector, "attribute": name, "value": value}


async def browser_storage(area: str = "local", action: str = "get", key: str = None, value: str = None) -> dict:
    """Read or write the page's ``localStorage`` / ``sessionStorage``.

    - ``area``: 'local' or 'session'.
    - ``action``: 'get' (dump all or one key), 'set', 'remove', or 'clear'.
    """
    if area not in ("local", "session"):
        raise ValueError("area must be 'local' or 'session'")
    store = "localStorage" if area == "local" else "sessionStorage"

    if action == "get":
        if key is not None:
            result = await manager.page.evaluate(f"k => window.{store}.getItem(k)", key)
            return {"area": area, "key": key, "value": result}
        result = await manager.page.evaluate(
            f"() => Object.fromEntries(Object.entries(window.{store}))"
        )
        return {"area": area, "count": len(result), "items": result}
    if action == "set":
        if key is None:
            raise ValueError("'set' requires a key")
        await manager.page.evaluate(
            f"([k, v]) => window.{store}.setItem(k, v)", [key, value or ""]
        )
        return {"area": area, "action": "set", "key": key}
    if action == "remove":
        if key is None:
            raise ValueError("'remove' requires a key")
        await manager.page.evaluate(f"k => window.{store}.removeItem(k)", key)
        return {"area": area, "action": "removed", "key": key}
    if action == "clear":
        await manager.page.evaluate(f"() => window.{store}.clear()")
        return {"area": area, "action": "cleared"}
    raise ValueError("action must be one of: get, set, remove, clear")
