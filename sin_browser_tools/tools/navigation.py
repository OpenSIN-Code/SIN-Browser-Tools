from sin_browser_tools.core import manager

async def browser_navigate(url: str) -> dict:
    response = await manager.page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return {"status": response.status if response else "unknown", "url": manager.page.url}

async def browser_back() -> dict:
    await manager.page.go_back(wait_until="domcontentloaded")
    return {"status": "navigated_back", "url": manager.page.url}

async def browser_scroll(direction: str = "down", amount: int = 500) -> dict:
    delta = amount if direction == "down" else -amount
    await manager.page.evaluate(f"window.scrollBy(0, {delta})")
    return {"status": "scrolled", "direction": direction, "amount": amount}

async def browser_press(key: str) -> dict:
    await manager.page.keyboard.press(key)
    return {"status": "pressed", "key": key}
