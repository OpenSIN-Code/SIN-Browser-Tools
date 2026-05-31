import base64
from sin_browser_tools.core import manager

async def browser_vision(full_page: bool = False) -> dict:
    img_bytes = await manager.page.screenshot(full_page=full_page)
    return {"format": "png", "base64": base64.b64encode(img_bytes).decode('utf-8'), "url": manager.page.url}

async def browser_screenshot(full_page: bool = False) -> dict:
    return await browser_vision(full_page=full_page)

async def browser_get_images() -> dict:
    images = await manager.page.evaluate("""
        () => Array.from(document.querySelectorAll('img')).map(img => ({
            src: img.src, alt: img.alt || '', width: img.naturalWidth, height: img.naturalHeight
        })).filter(img => img.src)
    """)
    return {"count": len(images), "images": images}

async def browser_get_text(selector: str = "body") -> dict:
    text = await manager.page.inner_text(selector)
    return {"text": text[:8000], "length": len(text)}
