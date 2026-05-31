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
