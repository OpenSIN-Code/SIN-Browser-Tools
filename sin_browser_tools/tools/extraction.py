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
